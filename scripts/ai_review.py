"""Ручной запуск исходного ai-reviewer через API; без публикации и исполнения кода PR."""

from __future__ import annotations

import argparse
import getpass
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from urllib.parse import urlsplit

REVIEWER_VERSION = "0.17.1"


class PilotError(Exception):
    """Ошибка подготовки или неполное ревью; артефакты сохраняются."""


def git(repository: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *args],
        capture_output=True, text=True, encoding="utf-8", check=False,
    )
    if result.returncode:
        # Git diagnostics may repeat credentials in malformed arguments.
        raise PilotError("Git не смог проверить репозиторий или указанные commits.")
    return result.stdout.strip()


def resolve_range(repository: Path, base: str, head: str) -> tuple[str, str]:
    base_sha = git(repository, "rev-parse", "--verify", "--end-of-options", base + "^{commit}")
    head_sha = git(repository, "rev-parse", "--verify", "--end-of-options", head + "^{commit}")
    if git(repository, "rev-parse", "HEAD") != head_sha:
        raise PilotError("HEAD проверяемой копии должен совпадать с --head.")
    if git(repository, "diff", "--no-ext-diff", "--no-textconv", "--name-only", "HEAD", "--"):
        raise PilotError("Есть незакоммиченные изменения отслеживаемых файлов; нужна чистая копия.")
    merge_base = git(repository, "merge-base", base_sha, head_sha)
    if not git(repository, "diff", "--no-ext-diff", "--no-textconv", "--name-only", merge_base, head_sha, "--"):
        raise PilotError("Между merge-base и head нет изменений для ревью.")
    return merge_base, head_sha


def validate_endpoint(value: str) -> str:
    try:
        parsed = urlsplit(value)
        valid_port = parsed.port  # Raises for malformed ports.
    except ValueError:
        raise PilotError("Некорректный адрес API.") from None
    if (
        parsed.scheme != "https" or not parsed.hostname
        or parsed.username is not None or parsed.password is not None
        or parsed.query or parsed.fragment
        or any(char.isspace() for char in value)
        or parsed.hostname == "example.invalid" or parsed.hostname.endswith(".example.invalid")
        or (valid_port is not None and valid_port <= 0)
    ):
        raise PilotError("Нужен HTTPS endpoint без логина, пароля, query и fragment; placeholder не подходит.")
    return value.rstrip("/")


