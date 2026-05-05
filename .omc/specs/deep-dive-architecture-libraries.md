# Deep Dive Spec: architecture-libraries-selection

## Goal

Перевести `Path-Of-Exile-2-RPC` с single-file pragmatic-MVP на полную **DDD + hexagonal** архитектуру с async event-bus, типизированными доменными моделями и event-driven log streaming. Целевая платформа — Windows desktop (.exe через PyInstaller). Целевой стек — современная Python экосистема, выбранная по docs из Context7.

**Outcome качества (по 4 приоритетам):**
1. **Latency**: sub-second отклик на изменение лога (вместо 5s polling) — `watchdog.Observer` + `ReadDirectoryChangesW` API.
2. **Reliability**: structured retry с логированием попыток + auto-reconnect Discord IPC — `tenacity.retry`.
3. **Testability**: 100% доменного слоя покрыто `pytest` unit-тестами; адаптеры интеграционно — domain не зависит от инфраструктуры через `typing.Protocol`.
4. **Observability/Config**: `structlog` (JSON для prod, console для dev) + `pydantic-settings` (config.toml + env-overrides) + `typer` CLI.

## Constraints

- **OS target**: Windows (PoE2 client), но кодбаза должна линтиться и тестироваться на macOS/Linux (CI Ubuntu-runner для тестов, Windows-runner для сборки).
- **Single-binary distribution**: PyInstaller `--onefile` (не `--onedir`) — пользователь скачивает один `.exe` из GitHub Releases.
- **Локации в .exe**: `locations.json` упаковывается в bundle через `datas=[('locations.json', '.')]` в spec-файле и читается через `importlib.resources` — это единственный источник по умолчанию, без runtime fetch.
- **Discord update rate-limit**: `pypresence` минимальный интервал между `update()` — 15 секунд (по docs). Domain-события могут лететь чаще — application-слой батчит/throttle до 15s.
- **Backward compatibility артефакта**: имя выходного файла — `PathOfExile2DiscordRPC.exe` (релизные ассеты ссылаются на это имя).
- **Discord App ID**: `1315800372207419504` — продолжаем использовать.
- **Python version**: 3.11+ (для `typing.Self`, `tomllib` встроенный, structural pattern matching).

## Non-Goals

- Не поддерживаем не-Steam-клиент PoE2 в этом цикле (отдельная задача в README — `PathOfExileSteam.exe` остаётся единственным detection target; абстракция `GameDetector` подготовит будущее расширение).
- Не делаем cross-platform desktop UI / трей-иконку (отдельный epic).
- Не вводим IPC между процессами / web-API / телеметрию во внешний сервис.
- Не используем DI-фреймворк (`dependency-injector`, `punq`) — конструкторная инъекция руками в `cli.py`.

## Acceptance Criteria

- [ ] Пакет `src/poe2_rpc/` с явными слоями `domain/`, `application/`, `infrastructure/`, `cli.py`.
- [ ] Все доменные модели — `pydantic.BaseModel(model_config=ConfigDict(frozen=True))` либо `Enum`. Глобального изменяемого state в коде нет.
- [ ] Все ports описаны как `typing.Protocol` в `domain/ports.py`. Доменный слой не импортирует ничего из `infrastructure/`.
- [ ] `WatchdogLogStream` — event-driven, `Observer.schedule(handler, log_dir, recursive=False, event_filter=[FileModifiedEvent])`. На Windows используется `ReadDirectoryChangesW`-наблюдатель из `watchdog.observers`. Если стартовать observer не удалось, поднимается `RuntimeError` — приложение завершается с понятной ошибкой (никакого скрытого polling-режима).
- [ ] `PypresencePublisher` использует `AioPresence` (asyncio-вариант) и обёрнут в `@retry(stop=stop_after_attempt(5), wait=wait_exponential(min=2, max=32), retry=retry_if_exception_type((ConnectionError, OSError, InvalidPipe)), before_sleep=before_sleep_log(logger, logging.WARNING))`.
- [ ] `AppSettings(BaseSettings)` загружает в порядке приоритета: CLI-args → env (`POE2RPC_*`) → `~/.config/poe2-rpc/config.toml` → defaults.
- [ ] `structlog` сконфигурирован в `infrastructure/logging.py`: `ConsoleRenderer` если `sys.stderr.isatty()`, иначе `JSONRenderer`. Контекст (`username`, `character_class`, `area`) биндится через `structlog.contextvars.bind_contextvars`.
- [ ] CLI `typer`-приложение: `poe2-rpc run` (default), `poe2-rpc once` (одно обновление и выход), `poe2-rpc validate-config`, `poe2-rpc --version`.
- [ ] `pytest` + `pytest-asyncio`: unit-тесты на parsers (regex contracts из CLAUDE.md), classes, locations, throttle, event-bus. Integration-тесты на `WatchdogLogStream` через `tmp_path` fixture.
- [ ] `mypy --strict src/poe2_rpc` проходит без ошибок.
- [ ] `ruff check` + `ruff format` проходят.
- [ ] `pyinstaller PathOfExile2DiscordRPC.spec` собирает рабочий `.exe` идентичный по UX текущему.
- [ ] CI workflow обновлён: path-filter `['src/**', 'PathOfExile2DiscordRPC.spec', 'pyproject.toml', 'locations.json']`, добавлены jobs `lint`, `typecheck`, `test` перед `build`.
- [ ] Regex contracts (`regex_level`, `regex_instance` из CLAUDE.md) сохранены **верхально** — переехали в `infrastructure/parsing.py` как class-level constants, контракт парсинга не изменился.

