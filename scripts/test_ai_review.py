"""Изолированные тесты launcher; не поднимают продукт и не обращаются к API."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("ai_review", Path(__file__).with_name("ai_review.py"))
ai_review = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ai_review)


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ai-review-launcher-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Pilot Test")
        self.git("config", "user.email", "test@example.invalid")
        (self.repo / "sample.py").write_text("value = 1\n", encoding="utf-8")
        self.git("add", "sample.py")
        self.git("commit", "-m", "base")
        self.base = self.git("rev-parse", "HEAD")
        (self.repo / "sample.py").write_text("value = 2\n", encoding="utf-8")
        self.git("commit", "-am", "head")
        self.head = self.git("rev-parse", "HEAD")
        self.output = self.root / "result"
        self.args = ["--repository-root", str(self.repo), "--base", self.base, "--head", self.head,
                     "--base-url", "https://api.example.org/v1", "--model", "test-model",
                     "--output-dir", str(self.output)]

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.repo), *args], stderr=subprocess.DEVNULL, text=True).strip()

    def invoke(self, extra=(), env=None):
        with patch.dict(os.environ, env or {}, clear=True), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return ai_review.main(self.args + list(extra))

    def write_reports(self, quality_changes=None, overview=True):
        self.output.mkdir(exist_ok=True)
        quality = {"requests_ok": 1, "requests_planned": 1, "requests_failed": 0,
                   "responses_unparsable": 0, "requests_unfittable": 0,
                   "responses_truncated": 0, "files_skipped": 0, "judge_unjudged": 0}
        quality.update(quality_changes or {})
        summary = "# AI review\n\n## Обзор\n\nИзменения проверены.\n" if overview else "# AI review\n\n- critical: 0\n"
        (self.output / "ai-review-summary.md").write_text(summary, encoding="utf-8")
        (self.output / "ai-review-findings.json").write_text("[]", encoding="utf-8")
        (self.output / "ai-review-invalid-findings.json").write_text("[]", encoding="utf-8")
        (self.output / "ai-review-usage.json").write_text(json.dumps({"requests": 2, "quality": quality}), encoding="utf-8")

    def test_diverged_target_uses_merge_base(self):
        self.git("checkout", "-b", "target", self.base)
        (self.repo / "target.txt").write_text("target only\n", encoding="utf-8")
        self.git("add", "target.txt")
        self.git("commit", "-m", "target advances")
        target = self.git("rev-parse", "HEAD")
        self.git("checkout", "main")
        self.assertEqual(ai_review.resolve_range(self.repo, target, self.head), (self.base, self.head))

    def test_dirty_checkout_rejected(self):
        (self.repo / "sample.py").write_text("value = 3\n", encoding="utf-8")
        with self.assertRaisesRegex(ai_review.PilotError, "незакоммиченные"):
            ai_review.resolve_range(self.repo, self.base, self.head)

    def test_head_mismatch_rejected(self):
        with self.assertRaisesRegex(ai_review.PilotError, "HEAD"):
            ai_review.resolve_range(self.repo, self.base, self.base)

    def test_untracked_launcher_does_not_change_review_range(self):
        (self.repo / "launcher.py").write_text("pass\n", encoding="utf-8")
        self.assertEqual(ai_review.resolve_range(self.repo, self.base, self.head), (self.base, self.head))

    def test_existing_report_is_not_overwritten(self):
        self.output.mkdir()
        report = self.output / "ai-review-summary.md"
        report.write_text("original", encoding="utf-8")
        with patch.object(ai_review, "validate_installation") as validate:
            self.assertEqual(self.invoke(), 1)
        validate.assert_not_called()
        self.assertEqual(report.read_text(encoding="utf-8"), "original")

    def test_check_does_not_start_review_or_write_output(self):
        with patch.object(ai_review, "validate_installation"), patch.object(ai_review, "resolve_range", return_value=(self.base, self.head)), patch.object(ai_review.subprocess, "run") as run:
            self.assertEqual(self.invoke(["--check"]), 0)
        run.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_missing_key_blocks_review(self):
        with patch.object(ai_review, "validate_installation"), patch.object(ai_review, "resolve_range", return_value=(self.base, self.head)), patch.object(ai_review.subprocess, "run") as run:
            self.assertEqual(self.invoke(), 1)
        run.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_environment_isolated_and_single_model(self):
        env = ai_review.build_environment({"AI_REVIEWER_PROVIDER__BASE_URL": "https://wrong.invalid",
            "AI_REVIEWER_MCP__ENABLED": "true", "CI_API_V4_URL": "https://gitlab.invalid",
            "GITLAB_USER_LOGIN": "user", "TECH_GITLAB_API_TOKEN": "gitlab-secret", "OPENAI_API_KEY": "api-secret",
            "PATH": "keep"}, "https://api.example.org/v1", "one-model", 32768)
        self.assertEqual(env["PATH"], "keep")
        self.assertEqual(env["OPENAI_API_KEY"], "api-secret")
        self.assertNotIn("TECH_GITLAB_API_TOKEN", env)
        self.assertFalse(any(key.startswith(("CI_", "GITLAB_")) for key in env))
        self.assertEqual(env["AI_REVIEWER_SKILLS__SEARCH_PATHS"], "")
        self.assertEqual(env["AI_REVIEWER_REVIEW__PROJECT_CONTEXT_PATH"], "")
        self.assertEqual(env["AI_REVIEWER_REVIEW__RULES_PATH"], "")
        self.assertEqual(env["AI_REVIEWER_MCP__ENABLED"], "false")
        for name in ("PROVIDER__MODEL", "REVIEW__HOLISTIC__MODEL", "REVIEW__FINDING_VERIFICATION__MODEL"):
            self.assertEqual(env["AI_REVIEWER_" + name], "one-model")

    def test_insecure_or_credential_bearing_endpoint_rejected(self):
        for value in ("http://api.example.org/v1", "https://user:secret@api.example.org/v1", "https://api.example.org?key=secret", "https://example.invalid/v1", "https://api.example.org/#secret"):
            with self.subTest(value=value), self.assertRaises(ai_review.PilotError):
                ai_review.validate_endpoint(value)

    def test_economy_cli_passes_budgets_to_engine_without_disabling_review_stages(self):
        def fake_run(command, **kwargs):
            env = kwargs["env"]
            expected = {
                "PROVIDER__MAX_OUTPUT_TOKENS": "2048", "PROVIDER__LONG_FORM_MAX_OUTPUT_TOKENS": "4096",
                "REVIEW__MAX_FILES": "5", "REVIEW__MAX_DIFF_LINES": "300", "REVIEW__CHUNK_DIFF_LINES": "300",
                "REVIEW__FINDING_VERIFICATION__WHOLE_FILE": "false",
                "REVIEW__FINDING_VERIFICATION__CONTEXT_LINES": "20",
                "REVIEW__FINDING_VERIFICATION__HEADER_LINES": "20",
                "REVIEW__FINDING_VERIFICATION__MAX_BATCH_CHARS": "12000",
                "REVIEW__FINDING_VERIFICATION__ENABLED": "true", "REVIEW__HOLISTIC__ENABLED": "true",
                "PROVIDER__MAX_CONCURRENCY": "1", "PROVIDER__MAX_RETRIES": "0",
            }
            for name, value in expected.items():
                self.assertEqual(env["AI_REVIEWER_" + name], value)
            self.write_reports()
            return subprocess.CompletedProcess(command, 0)
        with patch.object(ai_review, "validate_installation"), patch.object(ai_review, "resolve_range", return_value=(self.base, self.head)), patch.object(ai_review.subprocess, "run", side_effect=fake_run):
            self.assertEqual(self.invoke(["--economy"], env={"OPENAI_API_KEY": "api-secret"}), 0)

    def test_default_profile_keeps_existing_limits_and_does_not_inherit_economy(self):
        source = {"AI_REVIEWER_REVIEW__MAX_FILES": "5", "AI_REVIEWER_PROVIDER__MAX_OUTPUT_TOKENS": "2048"}
        env = ai_review.build_environment(source, "https://api.example.org/v1", "one-model", 32768)
        self.assertEqual(env["AI_REVIEWER_PROVIDER__MAX_OUTPUT_TOKENS"], "8192")
        self.assertEqual(env["AI_REVIEWER_PROVIDER__LONG_FORM_MAX_OUTPUT_TOKENS"], "16384")
        self.assertNotIn("AI_REVIEWER_REVIEW__MAX_FILES", env)
        self.assertNotIn("AI_REVIEWER_REVIEW__FINDING_VERIFICATION__WHOLE_FILE", env)

    def test_subprocess_is_isolated_no_publish_and_keeps_secret_out_of_args(self):
        def fake_run(command, **kwargs):
            self.assertIn("-I", command)
            self.assertIn("--no-publish", command)
            self.assertLess(command.index("--repository-root"), command.index("review"))
            self.assertNotIn("api-secret", " ".join(command))
            self.assertEqual(kwargs["cwd"], self.output)
            self.assertEqual(kwargs["env"]["OPENAI_API_KEY"], "api-secret")
            self.write_reports()
            return subprocess.CompletedProcess(command, 0)
        with patch.object(ai_review, "validate_installation"), patch.object(ai_review, "resolve_range", return_value=(self.base, self.head)), patch.object(ai_review.subprocess, "run", side_effect=fake_run):
            self.assertEqual(self.invoke(env={"OPENAI_API_KEY": "api-secret"}), 0)

    def test_child_failure_is_not_success(self):
        with patch.object(ai_review, "validate_installation"), patch.object(ai_review, "resolve_range", return_value=(self.base, self.head)), patch.object(ai_review.subprocess, "run", return_value=subprocess.CompletedProcess([], 7)):
            self.assertEqual(self.invoke(env={"OPENAI_API_KEY": "api-secret"}), 7)

    def test_missing_artifacts_is_not_success(self):
        with patch.object(ai_review, "validate_installation"), patch.object(ai_review, "resolve_range", return_value=(self.base, self.head)), patch.object(ai_review.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)):
            self.assertEqual(self.invoke(env={"OPENAI_API_KEY": "api-secret"}), 1)

    def test_successful_clean_review_with_zero_findings_is_accepted(self):
        self.write_reports()
        ai_review.assert_complete_review(self.output)

    def test_exit_zero_with_failed_chunk_is_not_success(self):
        def fake_run(command, **kwargs):
            self.write_reports({"requests_ok": 0, "requests_failed": 1})
            return subprocess.CompletedProcess(command, 0)
        with patch.object(ai_review, "validate_installation"), patch.object(ai_review, "resolve_range", return_value=(self.base, self.head)), patch.object(ai_review.subprocess, "run", side_effect=fake_run):
            self.assertEqual(self.invoke(env={"OPENAI_API_KEY": "api-secret"}), 1)
        self.assertTrue((self.output / "ai-review-usage.json").is_file())

    def test_incomplete_quality_counters_block_success(self):
        for name in ("requests_failed", "responses_unparsable", "requests_unfittable",
                     "responses_truncated", "files_skipped", "judge_unjudged"):
            with self.subTest(counter=name):
                self.write_reports({name: 1})
                with self.assertRaises(ai_review.PilotError):
                    ai_review.assert_complete_review(self.output)

    def test_missing_quality_counter_blocks_success(self):
        self.write_reports({"judge_unjudged": None})
        with self.assertRaises(ai_review.PilotError):
            ai_review.assert_complete_review(self.output)

    def test_missing_usage_blocks_success(self):
        self.write_reports()
        (self.output / "ai-review-usage.json").unlink()
        with self.assertRaises(ai_review.PilotError):
            ai_review.assert_complete_review(self.output)

    def test_holistic_fail_open_without_overview_blocks_success(self):
        # Judge can succeed after holistic failed, so total requests alone is insufficient.
        self.write_reports(overview=False)
        with self.assertRaisesRegex(ai_review.PilotError, "Holistic"):
            ai_review.assert_complete_review(self.output)

    def test_invalid_individual_finding_blocks_success(self):
        self.write_reports()
        (self.output / "ai-review-invalid-findings.json").write_text('[{"index": 0, "error": "missing path"}]', encoding="utf-8")
        with self.assertRaises(ai_review.PilotError):
            ai_review.assert_complete_review(self.output)


if __name__ == "__main__":
    unittest.main()
