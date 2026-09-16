"""
    Тесты JSON API: /api/state, /api/yaml, /api/meta (см. pult/server.py в pult-kachestva)
"""

import pytest


@pytest.mark.smoke
def test_index_page_ok(api):
    resp = api.client.get("/")
    assert resp.status_code == 200
    assert "html" in resp.headers.get("Content-Type", "").lower()


@pytest.mark.smoke
def test_state_after_clean_is_effectively_empty(api, clean_state):
    resp = api.get_state()
    assert resp.status_code == 200
    data = resp.json()
    # save_state всегда проставляет company.updated — буквально {} не бывает
    # после хотя бы одного сохранения, но больше в состоянии ничего не должно быть
    assert set(data.keys()) <= {"company"}
    assert set(data.get("company", {}).keys()) <= {"updated"}


@pytest.mark.smoke
def test_save_and_read_back_state(api, clean_state):
    body = {"company": {"name": "Acme"}, "practices": [{"id": "process", "level": 2, "target": 3}]}

    put_resp = api.put_state(body)
    assert put_resp.status_code == 200
    assert put_resp.json()["ok"] is True

    saved = api.get_state().json()
    assert saved["company"]["name"] == "Acme"
    assert saved["practices"][0]["level"] == 2
    # company.updated проставляется автоматически при каждом сохранении (core.save_state)
    assert saved["company"]["updated"]


@pytest.mark.regress
def test_cyrillic_round_trips(api, clean_state):
    body = {"company": {"name": "Компания"}, "note": "ёж, объём, «кавычки» — юникод без потерь"}
    api.put_state(body)

    saved = api.get_state().json()
    assert saved["company"]["name"] == "Компания"
    assert saved["note"] == "ёж, объём, «кавычки» — юникод без потерь"


@pytest.mark.regress
def test_put_non_dict_body_is_rejected(api, clean_state):
    resp = api.client.put("/api/state", json=[1, 2, 3])
    assert resp.status_code == 400


@pytest.mark.regress
def test_put_malformed_json_is_rejected(api, clean_state):
    resp = api.client.put("/api/state", data=b"{not valid json",
                           headers={"Content-Type": "application/json"})
    assert resp.status_code == 400


@pytest.mark.regress
def test_put_body_too_large_is_rejected(api, clean_state):
    huge = {"note": "x" * (9 * 1024 * 1024)}  # больше MAX_STATE_BYTES = 8 МБ (pult/server.py)
    resp = api.put_state(huge)
    assert resp.status_code == 413


@pytest.mark.regress
def test_get_yaml_reflects_saved_state(api, clean_state):
    api.put_state({"company": {"name": "YamlCheck"}})
    resp = api.get_yaml()
    assert resp.status_code == 200
    assert "YamlCheck" in resp.text


@pytest.mark.regress
def test_meta_reports_backend_and_file(api):
    resp = api.get_meta()
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("backend")
    assert data.get("file")


@pytest.mark.regress
def test_unknown_path_is_404(api):
    resp = api.client.get("/api/does-not-exist")
    assert resp.status_code == 404


@pytest.mark.regress
def test_second_save_creates_backup(api, clean_state, state_file):
    api.put_state({"company": {"name": "First"}})
    api.put_state({"company": {"name": "Second"}})

    bak = state_file.with_name(state_file.name + ".bak")
    assert bak.exists()
    assert "First" in bak.read_text(encoding="utf-8")