## Assumptions Exposed

- Polling 5s заметен пользователю — переход на watchdog даст видимое улучшение. (Можно подтвердить только тестом на живом game-сессии.)
- Размер .exe вырастет на ~5-8 MB из-за pydantic + watchdog + structlog. Это приемлемо для desktop-tool.
- `pypresence.AioPresence` стабильно работает в production (используется широко, see Context7 snippet count = 88).
- `watchdog` на Windows корректно ловит модификации `Client.txt` который пишется самим PoE2 (некоторые игры мапят файл и не триггерят inotify-аналог — но `Client.txt` пишется обычным append'ом по логам issue tracker watchdog).
- CI Windows-runner справляется с PyInstaller сборкой за разумное время (<5 минут).

## Technical Context

### Bounded Contexts (DDD)

```
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│  Game Context    │  │ Parsing Context  │  │ Presence Context │
│                  │  │                  │  │                  │
│ - GameProcess    │  │ - LogLine        │  │ - PresenceState  │
│ - GameLogPath    │──│ - LevelInfo      │──│ - DisplayDetails │
│ - DetectionEvent │  │ - InstanceInfo   │  │ - Throttle       │
└──────────────────┘  └──────────────────┘  └──────────────────┘
                              │
                       ┌──────┴───────────┐
                       │  Config Context  │
                       │                  │
                       │ - AppSettings    │
                       │ - LocationCatalog│
                       │ - CharacterClass │
                       └──────────────────┘
```

**Domain Events (между контекстами):**
- `GameStarted(log_path: Path)` — Game ⇒ Parsing
- `GameStopped()` — Game ⇒ Presence
- `CharacterLevelChanged(level_info: LevelInfo)` — Parsing ⇒ Presence
- `AreaEntered(instance_info: InstanceInfo)` — Parsing ⇒ Presence

### Hexagonal Layout

```
src/poe2_rpc/
├── __init__.py
├── __main__.py                    # python -m poe2_rpc → cli.app()
├── cli.py                         # Typer app, composition root
├── __version__.py
│
├── domain/                        # Pure logic, no I/O imports
│   ├── __init__.py
│   ├── events.py                  # GameStarted, CharacterLevelChanged, ...
│   ├── models.py                  # LevelInfo, InstanceInfo (frozen pydantic)
│   ├── classes.py                 # CharacterClass, ClassAscendency enums
│   ├── locations.py               # Location, LocationCatalog VOs
│   └── ports.py                   # Protocols: GameDetector, LogStream, PresencePublisher, EventBus, LocationCatalog
│
├── application/                   # Use cases / orchestration
│   ├── __init__.py
│   ├── bus.py                     # AsyncioEventBus (subscribe/publish)
│   ├── throttle.py                # PresenceThrottle (15s rate-limit)
│   ├── handlers.py                # on_level_changed, on_area_entered → PresencePublisher
│   └── orchestrator.py            # App: bootstrap detection → streaming → parsing → presence
│
├── infrastructure/                # Adapters (touch external world)
│   ├── __init__.py
│   ├── detection.py               # PsutilGameDetector implements GameDetector
│   ├── streaming.py               # WatchdogLogStream implements LogStream
│   ├── parsing.py                 # RegexLogParser (line → domain events)
│   ├── presence.py                # PypresencePublisher (AioPresence + tenacity)
│   ├── settings.py                # AppSettings(BaseSettings)
│   ├── catalog.py                 # JsonLocationCatalog (loads locations.json)
│   └── logging.py                 # configure_structlog()
│
└── py.typed                       # PEP 561 marker
```

### Library Stack (Context7-backed)

| Категория | Библиотека | Library ID | Роль |
|-----------|------------|------------|------|
| Domain models | **pydantic** ≥2.7 | `/pydantic/pydantic` | `LevelInfo`, `InstanceInfo`, `Location` — frozen models с runtime-валидацией |
| Config | **pydantic-settings** ≥2.5 | `/pydantic/pydantic-settings` | `AppSettings(BaseSettings)` + `TomlConfigSettingsSource` |
| Log streaming | **watchdog** ≥4.0 | `/gorakhargosh/watchdog` | `Observer` + `FileModifiedEvent` handler |
| Retry | **tenacity** ≥8.4 | `/jd/tenacity` | `@retry` декораторы для IPC connect/update |
| Logging | **structlog** ≥24.1 | `/hynek/structlog` | `ConsoleRenderer` (dev) / `JSONRenderer` (prod) + `bind_contextvars` |
| CLI | **typer** ≥0.12 | `/fastapi/typer` | `run`, `once`, `validate-config`, `--config` |
| Discord IPC | **pypresence** ≥4.3 | `/websites/qwertyquerty.../pypresence` | `AioPresence` (async) + retry-обёртка |
| Process detect | **psutil** ≥5.9 | (existing) | Wrapped в `PsutilGameDetector` |
| Testing | **pytest** + **pytest-asyncio** + **pytest-mock** | — | Unit + integration |
| Type check | **mypy** ≥1.10 | — | `--strict` в CI |
| Lint/format | **ruff** ≥0.5 | — | replaces black + isort + flake8 |
| Packaging | **PyInstaller** ≥6.14 | `/pyinstaller/pyinstaller` | `.spec` с `datas` и `hiddenimports` |

### Key Pattern Snippets

**Domain event (frozen):**
```python
# domain/events.py
from pydantic import BaseModel, ConfigDict
from .models import LevelInfo, InstanceInfo

class CharacterLevelChanged(BaseModel):
    model_config = ConfigDict(frozen=True)
    level_info: LevelInfo

class AreaEntered(BaseModel):
    model_config = ConfigDict(frozen=True)
    instance_info: InstanceInfo
```

**Port (Protocol):**
```python
# domain/ports.py
from typing import Protocol, AsyncIterator

class LogStream(Protocol):
    def lines(self) -> AsyncIterator[str]: ...

class PresencePublisher(Protocol):
    async def publish(self, details: str, state: str, *, small_image: str) -> None: ...
    async def close(self) -> None: ...
```

**Adapter (watchdog):**
```python
# infrastructure/streaming.py
import asyncio
from pathlib import Path
from watchdog.events import FileModifiedEvent, FileSystemEventHandler
from watchdog.observers import Observer

class WatchdogLogStream:
    def __init__(self, log_path: Path, loop: asyncio.AbstractEventLoop):
        self._log_path = log_path
        self._loop = loop
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._offset = log_path.stat().st_size  # seek-EOF
        self._observer = Observer()

    async def lines(self) -> AsyncIterator[str]:
        handler = self._Handler(self)
        self._observer.schedule(handler, str(self._log_path.parent), recursive=False)
        self._observer.start()
        try:
            while True:
                yield await self._queue.get()
        finally:
            self._observer.stop()
            self._observer.join()

    class _Handler(FileSystemEventHandler):
        def __init__(self, stream: "WatchdogLogStream"): self._stream = stream
        def on_modified(self, event: FileModifiedEvent) -> None:
            if Path(event.src_path) != self._stream._log_path: return
            with self._stream._log_path.open("r", encoding="utf-8") as f:
                f.seek(self._stream._offset)
                new = f.read()
                self._stream._offset = f.tell()
            for line in new.splitlines():
                self._stream._loop.call_soon_threadsafe(
                    self._stream._queue.put_nowait, line
                )
```

**Adapter (pypresence + tenacity):**
```python
# infrastructure/presence.py
import logging
import structlog
from pypresence import AioPresence, InvalidPipe
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_sleep_log

logger = structlog.get_logger()
_stdlib_logger = logging.getLogger(__name__)

class PypresencePublisher:
    def __init__(self, client_id: str):
        self._rpc = AioPresence(client_id)
        self._connected = False

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=32),
        retry=retry_if_exception_type((ConnectionError, OSError, InvalidPipe)),
        before_sleep=before_sleep_log(_stdlib_logger, logging.WARNING),
    )
    async def connect(self) -> None:
        await self._rpc.connect()
        self._connected = True
        logger.info("presence_connected")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8),
           retry=retry_if_exception_type((InvalidPipe, OSError)))
    async def publish(self, details: str, state: str, *, small_image: str, start: int) -> None:
        if not self._connected:
            await self.connect()
        await self._rpc.update(details=details, state=state, start=start, small_image=small_image)
```

**Settings:**
```python
# infrastructure/settings.py
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict, TomlConfigSettingsSource

class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="POE2RPC_",
        toml_file=str(Path.home() / ".config" / "poe2-rpc" / "config.toml"),
    )
    discord_client_id: str = "1315800372207419504"
    process_name: str = "PathOfExileSteam.exe"
    presence_min_interval_seconds: float = 15.0
    log_level: str = "INFO"
    log_json: bool = False
    locations_url: str | None = None  # None ⇒ bundled JSON; URL ⇒ явный override

    @classmethod
    def settings_customise_sources(cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings):
        return (init_settings, env_settings, TomlConfigSettingsSource(settings_cls), file_secret_settings)
```

**CLI composition root:**
```python
# cli.py
import asyncio
import typer
from .infrastructure.settings import AppSettings
from .infrastructure.logging import configure_structlog
from .infrastructure.detection import PsutilGameDetector
from .infrastructure.streaming import WatchdogLogStream
from .infrastructure.parsing import RegexLogParser
from .infrastructure.presence import PypresencePublisher
from .infrastructure.catalog import JsonLocationCatalog
from .application.bus import AsyncioEventBus
from .application.orchestrator import Orchestrator

app = typer.Typer(help="Discord Rich Presence for Path of Exile 2")

@app.command()
def run(config: Path | None = None) -> None:
    settings = AppSettings(_toml_file=config) if config else AppSettings()
    configure_structlog(level=settings.log_level, json_output=settings.log_json)
    asyncio.run(_run_async(settings))

async def _run_async(settings: AppSettings) -> None:
    bus = AsyncioEventBus()
    detector = PsutilGameDetector(settings.process_name)
    catalog = (
        JsonLocationCatalog.from_url(settings.locations_url)
        if settings.locations_url
        else JsonLocationCatalog.from_bundled()
    )
    publisher = PypresencePublisher(settings.discord_client_id)
    parser = RegexLogParser()
    orchestrator = Orchestrator(detector, parser, publisher, catalog, bus, settings)
    await orchestrator.run()
```

### PyInstaller `.spec`

```python
# PathOfExile2DiscordRPC.spec
# -*- mode: python ; coding: utf-8 -*-
a = Analysis(
    ['src/poe2_rpc/__main__.py'],
    pathex=['src'],
    binaries=[],
    datas=[('locations.json', '.')],
    hiddenimports=[
        'watchdog.observers.read_directory_changes',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas,
    name='PathOfExile2DiscordRPC',
    debug=False, strip=False, upx=False,
    console=True, onefile=True,
)
```

### CI Updates

```yaml
# .github/workflows/build.yml (changes)
on:
  push:
    branches: [main]
    paths: ['src/**', 'PathOfExile2DiscordRPC.spec', 'pyproject.toml', 'locations.json']

jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install -e ".[dev]"
      - run: ruff check src tests
      - run: mypy --strict src/poe2_rpc
      - run: pytest

  build:
    needs: lint-and-test
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install -e .
      - run: pip install pyinstaller
      - run: pyinstaller PathOfExile2DiscordRPC.spec
      # ...rest unchanged (tag + release)
```

## Ontology

| Term | Definition |
|------|------------|
| **GameLogPath** | Абсолютный `Path` к `Client.txt` внутри `<steam-library>/steamapps/common/Path of Exile 2/logs/`. |
| **LevelInfo** | VO `(username: str, base_class: str, ascension_class: str \| None, level: int)`. Frozen pydantic. |
| **InstanceInfo** | VO `(area_code: str, area_display_name: str, level: int, seed: int)`. |
| **LocationCatalog** | Read-only mapping `area_code → display_name`. Загружается из bundled `locations.json` (упакован в .exe через `--add-data`). Если в `AppSettings.locations_url` явно задан URL, каталог грузится с него — это override, не цепочка. |
| **PresenceState** | Текущее представление состояния для Discord: `details` (строка с username/класс/уровень) + `state` (зона или random_status) + `small_image` (`ascension_class.lower().replace(" ", "_")`). |
| **DomainEvent** | Frozen pydantic-модель из `domain/events.py`. Публикуется в `EventBus`. |
| **Adapter** | Класс из `infrastructure/`, реализующий `Protocol` из `domain/ports.py`. |
| **Composition root** | Единственное место, где собираются адаптеры — `cli.py`. |

## Ontology Convergence

- Текущие dict-based `level_info` / `instance_info` → frozen pydantic VO с одинаковыми именами полей (zero-rename миграция).
- Текущий `current_status` dict → удаляется, заменяется явным state в `Orchestrator`.
- Текущий global `rpc` → инкапсулирован в `PypresencePublisher`.
- `random_status` → переезжает в `application/throttle.py` или `domain/presence_state.py` как pure-function `default_state_text() -> str`.

## Trace Findings

Из Phase 3 trace (см. `deep-dive-trace-architecture-libraries.md`):

- **Lane 1 (code structure)**: глобальный `rpc`, monolithic `monitor_log()` с 4 ответственностями, dict-state-bag `current_status`, дублирование форматирования `details`. Естественные границы доменов уже проступают (game/parsing/presence/config).
- **Lane 2 (distribution)**: PyInstaller `--onefile` + path-filter совместимы с `src/`-layout при правке CI; spec-файл позволяет упаковать `locations.json` как data.
- **Lane 3 (Context7 best practices)**:
  - watchdog: `Observer + FileModifiedEvent` — нативный Windows API.
  - tenacity: `wait_exponential + retry_if_exception_type + before_sleep_log` покрывает текущий manual retry с улучшением логирования.
  - pydantic-settings: `TomlConfigSettingsSource` + env-overrides — один источник правды для конфига.
  - pypresence: `AioPresence` для async; min update interval — 15 секунд.
  - structlog: `ConsoleRenderer` для dev / `JSONRenderer` для prod, `contextvars.bind_contextvars` для rich-контекста.
  - PyInstaller: `.spec`-файл с `datas` + `hiddenimports`.

Все 3 per-lane critical unknowns разрешены пользователем выбором "Aggressive DDD" + 4 priorities — это даёт чёткий мандат на полную перестройку.

## Interview Transcript (compressed)

**Round 1 (lane confirmation):**
- Predloženo: Lane 1 = code structure, Lane 2 = distribution, Lane 3 = Context7 strict.
- Выбор: "Lane 3 — только Context7" — Context7-driven library research как ведущая линия.

**Round 2 (architectural direction):**
- Predloženo: Conservative / Balanced / Aggressive DDD.
- Выбор: **Aggressive DDD** — bounded contexts, hexagonal, async event bus, AioPresence, 100% type coverage, mypy strict.

**Round 3 (priorities):**
- Predloženo: latency / reliability / testability / observability.
- Выбор: **все 4** — полный outcome без компромиссов.

Ambiguity: ≈10% (направление + приоритеты явно зафиксированы; технические детали в Acceptance Criteria и снипетах).
