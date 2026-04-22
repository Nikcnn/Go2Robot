#pragma once

#include <atomic>
#include <cstddef>
#include <deque>
#include <mutex>
#include <string>
#include <thread>

#include "d1_safety.hpp"
#include "d1_transport.hpp"
#include "d1_types.hpp"

namespace d1 {

struct D1BridgeServerOptions {
    std::string socket_path{"/run/d1_bridge.sock"};
    bool mock_mode{false};
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
    std::int64_t poll_period_ms{100};
    std::int64_t watchdog_timeout_ms{1000};
    std::size_t max_dry_run_queue{32};
};

class D1BridgeServer {
public:
    explicit D1BridgeServer(D1BridgeServerOptions options = {});
    ~D1BridgeServer();

    bool run();
    void stop();
    std::string handle_request_for_test(const std::string& request_text);

private:
    static D1TransportOptions make_transport_options(const D1BridgeServerOptions& options);
    bool setup_socket();
    void cleanup_socket();
    void poll_loop();
    void handle_client(int client_fd);
    std::string handle_request(const std::string& request_text);

    D1BridgeServerOptions options_;
    D1Transport transport_;
    D1Safety safety_;
    std::atomic<bool> running_{false};
    int server_fd_{-1};
    std::mutex transport_mutex_;
    mutable std::mutex state_mutex_;
    JointState latest_joint_state_{};
    ArmStatus latest_status_{};
    std::deque<std::string> dry_run_queue_;
    std::thread poll_thread_;
};

}  // namespace d1
