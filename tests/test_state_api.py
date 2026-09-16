"""
    Тесты JSON API: /api/state, /api/yaml, /api/meta
    (см. pult/server.py в репозитории pult-kachestva)
"""

import allure
import pytest

from helpers.allure_helper.allure_assertion import assert_equals, assert_not_none, assert_status_code, assert_true


@allure.title("Главная страница отдаёт HTML")
@pytest.mark.smoke
def test_index_page_ok(api):
    with allure.step("Запрос главной страницы"):
        resp = api.client.get("/")
        assert_status_code(resp, 200)
        assert_true("html" in resp.headers.get("Content-Type", "").lower(), "Content-Type содержит html")


@allure.title("Состояние после «Снять всё» — только company.updated")
@pytest.mark.smoke
def test_state_after_clean_is_effectively_empty(api, clean_state):
    with allure.step("Запрос текущего состояния после clean_state"):
        resp = api.get_state()
        assert_status_code(resp, 200)
        data = resp.json()

    with allure.step("Проверка: кроме company.updated ничего не осталось"):
        # save_state всегда проставляет company.updated — буквально {} не бывает
        # после хотя бы одного сохранения, но больше в состоянии ничего не должно быть
        assert_true(set(data.keys()) <= {"company"}, "верхний уровень — максимум company")
        assert_true(set(data.get("company", {}).keys()) <= {"updated"}, "внутри company — максимум updated")


@allure.title("Сохранение и чтение состояния — round-trip")
@pytest.mark.smoke
def test_save_and_read_back_state(api, clean_state):
    body = {"company": {"name": "Acme"}, "practices": [{"id": "process", "level": 2, "target": 3}]}

    with allure.step("Сохранить состояние (PUT /api/state)"):
        put_resp = api.put_state(body)
        assert_status_code(put_resp, 200)
        assert_true(put_resp.json()["ok"] is True, "ответ содержит ok: true")

    with allure.step("Прочитать состояние обратно (GET /api/state)"):
        saved = api.get_state().json()
        assert_equals(saved["company"]["name"], "Acme", "имя компании сохранилось")
        assert_equals(saved["practices"][0]["level"], 2, "уровень практики сохранился")
        # company.updated проставляется автоматически при каждом сохранении (core.save_state)
        assert_not_none(saved["company"]["updated"], "company.updated проставлен")


@allure.title("Кириллица и спецсимволы не теряются при сохранении")
@pytest.mark.regress
def test_cyrillic_round_trips(api, clean_state):
    body = {"company": {"name": "Компания"}, "note": "ёж, объём, «кавычки» — юникод без потерь"}

    with allure.step("Сохранить состояние с кириллицей и спецсимволами"):
        api.put_state(body)

    with allure.step("Прочитать обратно и сверить byte-в-byte"):
        saved = api.get_state().json()
        assert_equals(saved["company"]["name"], "Компания", "имя компании")
        assert_equals(saved["note"], "ёж, объём, «кавычки» — юникод без потерь", "произвольное поле с юникодом")


@allure.title("PUT не-объектом (списком) отклоняется 400")
@pytest.mark.regress
def test_put_non_dict_body_is_rejected(api, clean_state):
    with allure.step("Отправить список вместо объекта"):
        resp = api.client.put("/api/state", json=[1, 2, 3])
        assert_status_code(resp, 400)


@allure.title("PUT битым JSON отклоняется 400")
@pytest.mark.regress
def test_put_malformed_json_is_rejected(api, clean_state):
    with allure.step("Отправить синтаксически невалидный JSON"):
        resp = api.client.put("/api/state", data=b"{not valid json",
                               headers={"Content-Type": "application/json"})
        assert_status_code(resp, 400)


@allure.title("PUT тела больше 8 МБ отклоняется 413")
@pytest.mark.regress
def test_put_body_too_large_is_rejected(api, clean_state):
    with allure.step("Отправить тело > MAX_STATE_BYTES (8 МБ, см. pult/server.py)"):
        huge = {"note": "x" * (9 * 1024 * 1024)}
        resp = api.put_state(huge)
        assert_status_code(resp, 413)


@allure.title("Сырой YAML отражает сохранённое состояние")
@pytest.mark.regress
def test_get_yaml_reflects_saved_state(api, clean_state):
    with allure.step("Сохранить состояние"):
        api.put_state({"company": {"name": "YamlCheck"}})

    with allure.step("Запросить сырой YAML и найти в нём сохранённое значение"):
        resp = api.get_yaml()
        assert_status_code(resp, 200)
        assert_true("YamlCheck" in resp.text, "имя компании присутствует в тексте файла")


@allure.title("/api/meta отдаёт бэкенд чтения YAML и путь к файлу")
@pytest.mark.regress
def test_meta_reports_backend_and_file(api):
    with allure.step("Запросить /api/meta"):
        resp = api.get_meta()
        assert_status_code(resp, 200)
        data = resp.json()
        assert_not_none(data.get("backend"), "поле backend заполнено")
        assert_not_none(data.get("file"), "поле file заполнено")


@allure.title("Неизвестный путь — 404")
@pytest.mark.regress
def test_unknown_path_is_404(api):
    with allure.step("Запросить несуществующий путь"):
        resp = api.client.get("/api/does-not-exist")
        assert_status_code(resp, 404)


@allure.title("Второе сохранение создаёт .bak с предыдущей версией")
@pytest.mark.regress
def test_second_save_creates_backup(api, clean_state, state_file):
    with allure.step("Сохранить дважды подряд разные значения"):
        api.put_state({"company": {"name": "First"}})
        api.put_state({"company": {"name": "Second"}})

    with allure.step("Проверить .bak рядом с файлом состояния"):
        bak = state_file.with_name(state_file.name + ".bak")
        assert_true(bak.exists(), ".bak создан")
        assert_true("First" in bak.read_text(encoding="utf-8"), ".bak содержит предыдущую (первую) версию")
