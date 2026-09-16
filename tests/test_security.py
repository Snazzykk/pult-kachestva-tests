"""
    Тесты CSRF-защиты: сверка заголовка Origin с Host (см. pult/server.py::_origin_ok)
"""

import allure
import pytest

from configuration import STAND
from helpers.allure_helper.allure_assertion import assert_status_code, assert_true


@allure.title("PUT без заголовка Origin разрешён")
@pytest.mark.regress
def test_put_without_origin_is_allowed(api, clean_state):
    with allure.step("PUT без Origin — как curl и tools/import_tms.py"):
        # requests по умолчанию не шлёт Origin
        resp = api.put_state({"company": {"name": "NoOrigin"}})
        assert_status_code(resp, 200)


@allure.title("PUT с совпадающим Origin разрешён")
@pytest.mark.regress
def test_put_with_matching_origin_is_allowed(api, clean_state):
    host, port = STAND["pult"]["host"], STAND["pult"]["port"]
    with allure.step("PUT с Origin, совпадающим с Host сервера"):
        resp = api.client.put("/api/state", json={"company": {"name": "SameOrigin"}},
                               headers={"Origin": f"http://{host}:{port}"})
        assert_status_code(resp, 200)


@allure.title("PUT с чужим Origin отклоняется 403")
@pytest.mark.regress
def test_put_with_foreign_origin_is_rejected(api, clean_state):
    with allure.step("PUT с посторонним Origin"):
        resp = api.client.put("/api/state", json={"company": {"name": "Evil"}},
                               headers={"Origin": "http://evil.example"})
        assert_status_code(resp, 403)

    with allure.step("Проверить, что состояние не перезаписалось"):
        name = api.get_state().json().get("company", {}).get("name")
        assert_true(name != "Evil", "отклонённая запись не попала в состояние")
