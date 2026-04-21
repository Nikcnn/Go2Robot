# Go2_MVP: как система работает технологически

## 1. Что это за система

`Go2_MVP` — это не полноценная автономная навигационная платформа, а Python MVP для безопасного сценарного запуска инспекционных миссий на Unitree Go2 в контролируемой среде.

По факту система делает следующее:

1. Поднимает FastAPI-сервер и простой web-интерфейс оператора.
2. Загружает маршрут из JSON.
3. Последовательно исполняет шаги маршрута.
4. Пропускает все движения через единый контур приоритетов и безопасности.
5. Снимает телеметрию и видеокадры.
6. На checkpoint-шагах сохраняет изображение, снапшот телеметрии и результат анализа.
7. Ведет run-артефакты на диск и формирует `final_report.json`.

Ключевая идея реализации: это не "умный робот, который сам строит путь", а "mission runner + safety/control core + adapter к железу + API/UI вокруг этого".

## 2. Что является реальной точкой входа

Рабочая точка входа MVP:

```bash
python -m src.main --config config/app_config.yaml
```

Важно:

- Реальный runtime запускается из `src/main.py`.
- Файл `Go2_MVP/main.py` в корне проекта сейчас является шаблонным PyCharm-скриптом и к MVP не относится.

## 3. Технологический стек

Система собрана на небольшом прикладном стеке без ROS/ROS2:

- `FastAPI` — HTTP API, WebSocket API, lifecycle приложения.
- `Uvicorn` — ASGI runtime.
- `Pydantic v2` — строгая валидация конфигов, API payload и route schema.
- `PyYAML` — загрузка `app_config.yaml`.
- `OpenCV` (`opencv-python-headless`) — JPEG-кодирование, resize, image diff, сохранение кадров.
- `numpy` — операции над кадрами и depth-данными.
- `pytest` / `httpx` — быстрые тесты без hardware.
- `unitree_sdk2py` — используется только в режиме `go2`.
- `pyrealsense2` — опционально для Intel RealSense D435i.

Архитектурно это обычный Python backend с несколькими фоновыми потоками, а не distributed-система и не robotics framework.

## 4. Общая архитектура

Упрощенно поток выглядит так:

```text
Operator UI / API client
        |
        v
   FastAPI app
        |
        v
     AppRuntime
        |
        +-- ControlCore
        +-- MissionManager
        +-- TelemetryService
        +-- CameraStream
        +-- RealsenseCameraService
        +-- StorageManager
        +-- EventBus
        +-- PersistentEventLog
        |
        v
 RobotAdapterProtocol
    |              |
    v              v
 MockRobotAdapter  Go2RobotAdapter
```

Ключевой принцип реализации: весь доступ к реальному роботу изолирован в adapter-слое. Оркестрация миссии, API, storage и UI не должны знать детали SDK Unitree.

## 5. Основные модули и их роли

### `src/main.py`

Отвечает за bootstrap процесса:

- читает путь к YAML-конфигу;
- загружает `AppConfig`;
- настраивает logging;
- создает приложение через `create_app(...)`;
- подбирает порт;
- запускает `uvicorn.run(...)`.

Дополнительно здесь есть два важных behavior:

1. Если `robot.mode == go2`, а создание real-adapter завершается `RuntimeError`, код пытается автоматически откатиться в `mock`.
2. Если желаемый порт занят, сервер ищет следующий свободный порт начиная с указанного в конфиге.

### `src/api.py`

Это композиционный слой всего приложения. Здесь создаются:

- `StorageManager`
- `EventBus`
- `PersistentEventLog`
- `ControlCore`
- `TelemetryService`
- `CameraStream`
- `RealsenseCameraService`
- `MissionManager`
- `RobotStateMachine`

Также здесь описаны:

- HTTP endpoints;
- WebSocket endpoints;
- startup/shutdown lifecycle;
- логика `AppRuntime`.

### `src/control.py`

Это главный контур управления и безопасности.

Именно он определяет:

- текущий режим робота;
- статус миссии;
- latch ESTOP;
- приоритет ручного режима над автоматическим;
- watchdog ручного teleop;
- сглаживание команд движения;
- когда реально слать `send_velocity(...)`, а когда делать `stop()`.