def build_environment(
    source: dict[str, str], endpoint: str, model: str, context_tokens: int, economy: bool = False,
) -> dict[str, str]:
    """Сбрасывает наследованные параметры: результат воспроизводим локально и в CI."""
    env = {
        name: value for name, value in source.items()
        if not name.upper().startswith(("AI_REVIEWER_", "CI_", "GITLAB_"))
        and name.upper() != "TECH_GITLAB_API_TOKEN"
    }
    settings = {
        "PROFILE": "costs", "COLOR": "never", "VERBOSE": "false",
        "PROVIDER__TYPE": "openai-compatible", "PROVIDER__BASE_URL": endpoint,
        "PROVIDER__MODEL": model, "PROVIDER__DISABLE_THINKING": "false",
        "PROVIDER__MODELS_ENDPOINT_ENABLED": "false", "PROVIDER__CONTEXT_TOKENS": str(context_tokens),
        "PROVIDER__MAX_OUTPUT_TOKENS": "8192", "PROVIDER__LONG_FORM_MAX_OUTPUT_TOKENS": "16384",
        "PROVIDER__MAX_CONCURRENCY": "1", "PROVIDER__MAX_RETRIES": "0",
        "REVIEW__LANGUAGE": "ru", "REVIEW__HOLISTIC__ENABLED": "true",
        "REVIEW__HOLISTIC__MODEL": model, "REVIEW__FINDING_VERIFICATION__ENABLED": "true",
        "REVIEW__FINDING_VERIFICATION__MODEL": model,
        "REVIEW__FINDING_VERIFICATION__TOOLS_ENABLED": "false",
        "REVIEW__FINDING_VERIFICATION__DISABLE_THINKING": "false",
        "REVIEW__INCREMENTAL__ENABLED": "false", "REVIEW__RESUME__ENABLED": "false",
        "REVIEW__EXTERNAL_CHECKS__ENABLED": "false", "REVIEW__DUMP_PROMPTS": "false",
        "REVIEW__PROJECT_CONTEXT_PATH": "", "REVIEW__RULES_PATH": "",
        "SKILLS__SELECTION_STRATEGY": "static", "SKILLS__OPTIMIZE__ENABLED": "false",
        "SKILLS__DISTILL__ENABLED": "false", "SKILLS__SEARCH_PATHS": "",
        "MCP__ENABLED": "false", "PUBLISH__INLINE__ENABLED": "false",
        "PUBLISH__SUMMARY_NOTE": "false", "PUBLISH__MERGE_REQUEST_DESCRIPTION__ENABLED": "false",
        "PUBLISH__ASSIGNMENT__ENABLED": "false",
    }
    if economy:
        settings.update({
            "PROVIDER__MAX_OUTPUT_TOKENS": "2048", "PROVIDER__LONG_FORM_MAX_OUTPUT_TOKENS": "4096",
            "REVIEW__MAX_FILES": "5", "REVIEW__MAX_DIFF_LINES": "300", "REVIEW__CHUNK_DIFF_LINES": "300",
            "REVIEW__FINDING_VERIFICATION__WHOLE_FILE": "false",
            "REVIEW__FINDING_VERIFICATION__CONTEXT_LINES": "20",
            "REVIEW__FINDING_VERIFICATION__HEADER_LINES": "20",
            "REVIEW__FINDING_VERIFICATION__MAX_BATCH_CHARS": "12000",
        })
    env.update({"AI_REVIEWER_" + name: value for name, value in settings.items()})
    env["PYTHONUTF8"] = "1"
    return env


def validate_installation(env: dict[str, str]) -> None:
    try:
        installed = importlib.metadata.version("ai-reviewer")
    except importlib.metadata.PackageNotFoundError:
        raise PilotError("ai-reviewer не установлен в этом Python; используй venv пилота.") from None
    if installed != REVIEWER_VERSION:
        raise PilotError(f"Нужна проверенная версия ai-reviewer {REVIEWER_VERSION}, установлена {installed}.")
    check_env = {name: value for name, value in env.items() if name.upper() != "OPENAI_API_KEY"}
    result = subprocess.run(
        [sys.executable, "-I", "-X", "utf8", "-c", "from ai_reviewer.config import AppConfig; AppConfig()"],
        cwd=Path(__file__).resolve().parent, env=check_env, capture_output=True, check=False,
    )
    if result.returncode:
        raise PilotError("Установленный ai-reviewer не смог загрузить конфигурацию пилота.")


