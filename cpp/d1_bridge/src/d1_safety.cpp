#include "d1_safety.hpp"

namespace d1 {

D1Safety::D1Safety(std::int64_t watchdog_timeout_ms)
    : watchdog_timeout_ms_(watchdog_timeout_ms),
      last_poll_ok_ms_(0) {}

void D1Safety::note_poll_success(std::int64_t now_ms) {
    std::lock_guard<std::mutex> lock(mutex_);
    last_poll_ok_ms_ = now_ms;
    if (watchdog_expired_) {
        watchdog_expired_ = false;
        record_transition_locked("D1 poll watchdog recovered");
    }
}

void D1Safety::note_poll_failure(const std::string& message, std::int64_t /*now_ms*/) {
    std::lock_guard<std::mutex> lock(mutex_);
    if (message != last_failure_message_) {
        last_failure_message_ = message;
        record_transition_locked("D1 poll failure: " + message);
    }
}

bool D1Safety::update_watchdog(std::int64_t now_ms) {
    std::lock_guard<std::mutex> lock(mutex_);
    const bool expired = last_poll_ok_ms_ <= 0 || (now_ms - last_poll_ok_ms_) > watchdog_timeout_ms_;
    if (expired != watchdog_expired_) {
        watchdog_expired_ = expired;
        record_transition_locked(expired ? "D1 poll watchdog expired" : "D1 poll watchdog healthy");
    }
    return watchdog_expired_;
}

void D1Safety::request_halt(const std::string& reason) {
    std::lock_guard<std::mutex> lock(mutex_);
    if (!halt_requested_) {
        halt_requested_ = true;
        record_transition_locked("D1 halt requested: " + reason);
    }
}

void D1Safety::clear_halt(const std::string& reason) {
    std::lock_guard<std::mutex> lock(mutex_);
    if (!halt_requested_) {
        return;
    }
    halt_requested_ = false;
    record_transition_locked("D1 halt cleared: " + reason);
}

void D1Safety::set_estop(bool estop) {
    std::lock_guard<std::mutex> lock(mutex_);
    if (estop_ == estop) {
        return;
    }
    estop_ = estop;
    record_transition_locked(estop ? "D1 ESTOP reported by transport" : "D1 ESTOP cleared by transport");
}

bool D1Safety::halt_requested() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return halt_requested_;
}

bool D1Safety::estop() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return estop_;
}

bool D1Safety::watchdog_expired() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return watchdog_expired_;
}

bool D1Safety::can_publish_motion() const {
    return false;
}

SafetySnapshot D1Safety::snapshot() const {
    std::lock_guard<std::mutex> lock(mutex_);
    SafetySnapshot snapshot;
    snapshot.halt_requested = halt_requested_;
    snapshot.estop = estop_;
    snapshot.watchdog_expired = watchdog_expired_;
    snapshot.dry_run_only = true;
    snapshot.last_poll_ok_ms = last_poll_ok_ms_;
    snapshot.last_failure_message = last_failure_message_;
    return snapshot;
}

std::optional<std::string> D1Safety::consume_transition_message() {
    std::lock_guard<std::mutex> lock(mutex_);
    auto message = transition_message_;
    transition_message_.reset();
    return message;
}

void D1Safety::record_transition_locked(const std::string& message) {
    transition_message_ = message;
}

}  // namespace d1
