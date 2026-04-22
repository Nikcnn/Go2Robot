# Build and Environment Setup

This project targets Ubuntu 20.04, Python 3.8, and ROS 2 Foxy.

There are three primary build paths:
- **Python App**: Core FastAPI app and dashboard.
- **D1 Bridge**: C++17 daemon for the Unitree D1 arm.
- **ROS 2 Layer**: ROS 2 Foxy workspace for navigation.

## 1. Python 3.8 App Setup

```bash
python3.8 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run mock mode:
```bash
python3 -m src.main --config config/app_config.yaml
```

## 2. D1 Bridge Build (C++17)

The D1 bridge requires CMake 3.10+ and a C++17 compiler.

```bash
cmake -S cpp/d1_bridge -B build/d1_bridge -DCMAKE_BUILD_TYPE=Release
cmake --build build/d1_bridge -j
```

### D1 SDK Dependencies (Optional)
To enable the official Unitree SDK2 DDS backend, provide the SDK root:
```bash
cmake -S cpp/d1_bridge -B build/d1_bridge \
  -DCMAKE_BUILD_TYPE=Release \
  -DD1_SDK_MSG_ROOT=/path/to/d1_sdk
cmake --build build/d1_bridge -j
```

### Running the Bridge
Mock mode (no hardware required):
```bash
./build/d1_bridge/d1_bridge --mock --socket /tmp/d1_bridge.sock
```

Official backend (requires Ubuntu 20.04 and D1 arm):
```bash
./build/d1_bridge/d1_bridge --interface eth0 --socket /run/d1_bridge.sock
```

### Environment Variables
- `D1_BRIDGE_SOCKET`: Path to the D1 bridge UNIX socket (default: `/run/d1_bridge.sock`).

## 3. ROS 2 Foxy System Packages

Install ROS 2 Foxy on Ubuntu 20.04:
```bash
sudo apt update
sudo apt install \
  python3-colcon-common-extensions \
  ros-foxy-navigation2 \
  ros-foxy-nav2-bringup \
  ros-foxy-rmw-cyclonedds-cpp
```

## 4. ROS 2 Workspace Build

```bash
cd ros_ws
source /opt/ros/foxy/setup.bash
colcon build --symlink-install
source install/setup.bash
export GO2_OPERATOR_APP_ROOT=$(pwd)/..
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
```

## 5. Process Boundary Rules

- **DDS Ownership**: Only one process should own the Unitree SDK DDS `ChannelFactory`.
- **Hybrid Runs**: Run the Python app in `mock` mode if `go2_bridge` owns the Go2 SDK.
- **D1 Bridge**: The C++ bridge owns the D1 SDK feedback; the Python app acts as a client.

## Validation

- Hardware-free testing: `pytest` and `d1_bridge --mock`.
- Runtime validation: Requires Ubuntu 20.04 for ROS 2 and real D1/Go2 hardware.
