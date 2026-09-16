"""
    Инициализация и фикстуры, выполняемые до тестов API «Пульта качества».

    У «Пульта» нет постоянно поднятого стенда — сервер локальный. Поэтому
    сессия тестов сама поднимает `python run.py` из репозитория pult-kachestva
    (см. configuration.PULT_REPO_PATH) на отдельном порту и отдельном
    scratch-файле состояния, а в конце гасит процесс.
"""

import subprocess
import sys
import time

import pytest
import requests

from configuration import PULT_REPO_PATH, STAND
from helpers.pult_helper import PultAPI

RUN_PY = PULT_REPO_PATH / "run.py"
_START_TIMEOUT = 15  # секунд — сколько ждём, пока сервер поднимется


@pytest.fixture(scope="session")
def state_file(tmp_path_factory):
    """
        Отдельный файл состояния на всю сессию тестов — не связан
        с реальными данными пользователя
    """
    return tmp_path_factory.mktemp("pult-api-tests") / "quality-state.yml"


@pytest.fixture(scope="session")
def pult_server(state_file):
    """
        Поднимает локальный сервер «Пульта качества» на время сессии тестов
    """
    if not RUN_PY.exists():
        pytest.exit(f"не найден run.py в {PULT_REPO_PATH} — склонируй pult-kachestva "
                    f"рядом с этим репозиторием (или задай PULT_REPO_PATH)")

    host, port = STAND["pult"]["host"], STAND["pult"]["port"]
    proc = subprocess.Popen(  # noqa: S603 — фиксированные аргументы, не пользовательский ввод
        [sys.executable, str(RUN_PY), "--file", str(state_file),
         "--host", host, "--port", str(port), "--no-browser"],
        cwd=PULT_REPO_PATH, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )

    base_url = f"http://{host}:{port}"
    deadline = time.time() + _START_TIMEOUT
    last_err = None
    up = False
    while time.time() < deadline:
        if proc.poll() is not None:
            break  # процесс уже упал — нет смысла ждать таймаут
        try:
            requests.get(f"{base_url}/api/meta", timeout=1)
            up = True
            break
        except requests.RequestException as exc:
            last_err = exc
            time.sleep(0.3)

    if not up:
        out = proc.stdout.read() if proc.stdout else ""
        proc.terminate()
        pytest.exit(f"сервер «Пульта качества» не поднялся за {_START_TIMEOUT}с "
                    f"на {base_url}: {last_err}\n{out}")

    yield proc

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture(scope="session")
def api(pult_server):
    """
        PultAPI — фасад для тестов, использует поднятый pult_server
    """
    return PultAPI(STAND)


@pytest.fixture
def clean_state(api):
    """
        Перед тестом — пустое состояние, чтобы тесты не зависели друг от друга
    """
    api.put_state({})
    yield
    api.put_state({})