Фактически `ControlCore` — это центральный arbiter движения.

### `src/mission.py`

Отвечает за маршрут и исполнение миссии:

- ищет route file;
- валидирует JSON route через `RouteModel`;
- создает новый run;
- запускает фоновый поток исполнения;
- выполняет шаги по одному;
- вызывает checkpoint-логику;
- завершает миссию и финализирует отчет.

### `src/telemetry.py`

Периодически опрашивает adapter и формирует `TelemetrySnapshot`.

Также:

- держит `latest` snapshot в памяти;
- пишет телеметрию в `telemetry.jsonl`;
- обновляет `RobotStateMachine`.

### `src/streaming.py`

Содержит два runtime-сервиса:

- `EventBus` — in-memory очередь событий для WebSocket-клиентов;
- `CameraStream` — фоновый захват кадра и публикация MJPEG потока.

### `src/storage.py`

Отвечает за disk artifacts миссии:

- создает каталог run;
- пишет `mission_meta.json`;
- ведет `event_log.jsonl` и `telemetry.jsonl`;
- сохраняет checkpoint-изображения и analysis JSON;
- формирует `final_report.json`.

### `src/analysis.py`

Очень легкий слой анализа изображения. Сейчас поддерживаются:

- `frame_diff`
- `simple_presence` как stub

Это не ML pipeline, а нормализованный интерфейс analyzer-функции.

### `src/robot/robot_adapter.py`

Определяет protocol adapter-а и mock implementation.

### `src/robot/go2_adapter.py`

Реальная интеграция с Go2 через `unitree_sdk2py`.

### `src/sensors/realsense_camera.py`

Опциональная интеграция внешней Intel RealSense D435i без ломки основной robot-camera логики.

## 6. Конфигурация

Основной конфиг лежит в:

- `config/app_config.yaml`

Конфиг загружается через `src/config.py` в строгую Pydantic-модель `AppConfig`.

Поддерживаются следующие секции:

- `robot`
- `telemetry`
- `camera`
- `realsense`
- `control`
- `analysis`
- `server`
- `storage`
- `logging`

Практически важные поля:

- `robot.mode: mock | go2`
- `robot.interface_name`
- `robot.camera_enabled`
- `robot.max_vx`
- `robot.max_vy`
- `robot.max_vyaw`
- `telemetry.hz`
- `camera.fps/width/height/jpeg_quality`
- `control.watchdog_timeout_ms`
- `analysis.frame_diff_threshold`
- `storage.runs_dir`

Нюанс:

- В `src/config.py` дефолт `watchdog_timeout_ms` равен `500`.
- В текущем `config/app_config.yaml` это значение переопределено на `1500`.

То есть реальное поведение системы определяется не только моделью конфигурации, но и содержимым конкретного YAML-файла.

## 7. Runtime bootstrap: что происходит при старте

Когда вызывается `create_app(...)`, происходит такая сборка runtime:

1. Вычисляется `project_root`, `routes_dir`, `web_dir`, `runs_dir`.
2. Создаются `EventBus`, `StorageManager`, `RobotStateMachine`, `PersistentEventLog`.
3. Через `build_robot_adapter(...)` создается либо `MockRobotAdapter`, либо `Go2RobotAdapter`.
4. Поверх adapter создаются `ControlCore`, `TelemetryService`, `CameraStream`, `MissionManager`.
5. Если включен внешний RGB-D сенсор, создается `RealsenseCameraService`.
6. Все это упаковывается в `AppRuntime` и кладется в `app.state.runtime`.

При входе в lifespan-протокол приложения вызывается `_start_runtime(...)`:

1. Стартует `ControlCore`.
2. Выполняется `adapter.connect()`.
3. Если подключение к adapter не удалось:
   - генерируется `adapter_startup_failed`;
   - runtime помечает adapter как неподнятый;
   - `ControlCore` лочит ESTOP.
4. Пытается стартовать RealSense.
5. Стартует telemetry poller.
6. Стартует camera stream worker.
7. Публикуется событие `server_started`.

Важно: сервер может подняться даже при проблеме с реальным adapter, но в безопасном состоянии.

## 8. Модель данных

Ключевые enum-и:

