"""
    Отправка итогов прогона в Telegram — по образцу отчёта в CI-пайплайне.

    Не обязательный шаг: если секреты TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID
    не заданы, скрипт молча ничего не делает (exit 0) — не ломает пайплайн,
    пока уведомления никому не нужны.

    python scripts/send_telegram_notification.py \
        --total 23 --passed 23 --failed 0 --duration 4.2 \
        --report-url https://... --ref master --status success
"""

from __future__ import annotations

import argparse
import os
import sys

import requests

_API = "https://api.telegram.org/bot{token}/sendMessage"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--total", type=int, default=0)
    ap.add_argument("--passed", type=int, default=0)
    ap.add_argument("--failed", type=int, default=0)
    ap.add_argument("--duration", default="?")
    ap.add_argument("--report-url", default="")
    ap.add_argument("--ref", default="?", help="ветка/тег pult-kachestva, который проверяли")
    ap.add_argument("--status", choices=["success", "failed"], default="failed")
    ap.add_argument("--run-url", default="", help="ссылка на запуск workflow в GitHub Actions")
    args = ap.parse_args()

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("[i] TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID не заданы — уведомление пропущено")
        return 0

    icon = "✅" if args.status == "success" else "❌"
    lines = [
        f"{icon} Пульт качества — автотесты API ({args.ref})",
        f"Всего: {args.total}  ·  Прошло: {args.passed}  ·  Упало: {args.failed}  ·  {args.duration}с",
    ]
    if args.report_url:
        lines.append(f"Отчёт: {args.report_url}")
    if args.run_url:
        lines.append(f"Запуск: {args.run_url}")
    text = "\n".join(lines)

    try:
        resp = requests.post(_API.format(token=token),
                             json={"chat_id": chat_id, "text": text}, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as exc:
        # уведомление — не критичный шаг пайплайна, не роняем CI из-за него
        print(f"[!] не отправилось в Telegram: {exc}")
        return 0

    print("[ok] уведомление отправлено")
    return 0


if __name__ == "__main__":
    sys.exit(main())
