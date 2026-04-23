# Go2 & D1 Quickstart

Use Ubuntu 20.04 and Python 3.8 for deployment. Use ROS 2 Foxy for navigation.

## 1. Quick Start (Mock Mode)

```bash
# Terminal 1: Python App
python3 -m src.main --config config/app_config.yaml

# Terminal 2: D1 Bridge (Mock)
./build/d1_bridge/d1_bridge --mock --socket /tmp/d1_bridge.sock
```

Open: `http://127.0.0.1:8000/`

## 2. Operator Workflow

The dashboard provides a dark-mode interface for both the Go2 robot and the D1 arm.

### Setup & Robot Check
1. Go to the **Setup** tab and press **Check system**.
2. Verify "Robot: Connected" (Go2) and "D1 Bridge: Online".

### D1 Arm Control & Monitoring
1. Switch to the **D1 Arm** tab.
2. Monitor real-time joint angles (q), velocities (dq), and torques (tau).
3. **Motion Enable**: Press **Enable Motion** to allow real joint commands (requires bridge-side enablement).
4. **Joint Control**: Use the sliders or input fields to send joint angle commands.
5. **Zero Arm**: Press **Zero Arm** to return the arm to its home position.
6. **Stop / Halt**: Use **Stop / Halt** if the bridge reports an error or if immediate motion cessation is needed.

### Go2 Mapping & Navigation
1. **Mapping**: Go to the **Mapping** tab, enter a name, and press **Start mapping**. Walk the robot around, then press **Save map**.
2. **Waypoints**: In the **Waypoints** tab, create a new route and add points from the current robot pose.
3. **Navigation**: In the **Navigation** tab, start the ROS stack and run your saved route.

### Sensors
- Use the **Sensors** tab to toggle between the built-in camera and optional RealSense views.
- The lidar card shows the status of the `/scan` source.

## 3. Real Hardware Bring-up

### Go2 Robot
```bash
python3 -m src.main --config config/app_config.go2.enp0s20f0u1c2.yaml
```

### D1 Arm
```bash
# Requires Ubuntu 20.04 and D1 connected via Ethernet
./build/d1_bridge/d1_bridge --interface eth0 --socket /run/d1_bridge.sock
```

## 4. Safety & Limits

- **ESTOP**: Always visible at the top. Halts all Go2 motion and triggers D1 software halt.
- **D1 Safety**: Real motion requires explicit bridge + app interlocks. Command validation ensures values are within joint limits.
- **Manual Takeover**: Pauses any active Go2 mission.
- **DDS Ownership**: Ensure only one process owns the Go2 SDK `ChannelFactory`.