- `RobotMode`: `AUTO`, `MANUAL`, `ESTOP`, `SERVICE`
- `MissionStatus`: `IDLE`, `STARTING`, `RUNNING`, `PAUSED_MANUAL`, `COMPLETED`, `ABORTED`, `FAILED`, `ESTOPPED`
- `MotionMode`: `idle`, `manual`, `mission`, `settling`, `stopped`
- `CommandSource`: `AUTO`, `MANUAL`, `SYSTEM`

Ключевые Pydantic-модели:

- `RouteModel`
- `MoveStep`
- `RotateStep`
- `CheckpointStep`
- `StopStep`
- `StandUpStep`
- `WaitStep`
- `TelemetrySnapshot`
- `MotionCommand`
- `MissionCurrentResponse`
- `MotionStateResponse`
- `AnalyzerResult`
- `FinalReport`

Это важно, потому что route, API и storage завязаны на одну и ту же строгую schema-модель, а не на "сырые dict".

## 9. Как устроен маршрут

Маршрут хранится как JSON в `config/routes/*.json`.

Механика разрешения маршрута:

1. Сначала система ищет файл с точным именем `routes_dir / route_id`.
2. Потом пробует `routes_dir / f"{route_id}.json"`.
3. Если файла по имени нет, перебирает все JSON и ищет совпадение по полю `route.route_id`.

Это позволяет стартовать миссию как по filename, так и по логическому `route_id`.

Поддерживаемые типы шагов в текущем коде:

- `stand_up`
- `move`
- `move_velocity`
- `rotate`
- `wait`
- `settle`
- `checkpoint`
- `stop`

Типичный route выглядит так:

```json
{
  "route_id": "demo_route_v1",
  "steps": [
    {"id": "move_1", "type": "move", "vx": 0.2, "vy": 0.0, "vyaw": 0.0, "duration_sec": 0.4},
    {"id": "checkpoint_panel_a", "type": "checkpoint", "waypoint_id": "panel_A", "settle_time_sec": 0.1, "analyzer": "simple_presence"},
    {"id": "rotate_1", "type": "rotate", "vyaw": 0.5, "duration_sec": 0.3},
    {"id": "stop_1", "type": "stop"}
  ]
}
```

## 10. Контур управления: как принимается решение, двигать робота или нет

### 10.1. `ControlCore` — единая точка арбитража

Все движения, вне зависимости от источника, проходят через `ControlCore.submit(...)`.

Именно здесь реализованы правила:

- если ESTOP залочен, команда отвергается;
- если источник `AUTO`, а робот в `MANUAL`, команда отвергается;
- если источник `MANUAL`, а режим не `MANUAL`, команда отвергается;
- системные команды (`SYSTEM`) могут пройти всегда.

Идея правильная: не mission runner и не API напрямую говорят adapter-у "едь", а всегда проходят через один central gatekeeper.

### 10.2. Приоритеты

Фактическая иерархия такая:

1. `ESTOP`
2. `MANUAL`
3. `AUTO`

Смысл:

- ESTOP полностью блокирует движение и переводит mission status в `ESTOPPED`;
- manual takeover останавливает автодвижение и ставит миссию на `PAUSED_MANUAL`;
- automatic mission commands работают только когда робот в `AUTO`.

### 10.3. Manual takeover

Когда вызывается `take_manual()`:

1. режим меняется на `MANUAL`;
2. при наличии активной миссии она переводится в `PAUSED_MANUAL`;
3. adapter получает `enter_manual_mode()`;
4. вызывается `stop_motion("manual_takeover")`;
5. генерируются `mode_changed` и `mission_paused`.

Когда вызывается `release_manual()`:

1. режим меняется обратно на `AUTO`;
2. adapter получает `exit_manual_mode()`;
3. движение принудительно останавливается;
4. миссия не возобновляется автоматически.

Ключевой behavioral contract: release manual не делает auto-resume. Для возобновления нужен отдельный `resume_mission()`.

### 10.4. ESTOP

`latch_estop()` делает сразу несколько вещей:

- `estop_latched = True`
- `mode = ESTOP`
- текущая миссия переводится в `ESTOPPED`
- активный шаг сбрасывается
- обнуляются target velocity
- вызывается `adapter.emergency_stop()`

ESTOP защелкивается до явного `reset_estop()`.

