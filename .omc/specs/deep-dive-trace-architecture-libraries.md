# Deep Dive Trace: architecture-libraries-selection

## Observed Result
Текущая архитектура `Path-Of-Exile-2-RPC` — single-file `main.py` (~330 LOC) с регексным парсингом `Client.txt`, polling-tail-loop (`time.sleep(5)`), ручной retry-loop для Discord IPC, JSON-локациями и enum-классификацией. Зависимости: `psutil`, `pypresence`. Тестов нет. Сборка: PyInstaller `--onefile` через CI с path-filter `paths: ['main.py']`. Пользователь хочет архитектурные рекомендации и набор библиотек/фреймворков по best-practices через Context7.

## Ranked Hypotheses
| Rank | Lane | Confidence | Evidence Strength | Why it leads |
|------|------|------------|-------------------|--------------|
| 1 | Lane 3 (Library landscape via Context7) | High | Strong (Context7 docs покрывают все нужные либы) | Прямой отклик на запрос пользователя — он сам попросил "через context7 mcp" |
| 2 | Lane 1 (Code structure) | High | Strong (main.py прочитан целиком) | Структура очевидна: 7 функций + 2 enum'а, нет границ доменов, glob state `rpc` |
| 3 | Lane 2 (Distribution constraints) | Medium | Strong (build.yml + CLAUDE.md) | Ограничения известны точно, но они не "причина", а "контейнер" решения |

## Evidence Summary by Hypothesis

### Lane 1 — Code structure (current architecture)
- **Глобальное состояние**: `rpc` создаётся в `__main__` и читается из `update_rpc()` через free-name lookup (line 263). Скрытая зависимость.
- **Coupling**: `monitor_log()` (lines 277–325) делает 4 вещи: discovery, initial state, tail loop, dispatch. Inline-дубликат форматирования `details` (lines 285–293 ≈ 254–262).
- **Domain boundaries** (естественные):
  1. **Game discovery** — `find_game_log()` ищет `PathOfExileSteam.exe`. Hardcoded: только Steam-build (см. open work в README).
  2. **Log streaming** — open + seek-EOF + `readlines()` + `sleep(5)`. Polling 5s = заметная задержка.
  3. **Parsing** — 2 регекса (`regex_level`, `regex_instance`). Нормальная инкапсуляция.
  4. **Domain mapping** — `CharacterClass`/`ClassAscendency` enum'ы + двусторонний lookup. Чистый VO/lookup.
  5. **Location resolution** — `determine_location()` + JSON cache + remote fallback. Смешан I/O и лукап.
  6. **Presence push** — `rpc_connect()` + `update_rpc()`. Manual retry: `time.sleep(2**retries)`.
- **Anti-patterns**:
  - `find_last_level_up()` называется как find_last но обрабатывает одну строку.
  - `current_status` — словарь-state-bag вместо value-object.
  - `random_status` — UI-flavour смешан с domain-state.
  - Нет separation of concerns между orchestration и I/O.

### Lane 2 — Distribution constraints
- **CI path filter**: `paths: ['main.py']` — изменения в других файлах НЕ триггерят сборку. Если разделить на модули, CI должен меняться синхронно.
- **PyInstaller `--onefile --name PathOfExile2DiscordRPC main.py`** — нет spec-файла, нет `--add-data`, поэтому `locations.json` НЕ упакован в .exe (он подгружается с GitHub при первом запуске).
- **Hidden imports**: `psutil` и `pypresence` обычно подхватываются автоматически, но при добавлении watchdog/aiofiles/pydantic потребуется проверить.
- **Альтернативы packaging**: spec-файл (PyInstaller), Briefcase (BeeWare), Nuitka (компиляция в C). Все совместимы с однофайловой выдачей.
- **Перевод на `src/` layout совместим** при условии: добавить `pyinstaller PathOfExile2DiscordRPC.spec` в CI и расширить path-filter (`paths: ['src/**', 'PathOfExile2DiscordRPC.spec']`).

### Lane 3 — Library landscape via Context7

| Библиотека | ID | Версия | Применение | Score |
|------------|----|----|-----------|-------|
| **watchdog** | `/gorakhargosh/watchdog` | latest | Замена `sleep+readlines` на `Observer + FileModifiedEvent` (event-driven tail) | 81.3 |
| **tenacity** | `/jd/tenacity` | latest | Замена ручного `2**retries` на `@retry(wait=wait_exponential, stop=stop_after_attempt, before_sleep=before_sleep_log)` | 86.4 |
| **pydantic** | `/pydantic/pydantic` | latest | Value-objects: `LevelInfo`, `InstanceInfo`, `LocationCatalog`. Type-safe immutable models | 83.3 |
| **pydantic-settings** | `/pydantic/pydantic-settings` | latest | `BaseSettings` + `TomlConfigSettingsSource` — пользовательский `config.toml` (client_id, poll_interval, log_path override) | 86.8 |
| **pypresence** | `/websites/qwertyquerty.../pypresence` | current | Уже используется. Альтернатива `AioPresence` для async. Минимальный update interval — 15 сек | 61.5 |
| **PyInstaller** | `/pyinstaller/pyinstaller` | v6.14 | Перейти на `.spec`-файл с `--add-data locations.json:.` и `--hidden-import` для новых либ | 83.1 |
| **structlog** | `/hynek/structlog` | latest | Замена `logging.basicConfig` — `ConsoleRenderer` для dev / `JSONRenderer` для prod, `bind_contextvars` для контекста | 92.6 |
| **typer** | `/fastapi/typer` | 0.21 | CLI-флаги: `--config`, `--log-level`, `--dry-run`, `--once` | 91.0 |

