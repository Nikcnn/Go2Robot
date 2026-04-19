# Go2 Quickstart

Use this only when the robot is already connected by LAN on `enp0s20f0u1c2`.

## 1. Install

```bash
cd /home/nikcnn/Go2Robot/Go2_MVP
pip install -r requirements.txt
```

If `unitree_sdk2py` is not installed yet, install it first. The server will fail fast if the SDK is missing in `go2` mode.

## 2. Start the server

```bash
python -m src.main --config config/app_config.go2.enp0s20f0u1c2.yaml
```

Open:

```text
http://127.0.0.1:8000/
```

The dashboard now shows:

- live robot camera frames
- battery percent, voltage/current, and cycle count
- richer fault text instead of only raw `error_code`

## 3. Run the short route

In the dashboard, keep the route field as:

```text
short_walk_20cm
```

Then press `Start`.

You can also run it by API:

```bash
curl -X POST http://127.0.0.1:8000/api/mission/start \
  -H "Content-Type: application/json" \
  -d '{"route_id":"short_walk_20cm"}'
```

## 4. What the route does

- Moves forward about 20 cm
- Takes a checkpoint snapshot
- Turns right
- Moves forward about 20 cm
- Takes a second checkpoint snapshot
- Moves back about 20 cm
- Turns around
- Stops

## 5. Important limitation

This MVP does not have a real "lie down" action. The final step is `stop`.

If you want a true lie-down or sit-down behavior, that needs a new robot action in the adapter and control layer.

## 6. Real robot activation flow

- Manual takeover now uses a posture-preserving stop and no longer calls `Damp()`.
- `ESTOP` still uses passive damping. After `Reset ESTOP`, activate the robot before moving again:

```bash
curl -X POST http://127.0.0.1:8000/api/robot/activate
```

- The dashboard now exposes the same action as `Activate Robot`.
