"""
    Класс и методы для работы с API «Пульта качества» —
    обёртка над сырыми endpoint's, чтобы тесты не трогали их напрямую.
"""

from endpoints.pult_endpoints import PultEndpoints
from helpers.api_helper import ApiClient


class PultAPI:
    """
        Фасад над JSON API «Пульта качества»
    """

    def __init__(self, stand_config):
        api_config = stand_config["pult"]
        self.client = ApiClient(api_config)

    # State

    def get_state(self):
        """
            Текущее состояние проекта
        """
        return self.client.get(PultEndpoints.GET_STATE)

    def put_state(self, body):
        """
            Сохранить состояние (полная перезапись файла, не merge)
        """
        return self.client.put(PultEndpoints.PUT_STATE, json=body)

    # Yaml / Meta

    def get_yaml(self):
        """
            Сырой текст quality-state.yml
        """
        return self.client.get(PultEndpoints.GET_YAML)

    def get_meta(self):
        """
            Бэкенд чтения YAML (PyYAML/yamlio) и путь к файлу состояния
        """
        return self.client.get(PultEndpoints.GET_META)

    # Импорт

    def import_openapi(self, url=None, text=None):
        """
            Разобрать OpenAPI/Swagger-спеку по ссылке или по тексту (JSON/YAML)
        """
        return self.client.post(PultEndpoints.POST_OPENAPI, json={"url": url, "text": text})

    def import_openapi_file(self, raw_bytes, content_type="application/octet-stream"):
        """
            Разобрать OpenAPI/Swagger-спеку из файла (сырые байты, не JSON-обёртка)
        """
        return self.client.post(PultEndpoints.POST_OPENAPI, data=raw_bytes,
                                 headers={"Content-Type": content_type})

    def import_tms(self, raw_bytes, content_type="text/csv"):
        """
            Разобрать CSV/XLSX-выгрузку кейсов из TMS (сырые байты файла)
        """
        return self.client.post(PultEndpoints.POST_TMS, data=raw_bytes,
                                 headers={"Content-Type": content_type})
