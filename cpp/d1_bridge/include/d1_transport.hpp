#pragma once

#include <memory>
#include <string>

#include "d1_command_model.hpp"
#include "d1_types.hpp"

namespace d1 {

class D1TransportBackend;

struct D1TransportOptions {
    bool mock_mode{false};
    std::string endpoint{"local"};
    std::string interface_name;
    std::string servo_topic{"current_servo_angle"};
    std::string feedback_topic{"rt/arm_Feedback"};
    std::string feedback_topic_fallback{"arm_Feedback"};
    std::string command_topic{"rt/arm_Command"};
    bool enable_motion{false};
    bool dry_run_fallback{true};
    double max_joint_delta_deg{20.0};
    double command_rate_limit_hz{10.0};
    double joint_min_deg{-180.0};
    double joint_max_deg{180.0};
    std::int64_t stale_timeout_ms{1500};
};

class D1Transport {
public:
    explicit D1Transport(D1TransportOptions options = {});
    ~D1Transport();

    bool connect();
    void close();
    bool is_connected() const;
    JointState read_joint_state();
    ArmStatus read_status();
    D1CommandResult set_motion_enabled(bool enabled);
    D1CommandResult send_command(const D1Command& command);
    bool stop_motion();

private:
    D1TransportOptions options_;
    std::unique_ptr<D1TransportBackend> backend_;
};

}  // namespace d1