### 10.5. Motion control loop

В `ControlCore` работает отдельный поток `_control_loop()` с частотой 50 Гц.

Этот поток:

1. читает активный target velocity;
2. применяет accel/decel ramp;
3. приводит команду к "эффективной" форме;
4. решает, нужно ли слать `send_velocity(...)` или `stop()`.

Технологически это важный момент: adapter не получает мгновенный raw target. Между API/mission и adapter-ом стоит прослойка плавного доведения скорости.

### 10.6. Ограничения и стабилизация скоростей

Внутри `ControlCore` зашиты:

- минимальные пороги эффективного движения:
  - `vx >= 0.22`
  - `vy >= 0.22`
  - `vyaw >= 0.45`
- коэффициенты ускорения/замедления по осям

Зачем это сделано:

- слишком маленькие скорости на Go2 могут приводить не к уверенной походке, а к "наклону без шага";
- через minimum effective command система поднимает команду до уровня, при котором gait реально включается;
- одновременный ramp-up/ramp-down уменьшает дерганость.

То есть тут реализован не просто clamp, а небольшой motion shaping слой.

### 10.7. Watchdog ручного управления

Отдельный поток `_watchdog_loop()` следит за тем, чтобы в `MANUAL` периодически приходили teleop-команды.

Если:

- робот в `MANUAL`,
- не идет settling после stand-up,
- и новые teleop команды не приходили дольше `watchdog_timeout_ms`,

то:

- вызывается `stop_motion("manual teleop watchdog timeout")`;
- генерируется warning event.

Это dead-man behavior для ручного teleop.

## 11. Как выполняется миссия

### 11.1. Старт миссии

При `mission.start(route_id)` происходит:

1. поиск и загрузка route;
2. валидация route;
3. `storage.start_run(route.route_id)`;
4. `control.begin_mission(mission_id, route_id)`;
5. запуск фонового потока `mission-executor`.

### 11.2. Фоновый mission thread

Миссия исполняется не в asyncio loop, а в отдельном потоке.

Это правильное решение для текущего MVP, потому что:

- шаги миссии синхронные;
- checkpoint-логика может блокировать;
- API сервер и WebSocket push не должны зависеть от длительности route step.

### 11.3. Основной цикл выполнения

В `_run_mission(...)` система:

1. переводит миссию в `RUNNING`;
2. идет по шагам route последовательно;
3. перед каждым шагом вызывает `wait_until_runnable()`;
4. выставляет `active_step_id`;
5. публикует `step_started`;
6. исполняет конкретный step handler;
7. увеличивает `steps_executed`;
8. публикует `step_completed`;
9. если цикл завершился без аварии, вызывает `complete_mission()`.

Если возникает исключение, вызывается `fail_mission(...)`.

В `finally` всегда вызывается `storage.finalize_run(...)`.

### 11.4. Что делает `wait_until_runnable()`

Этот метод блокирует исполнение шага, если:

- ESTOP активен;
- миссия прервана;
- статус миссии уже терминальный;
- миссия поставлена на паузу ручным режимом.

То есть mission thread не крутит свою логику в обход control-state.

### 11.5. Как реально исполняется движение

Метод `_execute_motion(...)` разбивает движение на куски по `0.05` секунды.

На каждом цикле он:

1. проверяет, что миссию можно продолжать;
2. отправляет target в `ControlCore.submit(...)` как `AUTO`;
3. ждет маленький chunk;
4. повторяет, пока не истечет `duration_sec`.

После завершения делает `stop_motion("mission step completed")`.

То есть mission runner не сам шлет прямые motor-команды. Он лишь регулярно обновляет целевую скорость, а реальную выдачу в adapter делает `ControlCore`.

## 12. Как работает checkpoint

Checkpoint — это центральный смысловой шаг MVP.

При checkpoint происходит:

1. `ControlCore.stop_motion("checkpoint settle")`
2. ожидание `settle_time_sec`
3. `adapter.capture_frame()`
4. чтение последнего telemetry snapshot
5. запуск `analyze(...)`
6. опциональный сбор RealSense snapshot
7. `storage.save_checkpoint(...)`
8. публикация `checkpoint_processed`

### 12.1. Анализ изображения

Сейчас есть два analyzer-режима:

