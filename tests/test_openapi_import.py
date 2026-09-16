"""
    Тесты импорта фич из OpenAPI/Swagger (POST /api/openapi, см. pult/openapi.py)
"""

import json

import pytest

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


@pytest.mark.smoke
def test_import_openapi_from_text(api):
    resp = api.import_openapi(text=json.dumps(MINI_SPEC, ensure_ascii=False))
    assert resp.status_code == 200

    data = resp.json()
    assert data["ok"] is True
    assert data["count"] == 2
    assert {op["method"] for op in data["operations"]} == {"GET", "POST"}


@pytest.mark.regress
def test_import_openapi_from_file_bytes(api):
    spec_bytes = json.dumps(MINI_SPEC, ensure_ascii=False).encode("utf-8")
    resp = api.import_openapi_file(spec_bytes, content_type="application/octet-stream")
    assert resp.status_code == 200

    data = resp.json()
    assert data["ok"] is True
    assert data["count"] == 2


@pytest.mark.regress
def test_import_openapi_without_url_or_text_is_rejected(api):
    resp = api.import_openapi()
    assert resp.status_code == 400


@pytest.mark.regress
def test_import_openapi_file_empty_is_rejected(api):
    resp = api.import_openapi_file(b"", content_type="application/octet-stream")
    assert resp.status_code == 400


@pytest.mark.regress
def test_import_openapi_non_object_is_soft_error(api):
    # валиден как JSON, но верхний уровень — не объект: SpecError, а не 400/500
    resp = api.import_openapi(text="[1, 2, 3]")
    assert resp.status_code == 200
    assert "error" in resp.json()


@pytest.mark.regress
def test_import_openapi_missing_paths_is_soft_error(api):
    resp = api.import_openapi(text=json.dumps({"openapi": "3.0.0"}))
    assert resp.status_code == 200
    assert "paths" in resp.json().get("error", "")
