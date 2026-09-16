"""
    Модуль с endpoint's JSON API «Пульта качества» [core]

    Список и поведение — см. докстринг server.py в репозитории pult-kachestva
    (pult/server.py).
"""


class PultEndpoints:
    """
        Endpoint's сервера «Пульта качества»:
        -Состояние проекта (State)
        -Сырой YAML (Yaml)
        -Метаданные бэкенда (Meta)
        -Импорт из OpenAPI/Swagger (OpenAPI)
        -Импорт кейсов из TMS (Tms)
    """

    # State
    GET_STATE = "/api/state"
    PUT_STATE = "/api/state"
    # Yaml
    GET_YAML = "/api/yaml"
    # Meta
    GET_META = "/api/meta"
    # Импорт
    POST_OPENAPI = "/api/openapi"
    POST_TMS = "/api/tms"
