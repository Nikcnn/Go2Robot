# Go2 Inspection System: техническое состояние проекта

Этот файл описывает текущее состояние проекта. Целевая платформа для запуска на роботе: Ubuntu 20.04 и Python 3.8. ROS-слой использует ROS 2 Foxy.

## 1. Что входит в проект

В репозитории сейчас есть два рабочих направления:

- `src/`: самостоятельное Python-приложение без ROS. Оно поднимает FastAPI, web-панель оператора, исполняет scripted JSON routes, пишет телеметрию, изображения, события и отчеты.
- `ros_ws/`: ROS 2 Foxy workspace для waypoint-навигации через Nav2, bridge-узлов и coordinate missions.

Оба направления рассчитаны на безопасную тестовую среду. Это не production safety system.

## 2. Платформа

- OS: Ubuntu 20.04.
- Python: 3.8.
- ROS: ROS 2 Foxy только для `ros_ws/`.
- RMW для SDK-facing процессов: `rmw_cyclonedds_cpp`.

Windows workspace можно использовать для редактирования и статической проверки, но runtime ROS 2, Nav2, Unitree SDK, lidar и RealSense нужно проверять на Ubuntu 20.04.

## 3. Структура репозитория

```text
src/                  Python application layer
config/routes/        scripted routes для Python app
ros_ws/               ROS 2 Foxy workspace
shared_missions/      coordinate missions и maps для ROS layer
runs/                 runtime artifacts
tests/                hardware-free pytest tests
requirements.txt      Python 3.8 dependencies для src/ и tests
```

## 4. Python application layer

Python app запускается так:

```bash
python3 -m src.main --config config/app_config.yaml
```

Главные модули:

- `src/main.py`: bootstrap, config loading, выбор порта, запуск Uvicorn.
- `src/api.py`: FastAPI application, HTTP endpoints, WebSockets, lifecycle.
- `src/control.py`: central control/safety arbiter.
- `src/mission.py`: загрузка и исполнение scripted routes.
- `src/models.py`: Pydantic v2 schemas.
- `src/robot/robot_adapter.py`: adapter protocol и mock adapter.
- `src/robot/go2_adapter.py`: boundary для real Unitree Go2 SDK.
- `src/telemetry.py`: polling telemetry.
- `src/streaming.py`: event stream и camera stream.
- `src/storage.py`: mission artifacts и final reports.
- `src/sensors/realsense_camera.py`: optional RealSense support.
- `src/web/`: vanilla dashboard.

## 5. Mock mode

Default config `config/app_config.yaml` использует:

```yaml
robot:
  mode: mock
```

Mock mode не требует:

- Unitree Go2;
- `unitree_sdk2py`;
- ROS 2;
- RealSense.

Он дает synthetic pose, telemetry и camera frames. Это основной режим для быстрой проверки backend, UI, storage и tests.

## 6. Real Go2 mode в Python app

Пример config:

```text
config/app_config.go2.enp0s20f0u1c2.yaml
```

Для запуска нужен установленный `unitree_sdk2py` и правильный network interface:

```yaml
robot:
  mode: go2
  interface_name: enp0s20f0u1c2
  camera_enabled: true
```

Unitree SDK integration должна оставаться в adapter layer. Нельзя размазывать SDK calls по API, mission или UI слоям.

## 7. Control semantics

Все движения проходят через `ControlCore`.

Приоритет:

```text
ESTOP > MANUAL > AUTO
```

Правила:

- ESTOP блокирует движение.
- Manual takeover ставит mission на паузу.
- Manual release не делает automatic resume.
- Manual teleop имеет watchdog.
- В один момент должен быть один active motion controller.

## 8. Python route model

Routes лежат в:

```text
config/routes/*.json
```

Поддерживаемые step types:

- `move`
- `move_velocity`
- `rotate`
- `checkpoint`
- `stop`
- `stand_up`
- `wait`
- `settle`

