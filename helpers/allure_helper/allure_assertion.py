"""
    Методы для работы с утверждениями allure — по образцу референс-проекта:
    каждая проверка сама оборачивается в allure.step и прикладывает
    ожидаемое/фактическое значение, а не остаётся голым assert без следа
    в отчёте.
"""

import pprint

import allure
from allure import attachment_type as at


def allure_text(title="attach", message=""):
    """
        Аттач сообщения типа "text/plain"
    """
    allure.attach(str(message), str(title), at.TEXT)


def assert_status_code(response, expected, msg=""):
    """
        Проверка кода ответа — самая частая проверка в этих тестах
    """
    with allure.step(f"Проверка кода ответа: ожидали {expected}" + (f" — {msg}" if msg else "")):
        allure_text("URL", getattr(response, "url", ""))
        allure_text("Фактический код", response.status_code)
        try:
            allure_text("Тело ответа", pprint.pformat(response.json()))
        except ValueError:
            allure_text("Тело ответа", response.text)
        assert response.status_code == expected, \
            msg or f"код ответа {response.status_code}, ожидали {expected}"


def assert_true(value, msg=""):
    """
        Проверка: value истинно
    """
    with allure.step(f"Проверка: {msg}"):
        allure_text("значение", value)
        assert value, msg


def assert_equals(actual, expected, msg=""):
    """
        Проверка: actual == expected (json/dict/list/скаляр)
    """
    with allure.step(f"Проверка: {msg}"):
        allure_text("ожидаемое значение", pprint.pformat(expected))
        allure_text("фактическое значение", pprint.pformat(actual))
        assert actual == expected, msg


def assert_contains(container, item, msg=""):
    """
        Проверка: item содержится в container
    """
    with allure.step(f"Проверка: {msg}"):
        allure_text("контейнер", container)
        allure_text("искомый элемент", item)
        assert item in container, msg


def assert_not_none(value, msg=""):
    """
        Проверка: value не None (и не пусто)
    """
    with allure.step(f"Проверка: {msg}"):
        allure_text("значение", value)
        assert value, msg