#### `frame_diff`

Делает:

- загрузку reference image;
- resize текущего кадра к размеру reference;
- mean absolute diff по всем пикселям;
- нормализацию в диапазон `0..1`;
- сравнение с threshold.

Результат:

- `stable`, если diff <= threshold
- `changed`, если diff > threshold

#### `simple_presence`

Пока не реализует реальный анализ и возвращает `not_configured`.

### 12.2. Разрешение reference image

Если `reference_image` в route относительный, он резолвится от `project_root`.

Это важно, потому что analyzer работает не из текущей shell-директории, а из вычисленного project context.

## 13. Adapter layer: mock и real mode

### 13.1. `MockRobotAdapter`

Mock adapter — это полноценная in-process симуляция:

- хранит текущую velocity;
- численно интегрирует pose;
- синтезирует battery/voltage/current;
- рисует искусственный BGR-кадр с текстом и маркерами;
- выдает pose и robot state как будто это настоящий робот.

Зачем это сделано:

- можно запускать весь стек end-to-end без железа;
- можно тестировать API, mission flow, storage, UI и telemetry;
- CI не зависит от robot hardware.

### 13.2. `Go2RobotAdapter`

Real adapter подключается к Unitree SDK и работает через DDS/CycloneDDS.

Используемые сущности:

- `ChannelFactory`
- `ChannelSubscriber`
- `SportClient`
- `RobotStateClient`
- `VideoClient`
- DDS messages `SportModeState_` и `LowState_`

Фактические источники данных:

- `rt/sportmodestate` — pose, IMU yaw, mode, sport errors;
- `rt/lowstate` — BMS и power data.

### 13.3. Активация робота в `go2`

Метод `activate()` делает:

1. `StandUp`
2. небольшую паузу на settle
3. `BalanceStand`

Смысл в том, что простого stand-up недостаточно для корректного включения locomotion режима.

### 13.4. Движение и остановка в `go2`

Используются:

- движение: `SportClient.Move(vx, vy, vyaw)`
- остановка: `SportClient.StopMove()`
- software estop: `SportClient.Damp()`

После `Damp()` требуется повторная активация робота перед продолжением движения.

### 13.5. Получение pose и battery в `go2`

Pose строится из:

- `position[0]`
- `position[1]`
- `imu_state.rpy[2]`

Battery и power читаются из `LowState_`:

- `soc`
- `power_v`
- `power_a`
- `cycle`

### 13.6. Камера в `go2`

Если `robot.camera_enabled: true`, adapter пытается получить кадр двумя путями:

1. через `VideoClient.GetImageSample()`
2. через fallback `cv2.VideoCapture(..., cv2.CAP_GSTREAMER)` на URI:

```text
udp://230.1.1.1:1720
```

То есть видеопуть здесь уже двухступенчатый: сначала прямой SDK client, потом UDP/GStreamer fallback.

## 14. Дополнительный внешний сенсор: RealSense D435i

`RealsenseCameraService` — это отдельный optional service.

Он не подменяет robot camera, а работает параллельно.

Если `realsense.enabled: true`, то сервис:

1. поднимает `pyrealsense2.pipeline()`;
2. включает color/depth stream;
3. при наличии обоих потоков выравнивает depth к color;
4. хранит последний bundle в памяти;
5. по запросу checkpoint-а сохраняет snapshot в run directory.

На checkpoint RealSense может создать:

- `*_color.jpg`
- `*_depth.npy`
- `*_depth_preview.png`

Также в metadata кладутся intrinsics color/depth stream.

Параметр `startup_required` задает поведение при неуспешном старте:

- `false` — сервер стартует, а сенсор считается unavailable;
- `true` — startup считается ошибкой.

## 15. Телеметрия и потоковое вещание

### 15.1. `TelemetryService`

Этот сервис:

- опрашивает adapter с частотой `telemetry.hz`;
- формирует `TelemetrySnapshot`;
- кладет snapshot в memory cache;
- пишет snapshot в `telemetry.jsonl`;
- обновляет `RobotStateMachine`.

В snapshot входят:

- timestamp
- robot mode
- mission status
- route id
- active step id
- mission id
- pose
- robot state

### 15.2. `RobotStateMachine`

Это отдельный слой "эффективного состояния" робота.

