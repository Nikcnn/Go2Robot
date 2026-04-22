#pragma once

#include <array>
#include <chrono>
#include <cstdint>
#include <string>

#include "d1_command_model.hpp"

namespace d1 {

struct JointState {
    std::array<double, kD1StateJointCount> q{};
    std::array<double, kD1StateJointCount> dq{};
    std::array<double, kD1StateJointCount> tau{};
    bool valid{false};
    std::int64_t stamp_ms{0};
};

struct ArmStatus {
    bool connected{false};
    bool estop{false};
    bool motion_enabled{false};
    bool dry_run_only{true};
    bool controller_lock_held{false};
    int error_code{0};
    std::string error_kind;
    std::string mode{"readonly"};
    std::string backend{"unavailable"};
    std::string controller_owner{"d1_bridge"};
    std::int64_t last_update_ms{0};
    std::string last_error;
    std::string last_error_message;
};

inline std::int64_t now_ms() {
    using namespace std::chrono;
    return duration_cast<milliseconds>(system_clock::now().time_since_epoch()).count();
}

}  // namespace d1
