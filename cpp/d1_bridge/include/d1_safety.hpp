#pragma once

#include <cstdint>
#include <mutex>
#include <optional>
#include <string>

namespace d1 {

struct SafetySnapshot {
    bool halt_requested{false};
    bool estop{false};
    bool watchdog_expired{false};
    bool dry_run_only{true};
    std::int64_t last_poll_ok_ms{0};
    std::string last_failure_message;
};

class D1Safety {
public:
    explicit D1Safety(std::int64_t watchdog_timeout_ms);

    void note_poll_success(std::int64_t now_ms);
    void note_poll_failure(const std::string& message, std::int64_t now_ms);
    bool update_watchdog(std::int64_t now_ms);

    void request_halt(const std::string& reason);
    void clear_halt(const std::string& reason);
    void set_estop(bool estop);

    bool halt_requested() const;
    bool estop() const;
    bool watchdog_expired() const;
    bool can_publish_motion() const;
    SafetySnapshot snapshot() const;
    std::optional<std::string> consume_transition_message();

private:
    void record_transition_locked(const std::string& message);

    std::int64_t watchdog_timeout_ms_{0};
    std::int64_t last_poll_ok_ms_{0};
    bool halt_requested_{false};
    bool estop_{false};
    bool watchdog_expired_{false};
    std::string last_failure_message_;
    std::optional<std::string> transition_message_;
    mutable std::mutex mutex_;
};

}  // namespace d1