Сейчас он умеет выводить:

- `disconnected`
- `connecting`
- `ready`
- `moving`
- `paused`
- `estop`

Однако practically important detail:

- `TelemetryService` при очередном poll передает в state machine connected/paused/estop;
- признак движения должен приходить через `notify_motion(...)`;
- в текущем коде `notify_motion(...)` нигде не вызывается.

Иными словами, state machine сейчас в основном отражает connection / pause / estop, а не полную фазу движения.

### 15.3. Camera stream

`CameraStream` работает в отдельном потоке:

1. вызывает `adapter.capture_frame()`;
2. при необходимости делает resize;
3. JPEG-кодирует кадр;
4. держит в памяти только latest JPEG;
5. отдает его через MJPEG generator.

Это single-slot streaming модель: хранится только последний кадр, а не очередь кадров.

### 15.4. Event streaming

`EventBus` хранит in-memory историю событий с sequence number.

Через `/ws/events` клиент:

- сначала получает хвост истории;
- потом дочитывает новые события через polling `read_since(last_sequence)`.

## 16. Два слоя логирования

В `Go2_MVP` логирование организовано в двух параллельных слоях.

### 16.1. Mission-scoped лог (`StorageManager`)

Во время активной миссии `StorageManager.record_event(...)` пишет события в:

- `runs/mission_<id>/event_log.jsonl`

Также эти события наполняют разделы:

- `mode_transitions`
- `errors`
- `warnings`

в итоговом `final_report.json`.

### 16.2. Cross-mission лог (`PersistentEventLog`)

Отдельно существует append-only лог:

- `runs/events.jsonl`

Он живет поверх всех миссий и нужен для:

- action history;
- connection history;
- state transitions;
- movement blocked history;
- ошибок и предупреждений, не привязанных только к одной миссии.

Категории событий здесь нормализованы:

- `state_transition`
- `action_accepted`
- `action_rejected`
- `movement_blocked`
- `fault`
- `mission`
- `connection`

Это полезный технологический момент: per-run лог и cross-run лог решают разные задачи.

## 17. HTTP API и WebSocket интерфейсы

### 17.1. Базовые mission endpoints

- `GET /api/status`
- `GET /api/mission/current`
- `GET /api/missions/state`
- `POST /api/mission/start`
- `POST /api/missions/run`
- `POST /api/mission/pause`
- `POST /api/mission/resume`
- `POST /api/mission/abort`

`/api/missions/run` позволяет запустить inline-миссию прямо телом запроса, без готового route file.

### 17.2. Control/mode endpoints

- `POST /api/mode/manual/take`
- `POST /api/mode/manual/release`
- `POST /api/mode/estop`
- `POST /api/mode/reset-estop`
- `POST /api/mode/sit`
- `POST /api/robot/activate`

### 17.3. Ручное управление

- `POST /api/teleop/cmd`
- `POST /api/robot/manual/cmd`
- `POST /api/robot/manual/stand-up`
- `POST /api/robot/manual/sit`
- `POST /api/robot/manual/stop`
- `POST /api/robot/manual/clear`

### 17.4. Дополнительный action API

Есть агрегированный endpoint:

- `POST /api/robot/action`

Поддерживаемые action:

- `connect`
- `disconnect`
- `stand_up`
- `stop_motion`
- `pause`
- `resume`
- `damping_on`
- `reset_fault`
- `manual_mode`
- `auto_mode`

Это по сути command-dispatch API поверх runtime.

### 17.5. Стриминг и история

- `WS /ws/telemetry`
- `WS /ws/events`
- `GET /stream/camera`
- `GET /api/robot/status`
- `GET /api/robot/history`

## 18. Как работает web UI

UI в `src/web/` сделан без frontend framework.

Слой состоит из:

- `index.html`
- `app.js`
- `styles.css`

Технологически UI делает три вещи:

1. Периодически дергает REST endpoints.
2. Подписывается на WebSocket telemetry/events.
3. Показывает MJPEG stream как обычный `<img src="/stream/camera">`.

### 18.1. Интервалы обновления

В текущем `app.js`:

- mission status обновляется раз в 1 секунду;
- robot status обновляется раз в 1 секунду;
- history panel обновляется раз в 5 секунд;
- teleop loop шлет команды раз в 100 мс.

