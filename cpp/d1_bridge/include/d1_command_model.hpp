#pragma once

#include <array>
#include <cstddef>
#include <string>
#include <utility>

namespace d1 {

inline constexpr std::size_t kD1StateJointCount = 6;
inline constexpr std::size_t kD1CommandJointCount = 7;

namespace error {
inline constexpr int kMalformedRequest = 1001;
inline constexpr int kBadPayload = 1002;

inline constexpr int kSdkUnavailable = 901;
inline constexpr int kTransportInitFailed = 902;
inline constexpr int kWatchdogExpired = 903;
inline constexpr int kOwnershipDenied = 904;
inline constexpr int kPublisherUnavailable = 905;

inline constexpr int kJointIdOutOfRange = 1101;
inline constexpr int kNonFiniteValue = 1102;
inline constexpr int kAngleOutOfBounds = 1103;
inline constexpr int kDeltaTooLarge = 1104;
inline constexpr int kRateLimited = 1105;
inline constexpr int kMissingFreshState = 1106;

inline constexpr int kMotionDisabledByConfig = 1201;
inline constexpr int kMotionNotEnabled = 1202;
inline constexpr int kArmDisconnected = 1203;
inline constexpr int kEstopActive = 1204;
inline constexpr int kControllerLockMissing = 1205;
inline constexpr int kDryRunOnly = 1206;
}  // namespace error

enum class D1CommandType {
    Halt,
    EnableMotion,
    DisableMotion,
    SetJointAngle,
    SetMultiJointAngle,
    ZeroArm,
};

struct JointAngleLimit {
    double min_deg{-180.0};
    double max_deg{180.0};
};

struct D1CommandValidation {
    std::array<JointAngleLimit, kD1CommandJointCount> joint_limits{};
    double max_joint_delta_deg{20.0};
    double command_rate_limit_hz{10.0};
};

struct D1Command {
    D1CommandType type{D1CommandType::Halt};
    int joint_id{0};
    double angle_deg{0.0};
    int delay_ms{0};
    int mode{1};
    std::array<double, kD1CommandJointCount> angles_deg{};
    std::size_t angle_count{0};
};

struct D1CommandResult {
    bool ok{false};
    int error_code{0};
    std::string error_kind{"unknown"};
    std::string message;
    bool accepted{false};
    bool motion_enabled{false};
    bool dry_run_only{true};
};

inline D1CommandValidation default_command_validation() {
    D1CommandValidation config;
    config.max_joint_delta_deg = 20.0;
    config.command_rate_limit_hz = 10.0;
    for (auto& limit : config.joint_limits) {
        limit.min_deg = -180.0;
        limit.max_deg = 180.0;
    }
    return config;
}

inline D1CommandResult make_command_result(
    bool ok,
    int error_code,
    std::string error_kind,
    std::string message,
    bool accepted,
    bool motion_enabled,
    bool dry_run_only) {
    D1CommandResult result;
    result.ok = ok;
    result.error_code = error_code;
    result.error_kind = std::move(error_kind);
    result.message = std::move(message);
    result.accepted = accepted;
    result.motion_enabled = motion_enabled;
    result.dry_run_only = dry_run_only;
    return result;
}

}  // namespace d1
