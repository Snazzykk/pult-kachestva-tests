"""
    Модуль настройки тестового стенда «Пульта качества».

    У «Пульта» нет задеплоенного стенда — сервер локальный и поднимается
    самими тестами на время прогона (см. conftest.py::pult_server). Поэтому
    «стенд» здесь один — адрес/порт, куда его поднимать.

    Код самого «Пульта качества» — отдельный репозиторий (pult-kachestva),
    тесты его не хранят у себя. PULT_REPO_PATH — путь, где его искать:
    по умолчанию ждём стандартный локальный layout (оба репозитория —
    соседи по каталогу), в CI подменяется переменной окружения на то
    место, куда workflow его чекаутит.
"""

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent

PULT_REPO_PATH = Path(os.environ.get("PULT_REPO_PATH", REPO_ROOT.parent / "pult-kachestva"))

local = {
    "name": "local",
    "pult": {
        "host": os.environ.get("PULT_TEST_HOST", "127.0.0.1"),
        "port": int(os.environ.get("PULT_TEST_PORT", "7997")),
    },
}

STAND = local
