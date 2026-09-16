"""
    Тесты импорта кейсов из TMS-выгрузки (POST /api/tms, см. pult/tmsio.py)
"""

import allure
import pytest

from helpers.allure_helper.allure_assertion import assert_contains, assert_equals, assert_status_code, assert_true

CSV_HAPPY_PATH = (
    "Название,Раздел,Автоматизация\r\n"
    "Логин работает,Smoke регресс,автоматизировано\r\n"
    "Проверка профиля,Sanity проверка,ручной\r\n"
).encode()


@allure.title("Импорт CSV с русскими заголовками — угадывание колонок")
@pytest.mark.smoke
def test_import_tms_csv_happy_path(api):
    with allure.step("Отправить CSV-выгрузку кейсов"):
        resp = api.import_tms(CSV_HAPPY_PATH, content_type="text/csv")
        assert_status_code(resp, 200)

    with allure.step("Проверить заголовки, число строк и угаданный маппинг колонок"):
        data = resp.json()
        assert_true(data["ok"] is True, "ok: true")
        assert_equals(data["headers"], ["Название", "Раздел", "Автоматизация"], "заголовки таблицы")
        assert_equals(data["total"], 2, "число строк с кейсами")
        # автоугадывание колонок (см. tmsio._GUESS) — по русским заголовкам
        assert_equals(data["guess"]["title"], 0, "колонка названия")
        assert_equals(data["guess"]["section"], 1, "колонка раздела")
        assert_equals(data["guess"]["automation"], 2, "колонка автоматизации")


@allure.title("Пустой файл — мягкая ошибка, не 400/500")
@pytest.mark.regress
def test_import_tms_empty_file_is_soft_error(api):
    with allure.step("Отправить пустой файл"):
        resp = api.import_tms(b"", content_type="text/csv")
        assert_status_code(resp, 200)

    with allure.step("Проверить, что ответ содержит error"):
        assert_contains(resp.json(), "error", "ключ error в ответе")


@allure.title("Битый .xlsx (похож на zip, но не архив) — мягкая ошибка")
@pytest.mark.regress
def test_import_tms_broken_xlsx_is_soft_error(api):
    with allure.step("Отправить файл с сигнатурой zip (PK), но невалидным содержимым"):
        resp = api.import_tms(b"PK\x03\x04not a real zip", content_type="application/octet-stream")
        assert_status_code(resp, 200)

    with allure.step("Проверить, что ответ содержит error"):
        assert_contains(resp.json(), "error", "ключ error в ответе")
