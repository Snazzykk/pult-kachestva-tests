"""
    Тесты импорта фич из OpenAPI/Swagger (POST /api/openapi, см. pult/openapi.py)
"""

import json

import allure
import pytest

from helpers.allure_helper.allure_assertion import assert_contains, assert_equals, assert_status_code, assert_true

MINI_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "Mini API", "version": "1.0"},
    "paths": {
        "/pets": {
            "get": {"summary": "Список питомцев", "tags": ["pets"]},
            "post": {"summary": "Завести питомца", "tags": ["pets"]},
        }
    },
}


@allure.title("Импорт OpenAPI-спеки текстом")
@pytest.mark.smoke
def test_import_openapi_from_text(api):
    with allure.step("Отправить спеку текстом (JSON)"):
        resp = api.import_openapi(text=json.dumps(MINI_SPEC, ensure_ascii=False))
        assert_status_code(resp, 200)

    with allure.step("Проверить разобранные операции"):
        data = resp.json()
        assert_true(data["ok"] is True, "ok: true")
        assert_equals(data["count"], 2, "найдено 2 операции")
        assert_equals({op["method"] for op in data["operations"]}, {"GET", "POST"}, "методы GET и POST")


@allure.title("Импорт OpenAPI-спеки файлом (сырые байты)")
@pytest.mark.regress
def test_import_openapi_from_file_bytes(api):
    with allure.step("Отправить спеку файлом, не JSON-обёрткой"):
        spec_bytes = json.dumps(MINI_SPEC, ensure_ascii=False).encode("utf-8")
        resp = api.import_openapi_file(spec_bytes, content_type="application/octet-stream")
        assert_status_code(resp, 200)

    with allure.step("Проверить разобранные операции"):
        data = resp.json()
        assert_true(data["ok"] is True, "ok: true")
        assert_equals(data["count"], 2, "найдено 2 операции")


@allure.title("Импорт без url и без text отклоняется 400")
@pytest.mark.regress
def test_import_openapi_without_url_or_text_is_rejected(api):
    with allure.step("Запрос без url и без text"):
        resp = api.import_openapi()
        assert_status_code(resp, 400)


@allure.title("Импорт пустого файла отклоняется 400")
@pytest.mark.regress
def test_import_openapi_file_empty_is_rejected(api):
    with allure.step("Отправить пустой файл"):
        resp = api.import_openapi_file(b"", content_type="application/octet-stream")
        assert_status_code(resp, 400)


@allure.title("Спека без объекта на верхнем уровне — мягкая ошибка, не 400/500")
@pytest.mark.regress
def test_import_openapi_non_object_is_soft_error(api):
    with allure.step("Отправить валидный JSON, но не объект (список)"):
        resp = api.import_openapi(text="[1, 2, 3]")
        assert_status_code(resp, 200)

    with allure.step("Проверить, что ответ содержит error"):
        assert_contains(resp.json(), "error", "ключ error в ответе")


@allure.title("Спека без секции paths — мягкая ошибка, не 400/500")
@pytest.mark.regress
def test_import_openapi_missing_paths_is_soft_error(api):
    with allure.step("Отправить объект-спеку без paths"):
        resp = api.import_openapi(text=json.dumps({"openapi": "3.0.0"}))
        assert_status_code(resp, 200)

    with allure.step("Проверить текст ошибки"):
        assert_contains(resp.json().get("error", ""), "paths", "упоминание paths в тексте ошибки")
