"""
    Класс для работы с методами JSON API «Пульта качества»
"""

import json

import allure
from requests import Session


class ApiClient:
    """
        Обёртка над requests.Session с логированием запросов/ответов в Allure —
        тесты обращаются к именованным методам, а не к сырым requests.*
    """

    def __init__(self, app_config):
        self.host = app_config["host"]
        self.port = app_config["port"]
        self.base_url = f"http://{self.host}:{self.port}"

        self.session = Session()

    def _request(self, method, endpoint, headers=None, **kwargs):
        """
            Универсальный метод для выполнения запросов с логированием в allure
        """
        url = f"{self.base_url}{endpoint}"
        response = self.session.request(method.upper(), url, headers=headers, timeout=30, **kwargs)
        self._log_to_allure(method, url, kwargs, response)
        return response

    def get(self, endpoint, headers=None, **kwargs):
        return self._request("GET", endpoint, headers=headers, **kwargs)

    def post(self, endpoint, headers=None, **kwargs):
        return self._request("POST", endpoint, headers=headers, **kwargs)

    def put(self, endpoint, headers=None, **kwargs):
        return self._request("PUT", endpoint, headers=headers, **kwargs)

    @staticmethod
    def _log_to_allure(method, url, request_kwargs, response):
        """
            Логирование запроса и ответа в Allure (с поддержкой кириллицы)
        """

        def _attach(data, name):
            content = (json.dumps(data, ensure_ascii=False, indent=2, default=str)
                       if isinstance(data, (dict, list)) else str(data))
            allure.attach(content, name, attachment_type=allure.attachment_type.TEXT)

        with allure.step(f"{method.upper()} [{response.status_code}] {url}"):
            if request_kwargs.get("json") is not None:
                _attach(request_kwargs["json"], "Request Body")
            if request_kwargs.get("data") is not None:
                _attach(request_kwargs["data"], "Request Data")
            allure.attach(str(response.status_code), "Status Code", attachment_type=allure.attachment_type.TEXT)
            try:
                _attach(response.json(), "Response Body")
            except ValueError:
                _attach(response.text, "Response Body")
