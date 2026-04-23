# D1 Bridge Setup

This repository keeps the D1 boundary unchanged:

```text
Python app -> D1Client -> UNIX socket -> cpp/d1_bridge -> Unitree SDK2 DDS
```

The bridge daemon in `cpp/d1_bridge/` now provides:

- `MockBackend` for hardware-free bring-up
- `DDSBackend` for real Unitree SDK2 DDS subscriptions
- real feedback reads from `current_servo_angle` and `rt/arm_Feedback` with `arm_Feedback` fallback
- a typed command layer that publishes Unitree `ArmString_` JSON payloads to `rt/arm_Command`
- explicit ownership so the bridge is the only in-process DDS / `ChannelFactory` owner
- hard motion gating, command validation, and socket-level machine-readable errors

## New Code Locations

```text
cpp/d1_bridge/              C++17 local bridge daemon
src/integrations/d1_client.py
src/services/d1_service.py
src/api_d1.py
src/web/                    D1 Arm operator tab in the existing dashboard
systemd/d1-bridge.service
tests/test_d1_client.py
tests/test_d1_api.py
tests/test_d1_service.py
```

## Build The C++ Bridge

From the repository root:

```bash
cmake -S cpp/d1_bridge -B build/d1_bridge -DCMAKE_BUILD_TYPE=Release
cmake --build build/d1_bridge -j
```

The bridge always builds in mock / dry-run fallback mode.

To enable the official Unitree SDK2 DDS backend, the build machine must provide:

- `unitree_sdk2` via CMake config, usually from `/opt/unitree_robotics` or another path on `CMAKE_PREFIX_PATH`
- D1 arm message headers from `d1_sdk.zip`, specifically `msg/ArmString_.hpp` and `msg/PubServoInfo_.hpp`

Example when the D1 msg headers live outside the default include paths:

```bash
cmake -S cpp/d1_bridge -B build/d1_bridge \
  -DCMAKE_BUILD_TYPE=Release \
  -DD1_SDK_MSG_ROOT=/path/to/d1_sdk
cmake --build build/d1_bridge -j
ctest --test-dir build/d1_bridge --output-on-failure
```

If `unitree_sdk2` or the D1 msg headers are absent, the bridge still compiles and the DDS backend degrades cleanly to an unavailable dry-run path while `--mock` remains fully supported.

## Run The Bridge Manually

Mock mode is the easiest safe bring-up path because it keeps the bridge online without any vendor SDK calls:

```bash
./build/d1_bridge/d1_bridge --mock --socket /tmp/d1_bridge.sock
```

For DDS feedback bring-up on the onboard PC:

```bash
./build/d1_bridge/d1_bridge \
  --interface enp0s20f0u1c2 \
  --servo-topic current_servo_angle \
  --feedback-topic rt/arm_Feedback \
  --feedback-topic-fallback arm_Feedback
```

For DDS feedback plus explicitly allowed motion publishing:

```bash
./build/d1_bridge/d1_bridge \
  --interface enp0s20f0u1c2 \
  --feedback-topic rt/arm_Feedback \
  --feedback-topic-fallback arm_Feedback \
  --command-topic rt/arm_Command \
  --enable-motion \
  --max-joint-delta-deg 20 \
  --command-rate-limit-hz 10 \
  --joint-min-deg -180 \
  --joint-max-deg 180
```

The default socket path used by both the bridge and the Python app is:

```text
/run/d1_bridge.sock
```

To run the Python app against a non-default socket during development:

```bash
export D1_BRIDGE_SOCKET=/tmp/d1_bridge.sock
python3 -m src.main --config config/app_config.yaml
```

Without `--mock`, the bridge selects the DDS backend. It subscribes to:

- `current_servo_angle` using `unitree_arm::msg::dds_::PubServoInfo_`
- `rt/arm_Feedback` using `unitree_arm::msg::dds_::ArmString_`
- optional documented compatibility fallback: `arm_Feedback`

When the publisher is available, it publishes typed `ArmString_` command payloads to:

- `rt/arm_Command`

The bridge uses `ChannelFactory::Instance()->Init(0)` or `Init(0, "<nic_name>")` depending on whether `--interface` is provided.

## Ownership Model

- The Python app never talks to Unitree DDS directly.
- Only the bridge initializes `ChannelFactory`.
- The bridge acquires explicit DDS ownership as `d1_bridge` and logs that ownership at startup.
- If a second in-process DDS owner is attempted, the backend reports an ownership error instead of silently double-initializing.

## Motion Safety

Real D1 motion is still safety-gated and OFF by default.

The bridge rejects motion commands unless all of the following are true:

- the bridge was started with `--enable-motion` or `D1_ENABLE_MOTION=true`
- the Python app config allows it with `d1.enable_motion: true`
- DDS feedback is connected
- ESTOP is clear
- the bridge holds the controller ownership lock
- the operator/API has explicitly called `enable_motion`
- command values pass validation

Validation includes:

- joint id range check
- finite numeric values only
- configurable joint bounds
- configurable maximum delta from the latest servo snapshot
- configurable command rate limiting

`stop` / `halt` stays available even when motion enable is off or validation rejects a motion command.

## Socket Protocol

The existing status polling remains:

- `ping`
- `status`
- `joints`
- `stop`
- `dry_run`

The bridge now also accepts:

- `halt`
- `enable_motion`
- `disable_motion`
- `set_joint_angle`
- `set_multi_joint_angle`
- `zero_arm`

Motion command errors return machine-readable fields including `error_code`, `error_kind`, and `accepted`.

## FastAPI And Web UI

Start the existing Python app the same way as before:

```bash
python3 -m src.main --config config/app_config.yaml
```

Open:

```text
http://127.0.0.1:8000/
```

The **D1 Arm** tab shows:

- bridge online/offline
- D1 connected/disconnected
- ESTOP state
- motion enabled vs blocked
- dry-run vs real command path
- controller lock state
- mode, error code, last error, and last update
- a six-joint `q` / `dq` / `tau` table

The operator actions are explicit and never auto-fire:

- `Refresh`
- `Enable motion`
- `Disable motion`
- `Zero arm`
- `Stop / Halt`
- `Send Dry-Run`

`Refresh` is read-only. `Send Dry-Run` submits a safe example payload for validation / queueing only. It does not move the arm.

## Systemd

Install the provided service file as a system unit:

```bash
sudo cp systemd/d1-bridge.service /etc/systemd/system/d1-bridge.service
sudo systemctl daemon-reload
sudo systemctl enable --now d1-bridge.service
sudo systemctl status d1-bridge.service
```

The unit runs the bridge as user `unitree`, targets `/run/d1_bridge.sock`, and defaults `D1_ENABLE_MOTION=false`.

Notes:

- The service is configured for the exact `/run/d1_bridge.sock` path requested here.
- On tighter systems, writing directly under `/run` as `unitree` may require review of the provided capability settings or an override to a user-runtime socket path.
- No `go2-web.service` file was added here. Keep the existing Python app service flow and only export `D1_BRIDGE_SOCKET` if you intentionally override the default socket path.

## Known Limitation

- The bridge keeps the operator-facing state model 6-wide.
- `servo6_data_` / gripper is retained internally for command compatibility, but the Python/UI side still exposes only six joints.
- Real Ubuntu 20.04 hardware validation is still required for DDS runtime behavior and arm motion before field use.
