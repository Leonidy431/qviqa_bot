# qviqa_bot backend — Python-порт фриланс-агрегатора

Порт Telegram-бота «FreelanceAgregatorRU», изначально собранного в
BrowserAutomationStudio (Windows-only, см. `../BAS_STUDIO.md`), на переносимый
Python-бекенд: без браузера, поднимается в Docker на любом Linux.

## Что умеет

- **Парсинг источников** по HTTP/RSS/API (без браузера):

  | Источник | Способ | Статус |
  |---|---|---|
  | fl_ru | RSS `fl.ru/rss/all.xml` | ✅ |
  | habr_freelance | RSS (заменяет freelansim.ru) | ✅ |
  | weblancer | RSS | ✅ |
  | freelance_ru | RSS | ✅ |
  | freelancehunt | API v2 (нужен токен) | ✅ |
  | freelancer_com | публичный API | ✅ |
  | youdo | JSON API | ✅ |
  | kwork | HTML (`window.stateData`) | ✅ |
  | telegram | публичные страницы `t.me/s/<канал>` | ✅ |

  Источники оригинала, которые НЕ портированы (см. `GET /api/sources` →
  `dead_sources`): freten.ru, 1clancer.ru, superlance.pro, fl-ru.com — закрыты;
  freelansim.ru — переехал на habr; vk.com / tgstat.ru / telemetr.me — требовали
  браузер с антидетектом и заменены прямым чтением `t.me/s/`; kadrof.ru,
  freelancejob.ru — нет машиночитаемой ленты.

  > ⚠️ Форматы лент проверены на записанных фикстурах (`tests/fixtures/`):
  > из среды разработки внешние фриланс-сайты недоступны (egress-политика).
  > После деплоя в прод прогоните `GET /api/parse/<источник>` по каждому —
  > если сайт сменил формат, правится один парсер в `app/parsers/`.

- **Telegram-бот** (long-polling, сырой Bot API как в оригинале):
  регистрация с тестовым периодом, ключевые слова, вкл/выкл источников,
  пауза, профиль, админ-команды `/grant` и `/stats`.
- **Подписка**: тестовый период + начисление дней. QIWI P2P (оплата в
  оригинале) закрыт в 2024 — оплата через админа (`app/payments.py`),
  интерфейс готов к подключению другого провайдера.
- **Dev-сервер**: `/health`, `/api/sources`, `/api/parse/{source}`,
  `POST /api/run-cycle`, `GET /api/stream?keywords=python,бот` — живой
  NDJSON-поток заказов, отфильтрованных по ключевым словам (по одной строке
  JSON на заказ, источники опрашиваются параллельно).
- **Фронтенд** (`app/frontend/`) — статичная SPA без сборки и бэкенд-рендера,
  архитектурно как приложение на Firebase Hosting: весь JS ходит прямо в
  REST/NDJSON API браузером (`fetch` + `ReadableStream`), `appConfig` в
  `app.js` играет роль `firebaseConfig`. Раздаётся тем же aiohttp-сервером
  на `/` и `/assets/*`; чтобы задеплоить на реальный Firebase Hosting —
  `firebase init hosting` с public-каталогом `app/frontend`, затем
  `firebase deploy` (без каких-либо правок кода).

## Запуск

### Docker (прод)

```bash
cd backend
cp .env.example .env      # заполнить BOT_TOKEN и ADMIN_ID
# 1. базовый образ (обходит недоступность registry; при доступном Docker Hub
#    можно заменить FROM на python:3.12-slim и пропустить этот шаг)
bash docker/build_base_image.sh
# 2. wheels для офлайн-установки зависимостей
pip download -r requirements.txt -d docker/wheels \
    --only-binary=:all: --python-version 3.12 \
    --platform manylinux2014_x86_64 --implementation cp
# 3. сборка и запуск
docker compose up -d --build
curl localhost:8000/health
```

### Локально (dev, с mock-источниками и mock-Telegram)

`api.telegram.org` и реальные фриланс-сайты недоступны из некоторых сред
разработки (egress-политика песочницы, например) — `dev_run.py` поднимает
локальные заглушки для обоих, чтобы весь пайплайн (парсинг → фильтр по
ключевым словам → доставка боту) проверялся по-настоящему через HTTP.

```bash
cd backend
python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python dev_run.py
# mock-источники :9001, mock-Telegram :9002, бекенд :8000
```

```bash
# парсинг одного источника
curl "localhost:8000/api/parse/kwork?limit=2"

# живой поток заказов по ключевым словам (NDJSON, по строке на заказ)
curl "localhost:8000/api/stream?keywords=python"

# имитируем реального пользователя, который пишет боту /start
curl -X POST localhost:9002/debug/push -H 'content-type: application/json' \
     -d '{"chat_id": 777, "text": "/start", "username": "demo"}'
sleep 2   # бот успевает обработать через long-polling
curl localhost:9002/debug/sent | python3 -m json.tool   # что бот реально ответил

# фронтенд
open http://localhost:8000/       # или curl -s localhost:8000/
```

### Тесты

```bash
.venv/bin/python -m pytest tests/ --cov=app
# 116 passed, покрытие 100% (statements + branches)
```

## Структура

```
backend/
├── app/
│   ├── parsers/          # base (Item, RSS), rss_sources, api_sources, html_sources
│   ├── bot.py            # команды и меню (порт commands_check и др.)
│   ├── scheduler.py      # цикл парсинг→фильтр→рассылка (порт parse_sites/send_project)
│   ├── matcher.py        # ключевые слова, хэштеги (порт words_check/hashtag_format)
│   ├── db.py             # SQLite: users/keywords/user_sites/sent
│   ├── telegram.py       # сырой Bot API клиент
│   ├── payments.py       # подписка (QIWI мёртв — начисление через админа)
│   ├── fetcher.py        # HTTP с ретраями 2/4/8/16с
│   ├── server.py         # dev/ops эндпоинты + NDJSON-стрим + фронтенд
│   ├── frontend/         # статичная SPA (index.html/app.js/style.css), Firebase-Hosting-style
│   ├── mock_sources.py   # сервер фикстур источников для dev
│   ├── mock_telegram.py  # заглушка Telegram Bot API для dev (реальный недоступен из песочницы)
│   └── main.py           # входная точка
├── tests/                # 116 тестов, фикстуры реальных форматов лент + live-интеграция
├── docker/build_base_image.sh   # базовый образ без registry
├── Dockerfile, docker-compose.yml
└── .env.example
```

## Безопасность

Файлы `настройки 15.11.22.xml` и dump-файлы в корне репозитория содержат
**живые секреты** (токен бота, прокси-креды, пароль superlance, ключ QIWI).
Отзовите их и уберите файлы из истории git. Бекенд секреты в код не
зашивает — только `.env` (в git не попадает).
