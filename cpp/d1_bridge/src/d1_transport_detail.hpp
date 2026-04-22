#pragma once

#include <cstdint>
#include <string>

#include "d1_types.hpp"

namespace d1::detail {

struct FeedbackParseResult {
    ArmStatus status{};
    bool parsed{false};
    std::string error_message;
};

FeedbackParseResult parse_arm_feedback_json(
    const std::string& payload,
    const ArmStatus& previous,
    std::int64_t now_ms);

JointState apply_joint_freshness(
    const JointState& cached,
    std::int64_t last_joint_msg_ms,
    std::int64_t stale_timeout_ms,
    std::int64_t now_ms);

ArmStatus apply_status_freshness(
    const ArmStatus& cached,
    std::int64_t last_joint_msg_ms,
    std::int64_t last_status_msg_ms,
    std::int64_t stale_timeout_ms,
    std::int64_t now_ms,
    bool halt_requested);

}  // namespace d1::detail