def assert_complete_review(output: Path) -> None:
    """Exit 0 у движка не доказывает полноту: часть ошибок он обрабатывает fail-open."""
    try:
        summary = (output / "ai-review-summary.md").read_text(encoding="utf-8")
        findings = json.loads((output / "ai-review-findings.json").read_text(encoding="utf-8"))
        invalid = json.loads((output / "ai-review-invalid-findings.json").read_text(encoding="utf-8"))
        usage = json.loads((output / "ai-review-usage.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise PilotError("Нет полного набора корректных артефактов; ревью нельзя считать выполненным.") from None
    if not isinstance(findings, list) or invalid != [] or not isinstance(usage, dict):
        raise PilotError("Некорректные или потерянные находки в артефактах; ревью неполное.")
    quality = usage.get("quality")
    if not isinstance(quality, dict):
        raise PilotError("Отсутствуют метрики качества; полнота ревью не подтверждена.")

    def counter(source: dict, name: str) -> int:
        value = source.get(name)
        if type(value) is not int or value < 0:
            raise PilotError(f"Нет корректного счётчика {name}; полнота ревью не подтверждена.")
        return value

    successful = counter(quality, "requests_ok")
    if successful == 0 or counter(quality, "requests_planned") != successful:
        raise PilotError("Не все запланированные запросы ревью успешно выполнены.")
    failures = (
        "requests_failed", "responses_unparsable", "requests_unfittable",
        "responses_truncated", "files_skipped", "judge_unjudged",
    )
    for name in failures:
        if counter(quality, name) != 0:
            raise PilotError(f"Ревью неполное: {name} > 0. Артефакты оставлены для диагностики.")
    # In pinned 0.17.1 holistic provider errors are only logged, not counted in
    # quality. The renderer inserts this opening section iff overview is nonempty;
    # finding text later in the report must not impersonate that section.
    lines = summary.splitlines()
    if counter(usage, "requests") <= successful or len(lines) < 5 or lines[2] != "## Обзор" or not lines[4].strip():
        raise PilotError("Holistic pass не подтвердил полный обзор; ревью неполное.")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--base", required=True, help="Целевая ветка/commit; используется общий предок с head")
    result.add_argument("--head", required=True, help="Проверяемый commit, совпадающий с HEAD")
    result.add_argument("--repository-root", type=Path, default=Path(__file__).resolve().parents[1])
    result.add_argument("--base-url", default=os.environ.get("AI_REVIEW_BASE_URL", ""))
    result.add_argument("--model", default=os.environ.get("AI_REVIEW_MODEL", ""))
    result.add_argument("--context-tokens", type=int, default=32768)
    result.add_argument("--output-dir", type=Path)
    result.add_argument("--check", action="store_true", help="Проверка установки и diff без запросов к API")
    result.add_argument("--prompt-key", action="store_true", help="Скрытый ввод ключа вместо значения в команде")
    result.add_argument("--economy", action="store_true", help="Небольшой пилот: до 5 файлов и 300 строк diff, сокращённый бюджет ответов")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        endpoint = validate_endpoint(args.base_url)
        if not args.model or any(char.isspace() for char in args.model):
            raise PilotError("Укажи имя модели через --model или AI_REVIEW_MODEL.")
        if args.context_tokens < 8192:
            raise PilotError("Для пилота нужен context-tokens >= 8192, не выше окна выбранной модели.")
        repository = args.repository_root.resolve()
        base_sha, head_sha = resolve_range(repository, args.base, args.head)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output = (args.output_dir or repository / "ai-review-results" / (stamp + "-" + uuid.uuid4().hex[:8])).resolve()
        if output.exists() and (not output.is_dir() or any(output.iterdir())):
            raise PilotError("Каталог результатов уже непустой; выбери новый --output-dir.")
        env = build_environment(dict(os.environ), endpoint, args.model, args.context_tokens, economy=args.economy)
        validate_installation(env)
        print(f"ai-reviewer: {REVIEWER_VERSION}\nРепозиторий: {repository}\nMerge-base: {base_sha}\nHead: {head_sha}")
        print(f"API: {endpoint}\nМодель: {args.model}\nКаталог результата: {output}")
        if args.check:
            print("API-ключ: " + ("задан" if env.get("OPENAI_API_KEY", "").strip() else "не задан"))
            print("Подготовка проверена. API не вызывался; AI-ревью не выполнено.")
            return 0
        if args.prompt_key and not env.get("OPENAI_API_KEY", "").strip():
            env["OPENAI_API_KEY"] = getpass.getpass("API-ключ (ввод скрыт): ").strip()
        if not env.get("OPENAI_API_KEY", "").strip():
            raise PilotError("Нужен OPENAI_API_KEY или --prompt-key; ключ не следует передавать аргументом команды.")
        output.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            [sys.executable, "-I", "-X", "utf8", "-c", "from ai_reviewer.cli import main; main()",
             "--repository-root", str(repository), "--output-dir", str(output),
             "review", "--base-sha", base_sha, "--head-sha", head_sha, "--no-publish"],
            cwd=output, env=env, check=False,
        )
        if result.returncode:
            return result.returncode
        assert_complete_review(output)
        print(f"Отчёт: {output / 'ai-review-summary.md'}")
        return 0
    except (PilotError, OSError, EOFError) as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
