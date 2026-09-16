"""
    Тесты CSRF-защиты: сверка заголовка Origin с Host (см. pult/server.py::_origin_ok)
"""

import pytest

from configuration import STAND


@pytest.mark.regress
def test_put_without_origin_is_allowed(api, clean_state):
    # requests по умолчанию не шлёт Origin — как curl и tools/import_tms.py
    resp = api.put_state({"company": {"name": "NoOrigin"}})
    assert resp.status_code == 200


@pytest.mark.regress
def test_put_with_matching_origin_is_allowed(api, clean_state):
    host, port = STAND["pult"]["host"], STAND["pult"]["port"]
    resp = api.client.put("/api/state", json={"company": {"name": "SameOrigin"}},
                           headers={"Origin": f"http://{host}:{port}"})
    assert resp.status_code == 200


@pytest.mark.regress
def test_put_with_foreign_origin_is_rejected(api, clean_state):
    resp = api.client.put("/api/state", json={"company": {"name": "Evil"}},
                           headers={"Origin": "http://evil.example"})
    assert resp.status_code == 403
    # состояние не должно было записаться поверх того, что уже было
    assert api.get_state().json().get("company", {}).get("name") != "Evil"
