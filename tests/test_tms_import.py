"""
    Тесты импорта кейсов из TMS-выгрузки (POST /api/tms, см. pult/tmsio.py)
"""

import pytest

CSV_HAPPY_PATH = (
    "Название,Раздел,Автоматизация\r\n"
    "Логин работает,Smoke регресс,автоматизировано\r\n"
    "Проверка профиля,Sanity проверка,ручной\r\n"
).encode()


@pytest.mark.smoke
def test_import_tms_csv_happy_path(api):
    resp = api.import_tms(CSV_HAPPY_PATH, content_type="text/csv")
    assert resp.status_code == 200

    data = resp.json()
    assert data["ok"] is True
    assert data["headers"] == ["Название", "Раздел", "Автоматизация"]
    assert data["total"] == 2
    # автоугадывание колонок (см. tmsio._GUESS) — по русским заголовкам
    assert data["guess"]["title"] == 0
    assert data["guess"]["section"] == 1
    assert data["guess"]["automation"] == 2


@pytest.mark.regress
def test_import_tms_empty_file_is_soft_error(api):
    resp = api.import_tms(b"", content_type="text/csv")
    assert resp.status_code == 200
    assert "error" in resp.json()


@pytest.mark.regress
def test_import_tms_broken_xlsx_is_soft_error(api):
    # похоже на .xlsx (сигнатура zip "PK"), но не валидный архив
    resp = api.import_tms(b"PK\x03\x04not a real zip", content_type="application/octet-stream")
    assert resp.status_code == 200
    assert "error" in resp.json()