**Ключевые findings из docs:**
- `watchdog`: на Windows работает через `ReadDirectoryChangesW` API — нативно, без polling. `Observer.schedule(handler, path, recursive=False)` + `on_modified` хук, читать дельту через сохранённый offset.
- `tenacity`: `@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=2, max=32), retry=retry_if_exception_type((ConnectionError, OSError)), before_sleep=before_sleep_log(logger, logging.WARNING))` ровно покрывает текущий retry pattern и логирует попытки.
- `pydantic-settings`: TOML-config + env-overrides + CLI defaults — single source of truth.
- `pypresence`: текущее использование корректно; для будущей AFK-фичи имеет смысл перейти на `AioPresence` (asyncio).
- `structlog`: `ConsoleRenderer` для dev / `JSONRenderer` для prod; `contextvars.bind_contextvars(username=..., character_class=...)` даёт rich-контекст без передачи через каждый вызов.
- `PyInstaller`: `.spec`-файл позволяет указать `datas=[('locations.json', '.')]` — `locations.json` будет внутри .exe и не нужен сетевой fallback (либо оставить как fallback для свежих версий).

## Evidence Against / Missing Evidence

- **Lane 1**: Refactoring единственного файла увеличивает нагрузку поддержки соло-разработчика; CI потребует изменений. Простота текущего main.py — это feature, не bug.
- **Lane 2**: Migration на `src/` layout — необратимое решение для CI/release pipeline. Возможен compromise: package layout + одноточечный entry, который PyInstaller всё равно собирает в один .exe.
- **Lane 3**: Каждая новая зависимость увеличивает размер .exe (PyInstaller bundle растёт ~2-5 MB на крупную либу). Watchdog нативно тянет `pywin32`-style hooks. Pydantic — самая тяжёлая по размеру (но даёт максимум value).

## Per-Lane Critical Unknowns

- **Lane 1 (Code structure)**: Готов ли пользователь перейти с single-file на multi-module package layout, или важнее сохранить простоту `main.py` с минимальными improvements внутри одного файла?
- **Lane 2 (Distribution)**: Готов ли поменять CI path-filter и перейти на `.spec`-файл (упаковать `locations.json` в .exe), или сохранить текущий pipeline?
- **Lane 3 (Libraries)**: Какой набор библиотек приоритетен — full stack (watchdog + tenacity + pydantic + structlog + typer) или минималистичный bundle (только tenacity + pydantic-settings)?

## Rebuttal Round

- **Best rebuttal to leader (Lane 3)**: "Зачем full library stack для тулзы на 330 строк? Текущий код работает — over-engineering убьёт maintainability."
- **Why leader holds**: Пользователь явно попросил best-practices через Context7. Текущий код имеет реальные слабые места: 5-секундный polling вместо event-driven, ручной retry без логирования, scattered state. Это не cosmetic — это влияет на user experience (задержка обновления presence) и debuggability.
- **Why leader could fail**: Если приоритет — "не ломать", тогда решение = consolidation внутри одного файла + только 2 либы (tenacity + pydantic-settings).

## Convergence / Separation Notes

Lanes 1, 2, 3 — НЕ независимы. Любая существенная архитектурная перестройка (Lane 1) требует решения по distribution (Lane 2) и выбора либ (Lane 3). Ключевая развилка: **single-file evolution vs package-layout refactor**. Эта развилка определяет всё остальное.

## Most Likely Explanation

Текущая архитектура — pragmatic single-file MVP, который вырос до точки, где простые improvements (event-driven tail, structured retry, typed models) дали бы значительный выигрыш по reliability/observability/testability **без** обязательного ухода от single-file shape. Best-practice путь: **layered single-file** (или minimal package) + **5 целевых либ** (watchdog, tenacity, pydantic-settings, structlog, pytest) + **PyInstaller spec-file**.

## Critical Unknown

**Готов ли пользователь принять компромисс между "минимальный change footprint" и "максимальный outcome"?** От этого зависит выбор: keep single-file vs migrate to `src/` package, full library stack vs minimal additions.

## Recommended Discriminating Probe

Один вопрос пользователю с 3 вариантами архитектурного направления:
1. **Conservative** — keep single-file, добавить только tenacity + pydantic-settings.
2. **Balanced (рекомендуется)** — `src/poe2_rpc/` package с 5 модулями (parsers, presence, settings, locations, app) + 5 либ (watchdog, tenacity, pydantic, structlog, typer) + PyInstaller spec.
3. **Aggressive (DDD)** — bounded contexts (game, presence, config), pydantic VO, async event bus, full DI, 100% type coverage.