Это scripted time/velocity routes. Это не map navigation и не path planner.

## 9. Storage and reports

Каждый run пишет artifacts в `runs/`.

Обычная структура:

```text
runs/mission_<id>/
  mission_meta.json
  event_log.jsonl
  telemetry.jsonl
  images/
  analysis/
  final_report.json
```

Cross-run event log:

```text
runs/events.jsonl
```

Если включен RealSense, могут появляться дополнительные RGB-D artifacts.

## 10. ROS 2 Foxy layer

ROS workspace:

```text
ros_ws/
```

Пакеты:

- `go2_interfaces`: custom services `CheckpointCapture` и `MissionControl`.
- `go2_bridge`: owner adapter process, `/cmd_vel`, `/odom`, `/tf`, checkpoint capture, lidar, optional RealSense bridge.
- `go2_mission`: mission service, coordinate mission loader, Nav2 `FollowWaypoints` client.
- `go2_nav_bringup`: launch files, Nav2 params, RViz config, maps.

Build:

```bash
cd ros_ws
source /opt/ros/foxy/setup.bash
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
source install/setup.bash
export GO2_OPERATOR_APP_ROOT=/path/to/Go2Robot
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
```

## 11. ROS mission model

Coordinate missions лежат в:

```text
shared_missions/missions/*.json
```

Пример:

```json
{
  "mission_id": "inspect_line_a",
  "map_id": "site_a_floor_1",
  "waypoints": [
    {"id": "panel_A", "x": 4.12, "y": 1.83, "yaw": 1.57, "task": "inspect_panel"}
  ]
}
```

`go2_mission` отправляет waypoints в Nav2 `FollowWaypoints`, а checkpoint capture делает через service в `go2_bridge`.

## 12. Lidar, mapping, AMCL, Nav2

В коде ROS слоя есть путь:

```text
Unitree or mock lidar -> /points -> lidar_bridge -> /scan
```

Но real Unitree built-in lidar SDK message import path еще требует проверки на Ubuntu 20.04 с подключенным роботом. Поэтому нельзя считать mapping, AMCL или Nav2 полностью runtime-validated, пока нет живого и корректного `/scan`.

## 13. RealSense

RealSense D435i optional.

В Python app он работает через `src/sensors/realsense_camera.py`.

В ROS layer он работает через:

```text
go2_bridge/camera_bridge.py
```

RealSense не должен ломать base mock path или robot camera path.

## 14. API and UI

Основные HTTP endpoints:

- `GET /api/status`
- `GET /api/mission/current`
- `GET /api/missions/state`
- `POST /api/mission/start`
- `POST /api/missions/run`
- `POST /api/mission/pause`
- `POST /api/mission/resume`
- `POST /api/mission/abort`
- `POST /api/mode/manual/take`
- `POST /api/mode/manual/release`
- `POST /api/mode/estop`
- `POST /api/mode/reset-estop`
- `POST /api/teleop/cmd`
- `POST /api/robot/action`
- `GET /stream/camera`

WebSockets:

- `WS /ws/telemetry`
- `WS /ws/events`

UI находится в `src/web/` и не использует frontend build system.

## 15. Tests

Hardware-free tests:

```bash
pytest
```

Tests покрывают route loading, control priority, lifecycle behavior, API smoke flow, report building, mock adapter, Go2 adapter boundaries, RealSense service behavior и sensor bridge helpers.

ROS build и runtime нужно отдельно проверять на Ubuntu 20.04 с ROS 2 Foxy.

## 16. Краткий итог

Текущая архитектура:

```text
FastAPI app + dashboard
+ control/safety core
+ scripted route executor
+ adapter boundary
+ telemetry/camera streaming
+ storage/reporting
+ optional ROS 2 Foxy navigation layer
```

Главное инженерное правило: не смешивать слои. Python app должен оставаться runnable сам по себе, ROS stack должен владеть SDK только через `go2_bridge`, а mock mode должен всегда работать без hardware.
