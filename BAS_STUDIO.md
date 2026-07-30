# BrowserAutomationStudio (BAS) — что это и как туда завести Claude

## В чём был сделан этот бот

Файлы `настройки 15.11.22.xml`, `freelancemonitor_БОТ_59_Леонид_RU.xml` и архив
`FreelanceAgregatorRU.1.zip` — это проект **BrowserAutomationStudio (BAS)** от
**BabloSoft** (bablosoft.com). Признаки:

- корневой тег XML — `<BrowserAutomationStudioProject>`;
- в архиве лежит рантайм BAS: `FreelanceAgregatorRU.exe`,
  `RemoteExecuteScriptSilent.exe`, Qt5-библиотеки (`Qt5Core.dll`, `Qt5WebEngine*`),
  `data/project.xml` с `<Remote ScriptName="FreelanceAgregatorRU" Mode="1"/>`;
- скрипт внутри — характерный для BAS транспилированный JavaScript с
  `section_start(...)!`, `_call_function(...)`, ресурсами `{{telegram_urls|notreuse}}`
  и закодированными в base64 блоками визуального конструктора (`/*Dat:...*/`).

BAS — это не «вайб-кодинг» в современном смысле (AI-генерация кода), а
**визуальный низкокодовый конструктор браузерной автоматизации**: логика
собирается мышкой из кубиков-действий (клик, HTTP-запрос, парсинг, цикл), а
BAS генерирует из них исполняемый скрипт. Работает **только под Windows**
(Qt + встроенный Chromium), поэтому его exe нельзя поднять в Linux-докере.

## Подписка BAS (актуально на середину 2026, проверяйте на bablosoft.com)

| Тариф | Что даёт | Ориентировочная цена |
|---|---|---|
| **Free** | Полный конструктор, компиляция своих ботов, до 1 потока в ScriptEngine, базовые функции | бесплатно |
| **Premium** | Многопоточность без ограничений, защита скриптов (обфускация/привязка), продажа скриптов через магазин BAS, приоритетная поддержка | ~$27–30 / мес |
| **FingerprintSwitcher** (опция) | Подмена отпечатков браузера (антидетект) — отдельная подписка BabloSoft | ~$29 / мес |

Точные цены смотрите на https://bablosoft.com (из этой песочницы сайт недоступен,
цифры даны по памяти и могут устареть). Оплата исторически принималась картой и
криптовалютой. Лицензия привязывается к аккаунту BabloSoft, вход из BAS.

## Как завести Claude в BAS

BAS не имеет нативного плагина Anthropic, но в нём есть действие
**«HTTP-клиент → POST»** и блок **«Выполнить код» (JavaScript)** — этого
достаточно, чтобы вызывать Claude API напрямую.

### 1. Прямой вызов Messages API из BAS (HTTP-запрос)

Действие «HTTP Client → POST» со следующими параметрами:

- **URL**: `https://api.anthropic.com/v1/messages`
- **Заголовки**:
  ```
  x-api-key: ВАШ_ANTHROPIC_API_KEY
  anthropic-version: 2023-06-01
  content-type: application/json
  ```
- **Тело** (POST data, raw JSON):
  ```json
  {
    "model": "claude-opus-5",
    "max_tokens": 1024,
    "system": "Ты классификатор фриланс-заказов. Отвечай одним словом: категория заказа.",
    "messages": [
      {"role": "user", "content": "{{PROJECT_TEXT}}"}
    ]
  }
  ```
  где `{{PROJECT_TEXT}}` — переменная BAS с текстом спарсенного заказа.

Ответ приходит в JSON; текст лежит в `content[0].text` — в BAS достаточно
действия «Парсить JSON» / `JSON.parse` в блоке кода:

```javascript
var resp = JSON.parse(VAR_HTTP_RESPONSE);
if (resp.stop_reason === "refusal") {
    VAR_AI_ANSWER = "";
} else {
    VAR_AI_ANSWER = resp.content[0].text;
}
```

API-ключ берётся на https://platform.claude.com → API Keys. Ключ храните в
настройках проекта BAS (FixedString с Visible=0), а не в коде.

Так в старый бот добавляются AI-фичи без переписывания: классификация заказов
по ключевым словам → семантическая классификация, автогенерация откликов,
фильтрация спама в телеграм-каналах.

### 2. Правильный путь: AI-логика в бекенде, BAS — только браузер

Прямые вызовы из BAS ограничены (нет стриминга, неудобно вести историю диалога,
ключ лежит на Windows-машине). Практичнее держать AI-логику в Python-бекенде
(см. `backend/` в этом репозитории) и дать BAS один простой эндпоинт:

```
BAS (Windows, браузер) ──POST /api/classify──▶ backend (Docker, Python)
                                                └──▶ Anthropic API (claude-opus-5)
```

В бекенде это ~20 строк на официальном SDK:

```python
import anthropic

client = anthropic.Anthropic()  # ключ из ANTHROPIC_API_KEY

def classify(text: str) -> str:
    resp = client.messages.create(
        model="claude-opus-5",
        max_tokens=64,
        system="Классифицируй фриланс-заказ одним словом.",
        messages=[{"role": "user", "content": text}],
    )
    if resp.stop_reason == "refusal":
        return ""
    return next(b.text for b in resp.content if b.type == "text")
```

### 3. Замена BAS целиком (этот репозиторий)

Каталог `backend/` — портированный на Python бекенд этого бота: парсеры
источников работают по HTTP/RSS/API без браузера, Telegram — через Bot API
long-polling, всё поднимается в Docker на любом Linux. BAS остаётся нужен
только для источников, требующих полноценного браузера с антидетектом
(vk.com, tgstat.ru, telemetr.me) — их в порте заменяет прямое чтение
публичных страниц `t.me/s/<канал>`.

## Итого

- **Инструмент**: BrowserAutomationStudio (BabloSoft), Windows-only визуальный конструктор.
- **Подписка**: Free достаточно для запуска; Premium (~$27/мес) — для многопоточности и защиты скриптов.
- **Claude в BAS**: да, через HTTP POST на `api.anthropic.com/v1/messages` (пример выше), но лучше выносить AI-логику в бекенд и дергать её из BAS одним запросом.
