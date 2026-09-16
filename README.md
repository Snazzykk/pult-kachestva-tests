# pult-kachestva-tests

Автотесты JSON API «Пульта качества» — отдельный репозиторий, отдельно от кода
продукта ([pult-kachestva](https://github.com/Snazzykk/pult-kachestva)). Обычная
для компаний схема: у разработчиков — свой репозиторий, у тестировщиков — свой,
со своей историей изменений и своим CI.

У «Пульта качества» нет постоянно задеплоенного стенда (это локальный инструмент) —
поэтому вместо похода по `preprod`/`prod` URL тесты сами поднимают
`python run.py` из репозитория `pult-kachestva` на время прогона, на отдельном
порту и scratch-файле состояния, и гасят его в конце. Реальные данные пользователя
(`data/quality-state.yml`) тесты никогда не трогают.

---

## Устройство (по образцу типового test-репозитория)

```
configuration.py     стенд: адрес/порт (STAND) + путь к репозиторию pult-kachestva
endpoints/
  pult_endpoints.py   сырые пути ручек API
helpers/
  api_helper.py        ApiClient — requests.Session + логирование в Allure
  pult_helper.py        PultAPI — фасад с именованными методами над endpoint's
conftest.py           фикстуры: поднять/погасить сервер, api, clean_state
tests/
  test_state_api.py     /api/state, /api/yaml, /api/meta
  test_security.py      CSRF (Origin vs Host)
  test_openapi_import.py  /api/openapi
  test_tms_import.py      /api/tms
scripts/
  send_telegram_notification.py   итоги прогона в Telegram (см. ниже, опционально)
```

## Запуск локально

Ожидается стандартный layout — `pult-kachestva` склонирован рядом, соседним
каталогом:

```
Users/you/pult-kachestva/
Users/you/pult-kachestva-tests/
```

```bash
python -m pip install -r requirements.txt
python -m pytest                 # весь набор
python -m pytest -m smoke        # только быстрый набор
python -m pytest -m regress      # набор для master (включает всё)
```

Если `pult-kachestva` лежит не рядом — укажи путь явно:

```bash
PULT_REPO_PATH=/путь/к/pult-kachestva python -m pytest
```

Полезные переменные окружения: `PULT_TEST_HOST` / `PULT_TEST_PORT` (по умолчанию
`127.0.0.1:7997`) — на каком порту поднимать сервер на время тестов.

**Параллельный запуск (`pytest-xdist -n auto`) сознательно не используется** —
каждый воркер поднимал бы свой собственный сервер отдельным процессом, и под
нагрузкой это давало нестабильные `ConnectionError`. Набор маленький (~1.5 секунды
последовательно) — выигрыш от параллели не окупает нестабильность.

## CI (GitHub Actions)

`.github/workflows/api-tests.yml`. Прямой связи с репозиторием `pult-kachestva`
нет (мердж туда не триггерит тесты здесь автоматически) — запуск:

- **вручную** — вкладка Actions → «Pult API tests» → Run workflow. Можно указать
  ветку/тег `pult-kachestva` для проверки (`pult_ref`, по умолчанию `master`) и
  фильтр по маркеру (`markers`: `smoke` / `regress`, пусто — весь набор);
- **по расписанию** — раз в сутки, полный набор на `master`.

Что делает workflow: чекаутит себя и `pult-kachestva` (в подкаталог), ставит
зависимости, гоняет `pytest` (с ретраями на упавших), собирает Allure-отчёт и
публикует его на GitHub Pages (`https://<user>.github.io/pult-kachestva-tests/`),
кладёт сырые результаты артефактом, и — если заданы секреты — шлёт итог в Telegram.

**Разовая настройка репозитория на GitHub** (руками, не через git push):
Settings → Pages → Source → **GitHub Actions** (иначе `actions/deploy-pages`
падает — Pages должен быть явно переключён на этот режим).

**Уведомление в Telegram — опционально.** Ничего не отправится, пока не заданы
секреты репозитория (Settings → Secrets and variables → Actions):

- `TELEGRAM_BOT_TOKEN` — токен бота (получить у [@BotFather](https://t.me/BotFather));
- `TELEGRAM_CHAT_ID` — куда слать (свой user id или id чата/канала).

Без них шаг отправки просто печатает в лог «секреты не заданы» и завершается
без ошибки — на прохождение тестов и остальной пайплайн не влияет.