### 18.2. Keyboard teleop

Во время manual mode UI:

- отслеживает `W/S` для `vx`;
- `A/D` для `vy`;
- `Q/E` для `vyaw`;
- `Space` как мгновенный stop;
- `X` как ESTOP.

Команды отправляются на `/api/teleop/cmd`.

Это означает, что browser является teleop publisher-ом, а backend — safety gate и executor.

## 19. Что сохраняется на диск

Каждый run создает каталог:

```text
runs/mission_<mission_id>/
```

Внутри хранятся:

```text
mission_meta.json
event_log.jsonl
telemetry.jsonl
analysis/<waypoint_id>.json
images/<waypoint_id>_<timestamp>.jpg
final_report.json
```

Если включен RealSense, дополнительно:

```text
realsense/<waypoint_id>_<timestamp>_color.jpg
realsense/<waypoint_id>_<timestamp>_depth.npy
realsense/<waypoint_id>_<timestamp>_depth_preview.png
```

### `final_report.json` содержит

- `mission_id`
- `route_id`
- `mission_status`
- `started_at`
- `finished_at`
- `steps_executed`
- `checkpoints`
- `analysis_results`
- `mode_transitions`
- `errors`
- `warnings`

То есть финальный отчет собирает не только итоговый статус, но и всю важную историю миссии.

## 20. Как работает система в mock mode

В `mock` режиме:

- не нужен Go2;
- не нужен `unitree_sdk2py`;
- телеметрия синтетическая;
- pose синтетическая;
- battery синтетическая;
- камера синтетическая;
- весь mission flow, UI, storage и tests остаются рабочими.

Это основной режим разработки и smoke-проверки.

Фактически mock mode реализован как полноценный digital execution harness для backend-логики.

## 21. Как работает система в go2 mode

В `go2` режиме:

- нужен Ethernet interface, передаваемый как `interface_name`;
- нужен установленный `unitree_sdk2py`;
- желательно включить `robot.camera_enabled`, если нужен live stream с робота;
- можно отдельно включить `realsense.enabled`, если нужен внешний RGB-D checkpoint capture.

Типовой operational flow:

1. сервер стартует;
2. adapter подключается к DDS transport;
3. robot status начинает поступать из `rt/sportmodestate` и `rt/lowstate`;
4. оператор может активировать робота;
5. миссия запускается из route;
6. на каждом шаге движение идет через `ControlCore`;
7. checkpoint сохраняет артефакты и отчетность;
8. после завершения run закрывается и отчет пишется на диск.

## 22. Ограничения текущего MVP

Это важно явно зафиксировать.

Система сейчас не реализует:

- SLAM;
- локализацию по карте;
- obstacle avoidance;
- планировщик траектории;
- глобальную навигацию по waypoint map;
- multi-robot orchestration;
- production safety certification;
- серьезный vision/ML pipeline;
- ROS2 integration как основу runtime;
- frontend build system.

Даже route "short_walk_20cm" — это сценарий по времени и скорости, а не движение к геометрической цели с feedback-навигацией.

## 23. Что проверяется тестами

В `tests/` покрыты ключевые инженерные контуры:

- загрузка и валидация маршрута;
- приоритеты control layer;
- watchdog ручного teleop;
- API smoke scenario;
- формирование final report;
- отдельные проверки Go2 adapter и RealSense service.

Это значит, что минимальный контракт системы уже закреплен на уровне unit/smoke tests, а не только на уровне ручной проверки.

## 24. Краткий итог по архитектурной идее

Если описать `Go2_MVP` одной формулой, то это:

```text
FastAPI runtime
+ control/safety core
+ route executor
+ adapter abstraction
+ telemetry/camera streaming
+ per-run storage
```

Система технологически сильна не "сложным AI", а правильным разнесением ответственности:

- adapter изолирует железо;
- control централизует правила безопасности;
- mission отвечает только за сценарий;
- telemetry и camera работают как сервисы;
- storage делает воспроизводимые артефакты;
- UI и API являются только операторским слоем над этим runtime.

Именно поэтому проект можно прогонять end-to-end в `mock`, а затем переводить тот же orchestration-layer на реальный Go2 через `Go2RobotAdapter`.
