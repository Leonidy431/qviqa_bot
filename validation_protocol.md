# validation_protocol.md — протокол самопроверки

**Жёсткое правило**: ни один пункт бэклога/ТЗ не считается закрытым, пока
все применимые шаги ниже не прошли. Незакрытый шаг = запись в
`state_journal.md` → «Нерешённые проблемы», не в «Выполнено». Соответствует
`.clauderc` правилам 26 (coverage 95%+) и 89 (стайлгайд), и
AUTONOMY_PROTOCOL.md §0 (Валидационный протокол, часть 1).

Все команды запускаются из `backend/`, если не указано иное.

---

## 1. Тесты и покрытие (обязательно всегда)

```bash
.venv/bin/python -m pytest tests/ -q --cov=app --cov-report=term
```

**Критерий прохождения**: 0 failed; покрытие ≥ 95% и по statements, и по
branches (`--cov-branch` включён в `pyproject.toml`). Текущий факт: 100%,
116 тестов — не давать покрытию упасть ниже 95% ни при каком коммите.

Каждый новый баг/слепая зона сначала получает **свой** unit-тест,
воспроизводящий проблему, и только потом — исправление (TDD, AUTONOMY_PROTOCOL
§3 п.2).

## 2. Стиль / статический анализ (обязательно всегда)

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```

**Критерий прохождения**: `All checks passed!` на обеих командах. Если
`ruff check` находит проблему сложности (C901) — не подавлять правило,
рефакторить (см. пример: `Bot._dispatch` → таблица диспетчеризации вместо
`if/elif`-цепочки).

## 3. Секреты (обязательно при изменении любого `*.md`, `.env.example`, конфигов)

Перед коммитом **любого** файла документации/конфига — проверить staged
diff на признаки реального секрета, а не только на имя переменной:

```bash
git diff --cached | grep -inE 'token|secret|password|api[_-]?key'
```

Каждое срабатывание разобрать вручную: `BOT_TOKEN=` (имя переменной, без
значения) — ок; `BOT_TOKEN=1234567:AA...` (реальное значение после `=`) —
стоп, не коммитить. При работе с уже известными утёкшими секретами (см.
`SECRETS_REVOCATION.md`) — дополнительно прогнать точные строки:

```bash
git diff --cached | grep -F "<строка секрета>"   # должно быть пусто
```

## 4. Контекстная карта (обязательно, если менялись top-level import'ы)

```bash
python3 tools/gen_context_map.py --write
git diff --stat context_map.json
```

Если diff не пустой — закоммитить обновлённый `context_map.json` вместе с
изменением кода, а не отдельным «забыл» коммитом.

## 5. Docker (обязательно перед объявлением готовности к деплою)

```bash
cd backend
docker build -t qviqa-bot:latest .
cp .env.example .env   # если нет
docker compose up -d --force-recreate
# ждать: docker inspect -f '{{.State.Health.Status}}' backend-bot-1  == healthy
curl -sf localhost:8000/health
curl -sf -o /dev/null -w '%{http_code}\n' localhost:8000/
docker compose down
rm -f .env
```

**Критерий прохождения**: health status `healthy`, `/health` возвращает
`200 {"status": "ok", ...}`, `/` возвращает `200`. Сборка не должна
обращаться ни к одному container registry (см. `docker/build_base_image.sh`
— обход недоступности Docker Hub/ghcr/ECR из некоторых сред).

## 6. State journal (обязательно в конце итерации)

Добавить блок в `state_journal.md` **после**, а не вместо, прохождения
пп. 1–5 — см. формат записи в самом файле.

---

## Быстрый прогон (все обязательные пункты разом)

```bash
cd backend && \
  .venv/bin/pytest tests/ -q --cov=app --cov-report=term && \
  .venv/bin/ruff check . && \
  .venv/bin/ruff format --check . && \
  echo "PASS: tests + lint" || echo "FAIL — не переходить к следующей задаче"
```

Docker и context_map — по условиям выше (не на каждый мелкий diff, но
обязательны перед мержем/деплоем).
