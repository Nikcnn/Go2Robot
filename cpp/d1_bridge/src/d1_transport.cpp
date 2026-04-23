#include "d1_transport.hpp"

#include "d1_command_serializer.hpp"
#include "d1_transport_detail.hpp"

#include <algorithm>
#include <atomic>
#include <cctype>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <functional>
#include <iomanip>
#include <iostream>
#include <limits>
#include <memory>
#include <mutex>
#include <optional>
#include <sstream>
#include <string>
#include <utility>

#ifndef D1_TRANSPORT_HAS_UNITREE_SDK
#define D1_TRANSPORT_HAS_UNITREE_SDK 0
#endif

#if D1_TRANSPORT_HAS_UNITREE_SDK
#include <unitree/robot/channel/channel_factory.hpp>
#include <unitree/robot/channel/channel_publisher.hpp>
#include <unitree/robot/channel/channel_subscriber.hpp>

#include "msg/ArmString_.hpp"
#include "msg/PubServoInfo_.hpp"
#endif

namespace d1 {

class D1TransportBackend {
public:
    virtual ~D1TransportBackend() = default;

    virtual bool connect() = 0;
    virtual void close() = 0;
    virtual bool is_connected() const = 0;
    virtual JointState read_joint_state() = 0;
    virtual ArmStatus read_status() = 0;
    virtual D1CommandResult set_motion_enabled(bool enabled) = 0;
    virtual D1CommandResult send_command(const D1Command& command) = 0;
    virtual bool stop_motion() = 0;
};

namespace {

void log_line(const char* level, const std::string& message) {
    std::cerr << "[d1_transport][" << level << "] " << message << std::endl;
}

std::string trim_copy(std::string text) {
    while (!text.empty() && std::isspace(static_cast<unsigned char>(text.front())) != 0) {
        text.erase(text.begin());
    }
    while (!text.empty() && std::isspace(static_cast<unsigned char>(text.back())) != 0) {
        text.pop_back();
    }
    return text;
}

std::optional<std::size_t> find_json_key(const std::string& text, const std::string& key) {
    const std::string needle = "\"" + key + "\"";
    const auto pos = text.find(needle);
    if (pos == std::string::npos) {
        return std::nullopt;
    }
    return pos + needle.size();
}

std::optional<std::string> extract_string_field(const std::string& text, const std::string& key) {
    const auto key_end = find_json_key(text, key);
    if (!key_end) {
        return std::nullopt;
    }

    std::size_t cursor = *key_end;
    while (cursor < text.size() && std::isspace(static_cast<unsigned char>(text[cursor])) != 0) {
        ++cursor;
    }
    if (cursor >= text.size() || text[cursor] != ':') {
        return std::nullopt;
    }
    ++cursor;
    while (cursor < text.size() && std::isspace(static_cast<unsigned char>(text[cursor])) != 0) {
        ++cursor;
    }
    if (cursor >= text.size() || text[cursor] != '"') {
        return std::nullopt;
    }
    ++cursor;

    std::string value;
    bool escaped = false;
    while (cursor < text.size()) {
        const char ch = text[cursor++];
        if (escaped) {
            switch (ch) {
                case '"':
                case '\\':
                case '/':
                    value.push_back(ch);
                    break;
                case 'n':
                    value.push_back('\n');
                    break;
                case 'r':
                    value.push_back('\r');
                    break;
                case 't':
                    value.push_back('\t');
                    break;
                default:
                    value.push_back(ch);
                    break;
            }
            escaped = false;
            continue;
        }
        if (ch == '\\') {
            escaped = true;
            continue;
        }
        if (ch == '"') {
            return value;
        }
        value.push_back(ch);
    }
    return std::nullopt;
}

std::optional<std::string> extract_object_field(const std::string& text, const std::string& key) {
    const auto key_end = find_json_key(text, key);
    if (!key_end) {
        return std::nullopt;
    }

    std::size_t cursor = *key_end;
    while (cursor < text.size() && std::isspace(static_cast<unsigned char>(text[cursor])) != 0) {
        ++cursor;
    }
    if (cursor >= text.size() || text[cursor] != ':') {
        return std::nullopt;
    }
    ++cursor;
    while (cursor < text.size() && std::isspace(static_cast<unsigned char>(text[cursor])) != 0) {
        ++cursor;
    }
    if (cursor >= text.size() || text[cursor] != '{') {
        return std::nullopt;
    }

    const auto start = cursor;
    int depth = 0;
    bool in_string = false;
    bool escaped = false;
    while (cursor < text.size()) {
        const char ch = text[cursor];
        if (in_string) {
            if (escaped) {
                escaped = false;
            } else if (ch == '\\') {
                escaped = true;
            } else if (ch == '"') {
                in_string = false;
            }
        } else if (ch == '"') {
            in_string = true;
        } else if (ch == '{') {
            ++depth;
        } else if (ch == '}') {
            --depth;
            if (depth == 0) {
                return text.substr(start, cursor - start + 1);
            }
        }
        ++cursor;
    }

    return std::nullopt;
}

std::optional<int> extract_int_field(const std::string& text, const std::string& key) {
    const auto key_end = find_json_key(text, key);
    if (!key_end) {
        return std::nullopt;
    }

    std::size_t cursor = *key_end;
    while (cursor < text.size() && std::isspace(static_cast<unsigned char>(text[cursor])) != 0) {
        ++cursor;
    }
    if (cursor >= text.size() || text[cursor] != ':') {
        return std::nullopt;
    }
    ++cursor;
    while (cursor < text.size() && std::isspace(static_cast<unsigned char>(text[cursor])) != 0) {
        ++cursor;
    }
    if (cursor >= text.size()) {
        return std::nullopt;
    }

    if (text[cursor] == '"') {
        const auto value = extract_string_field(text, key);
        if (!value) {
            return std::nullopt;
        }
        try {
            return std::stoi(*value);
        } catch (...) {
            return std::nullopt;
        }
    }

    const auto start = cursor;
    if (text[cursor] == '-') {
        ++cursor;
    }
    while (cursor < text.size() && std::isdigit(static_cast<unsigned char>(text[cursor])) != 0) {
        ++cursor;
    }
    if (start == cursor) {
        return std::nullopt;
    }
    try {
        return std::stoi(text.substr(start, cursor - start));
    } catch (...) {
        return std::nullopt;
    }
}

std::optional<double> extract_double_field(const std::string& text, const std::string& key) {
    const auto key_end = find_json_key(text, key);
    if (!key_end) {
        return std::nullopt;
    }

    std::size_t cursor = *key_end;
    while (cursor < text.size() && std::isspace(static_cast<unsigned char>(text[cursor])) != 0) {
        ++cursor;
    }
    if (cursor >= text.size() || text[cursor] != ':') {
        return std::nullopt;
    }
    ++cursor;
    while (cursor < text.size() && std::isspace(static_cast<unsigned char>(text[cursor])) != 0) {
        ++cursor;
    }
    if (cursor >= text.size()) {
        return std::nullopt;
    }

    if (text[cursor] == '"') {
        const auto value = extract_string_field(text, key);
        if (!value) {
            return std::nullopt;
        }
        try {
            return std::stod(*value);
        } catch (...) {
            return std::nullopt;
        }
    }

    char* end = nullptr;
    const double value = std::strtod(text.c_str() + cursor, &end);
    if (end == text.c_str() + cursor) {
        return std::nullopt;
    }
    return value;
}

std::optional<bool> extract_bool_field(const std::string& text, const std::string& key) {
    const auto key_end = find_json_key(text, key);
    if (!key_end) {
        return std::nullopt;
    }

    std::size_t cursor = *key_end;
    while (cursor < text.size() && std::isspace(static_cast<unsigned char>(text[cursor])) != 0) {
        ++cursor;
    }
    if (cursor >= text.size() || text[cursor] != ':') {
        return std::nullopt;
    }
    ++cursor;
    while (cursor < text.size() && std::isspace(static_cast<unsigned char>(text[cursor])) != 0) {
        ++cursor;
    }
    if (cursor >= text.size()) {
        return std::nullopt;
    }

    if (text.compare(cursor, 4, "true") == 0) {
        return true;
    }
    if (text.compare(cursor, 5, "false") == 0) {
        return false;
    }
    if (text[cursor] == '"') {
        const auto value = extract_string_field(text, key);
        if (!value) {
            return std::nullopt;
        }
        if (*value == "true" || *value == "1") {
            return true;
        }
        if (*value == "false" || *value == "0") {
            return false;
        }
        return std::nullopt;
    }
    if (std::isdigit(static_cast<unsigned char>(text[cursor])) != 0 || text[cursor] == '-') {
        const auto value = extract_int_field(text, key);
        if (!value) {
            return std::nullopt;
        }
        return *value != 0;
    }

    return std::nullopt;
}

std::optional<int> extract_status_like_field(const std::string& text, const std::string& key) {
    if (const auto number = extract_int_field(text, key)) {
        return number;
    }
    if (const auto boolean = extract_bool_field(text, key)) {
        return *boolean ? 1 : 0;
    }
    return std::nullopt;
}

std::int64_t max_update_time(std::int64_t lhs, std::int64_t rhs, std::int64_t fallback) {
    return std::max(fallback, std::max(lhs, rhs));
}

void set_status_error_fields(ArmStatus& status, const std::string& message, int error_code, const std::string& error_kind) {
    status.error_code = error_code;
    status.error_kind = error_kind;
    status.last_error = message;
    status.last_error_message = message;
    status.last_update_ms = now_ms();
}

void clear_status_error_fields(ArmStatus& status) {
    status.error_code = 0;
    status.error_kind.clear();
    status.last_error.clear();
    status.last_error_message.clear();
}

bool is_finite_number(double value) {
    return std::isfinite(value) != 0;
}

std::int64_t min_command_spacing_ms(double command_rate_limit_hz) {
    if (!is_finite_number(command_rate_limit_hz) || command_rate_limit_hz <= 0.0) {
        return 0;
    }
    return static_cast<std::int64_t>(std::ceil(1000.0 / command_rate_limit_hz));
}

D1CommandResult precondition_error(
    int code,
    const std::string& kind,
    const std::string& message,
    bool motion_enabled,
    bool dry_run_only) {
    return make_command_result(false, code, kind, message, false, motion_enabled, dry_run_only);
}

D1CommandResult success_result(
    const std::string& message,
    bool motion_enabled,
    bool dry_run_only) {
    return make_command_result(true, 0, "", message, true, motion_enabled, dry_run_only);
}

bool validate_joint_limit(
    int joint_id,
    double angle_deg,
    const D1CommandValidation& validation,
    D1CommandResult& out_result) {
    if (joint_id < 0 || joint_id >= static_cast<int>(kD1CommandJointCount)) {
        out_result = precondition_error(
            error::kJointIdOutOfRange,
            "joint_id_out_of_range",
            "joint_id must be between 0 and 6",
            false,
            true);
        return false;
    }

    if (!is_finite_number(angle_deg)) {
        out_result = precondition_error(
            error::kNonFiniteValue,
            "non_finite_value",
            "joint angle must be finite",
            false,
            true);
        return false;
    }

    const auto& limit = validation.joint_limits[static_cast<std::size_t>(joint_id)];
    if (angle_deg < limit.min_deg || angle_deg > limit.max_deg) {
        std::ostringstream message;
        message << "joint " << joint_id << " angle " << std::fixed << std::setprecision(3) << angle_deg
                << " deg is outside configured bounds [" << limit.min_deg << ", " << limit.max_deg << "]";
        out_result = precondition_error(
            error::kAngleOutOfBounds,
            "angle_out_of_bounds",
            message.str(),
            false,
            true);
        return false;
    }

    return true;
}

bool validate_joint_delta(
    int joint_id,
    double target_angle_deg,
    const std::array<double, kD1CommandJointCount>& current_angles_deg,
    const D1CommandValidation& validation,
    D1CommandResult& out_result) {
    if (!is_finite_number(validation.max_joint_delta_deg) || validation.max_joint_delta_deg <= 0.0) {
        return true;
    }

    const double delta = std::abs(target_angle_deg - current_angles_deg[static_cast<std::size_t>(joint_id)]);
    if (delta <= validation.max_joint_delta_deg) {
        return true;
    }

    std::ostringstream message;
    message << "joint " << joint_id << " delta " << std::fixed << std::setprecision(3) << delta
            << " deg exceeds max_joint_delta_deg=" << validation.max_joint_delta_deg;
    out_result = precondition_error(
        error::kDeltaTooLarge,
        "delta_too_large",
        message.str(),
        false,
        true);
    return false;
}

#if D1_TRANSPORT_HAS_UNITREE_SDK
class ChannelFactoryGuard {
public:
    bool init(const std::string& interface_name) {
        std::lock_guard<std::mutex> lock(mutex_);
        if (initialized_) {
            if (!interface_name.empty() && !interface_name_.empty() && interface_name_ != interface_name) {
                log_line("WARN", "ChannelFactory already initialized with interface '" + interface_name_ +
                                     "', ignoring requested interface '" + interface_name + "'");
            }
            return init_ok_;
        }

        log_line("INFO", interface_name.empty()
                             ? "Initializing Unitree ChannelFactory::Instance()->Init(0)"
                             : "Initializing Unitree ChannelFactory::Instance()->Init(0, \"" + interface_name + "\")");
        try {
            if (interface_name.empty()) {
                unitree::robot::ChannelFactory::Instance()->Init(0);
            } else {
                unitree::robot::ChannelFactory::Instance()->Init(0, interface_name);
            }
            init_ok_ = true;
            interface_name_ = interface_name;
        } catch (const std::exception& exc) {
            init_ok_ = false;
            last_error_ = exc.what();
            log_line("ERROR", "Unitree ChannelFactory init failed: " + last_error_);
        } catch (...) {
            init_ok_ = false;
            last_error_ = "unknown exception";
            log_line("ERROR", "Unitree ChannelFactory init failed with an unknown exception");
        }
        initialized_ = true;
        return init_ok_;
    }

    std::string last_error() const {
        std::lock_guard<std::mutex> lock(mutex_);
        return last_error_;
    }

private:
    mutable std::mutex mutex_;
    bool initialized_{false};
    bool init_ok_{false};
    std::string interface_name_;
    std::string last_error_;
};

ChannelFactoryGuard& channel_factory_guard() {
    static ChannelFactoryGuard guard;
    return guard;
}
#endif

class DdsOwnershipGuard {
public:
    bool acquire(const std::string& owner, std::string& failure_message) {
        std::lock_guard<std::mutex> lock(mutex_);
        if (owner_.empty()) {
            owner_ = owner;
            return true;
        }
        if (owner_ == owner) {
            return true;
        }
        failure_message = "DDS ownership already held by " + owner_;
        return false;
    }

    void release(const std::string& owner) {
        std::lock_guard<std::mutex> lock(mutex_);
        if (owner_ == owner) {
            owner_.clear();
        }
    }

    std::string owner() const {
        std::lock_guard<std::mutex> lock(mutex_);
        return owner_;
    }

private:
    mutable std::mutex mutex_;
    std::string owner_;
};

DdsOwnershipGuard& dds_ownership_guard() {
    static DdsOwnershipGuard guard;
    return guard;
}

}  // namespace

namespace detail {

FeedbackParseResult parse_arm_feedback_json(
    const std::string& payload,
    const ArmStatus& previous,
    std::int64_t parsed_at_ms) {
    FeedbackParseResult result;
    result.status = previous;
    result.status.last_update_ms = parsed_at_ms;

    const std::string trimmed = trim_copy(payload);
    if (trimmed.empty()) {
        result.error_message = "D1 feedback payload is empty";
        set_status_error_fields(result.status, result.error_message, previous.error_code, previous.error_kind);
        return result;
    }

    const std::string field_source = extract_object_field(trimmed, "data").value_or(trimmed);

    const auto enable_status = extract_status_like_field(field_source, "enable_status");
    const auto power_status = extract_status_like_field(field_source, "power_status");
    const auto pow_status = extract_status_like_field(field_source, "pow_status");
    const auto error_status = extract_status_like_field(field_source, "error_status");
    const auto recv_status = extract_status_like_field(field_source, "recv_status");
    const auto exec_status = extract_status_like_field(field_source, "exec_status");
    const auto explicit_error_code = extract_int_field(field_source, "error_code");

    std::optional<bool> estop = extract_bool_field(field_source, "estop");
    if (!estop) {
        estop = extract_bool_field(field_source, "estop_status");
    }
    if (!estop) {
        estop = extract_bool_field(field_source, "emergency_stop");
    }

    bool has_known_status_field = enable_status || power_status || pow_status || error_status ||
                                  recv_status || exec_status || explicit_error_code || estop;
    std::array<std::optional<int>, kD1CommandJointCount> motor_status{};
    for (std::size_t idx = 0; idx < motor_status.size(); ++idx) {
        motor_status[idx] = extract_status_like_field(field_source, "motor" + std::to_string(idx) + "_status");
        has_known_status_field = has_known_status_field || motor_status[idx].has_value();
    }

    if (!has_known_status_field) {
        result.error_message = "D1 feedback JSON did not contain supported status fields";
        set_status_error_fields(result.status, result.error_message, previous.error_code, previous.error_kind);
        return result;
    }

    result.parsed = true;
    result.status.connected = true;
    result.status.estop = estop.value_or(false);

    int derived_error_code = 0;
    std::string status_message;
    const auto append_message = [&status_message](const std::string& fragment) {
        if (!status_message.empty()) {
            status_message += "; ";
        }
        status_message += fragment;
    };

    if (explicit_error_code) {
        derived_error_code = *explicit_error_code;
        if (derived_error_code != 0) {
            append_message("error_code=" + std::to_string(derived_error_code));
        }
    }

    const auto process_status_flag = [&](const std::optional<int>& value, const char* name, int fallback_code) {
        if (!value) {
            return;
        }
        if (*value == 1) {
            return;
        }
        if (derived_error_code == 0) {
            derived_error_code = (*value == 0) ? fallback_code : *value;
        }
        append_message(std::string(name) + "=" + std::to_string(*value));
    };

    process_status_flag(error_status, "error_status", 1);
    process_status_flag(recv_status, "recv_status", 2);
    process_status_flag(exec_status, "exec_status", 3);
    process_status_flag(power_status ? power_status : pow_status, power_status ? "power_status" : "pow_status", 4);
    process_status_flag(enable_status, "enable_status", 5);

    for (std::size_t idx = 0; idx < motor_status.size(); ++idx) {
        process_status_flag(motor_status[idx], ("motor" + std::to_string(idx) + "_status").c_str(), 20 + static_cast<int>(idx));
    }

    if (derived_error_code == 0 && result.status.estop) {
        derived_error_code = error::kEstopActive;
        append_message("estop=true");
    }

    result.status.error_code = derived_error_code;
    result.status.error_kind = derived_error_code == 0 ? "" : "feedback_fault";
    if (derived_error_code == 0) {
        clear_status_error_fields(result.status);
    } else {
        const auto message = status_message.empty() ? "D1 reported a non-ready status" : status_message;
        set_status_error_fields(result.status, message, derived_error_code, result.status.error_kind);
    }

    return result;
}

JointState apply_joint_freshness(
    const JointState& cached,
    std::int64_t last_joint_msg_ms,
    std::int64_t stale_timeout_ms,
    std::int64_t now) {
    JointState snapshot = cached;
    const bool fresh = last_joint_msg_ms > 0 && (now - last_joint_msg_ms) <= stale_timeout_ms;
    snapshot.valid = cached.valid && fresh;
    return snapshot;
}

ArmStatus apply_status_freshness(
    const ArmStatus& cached,
    std::int64_t last_joint_msg_ms,
    std::int64_t last_status_msg_ms,
    std::int64_t stale_timeout_ms,
    std::int64_t now,
    bool halt_requested) {
    ArmStatus snapshot = cached;
    const bool fresh_joint = last_joint_msg_ms > 0 && (now - last_joint_msg_ms) <= stale_timeout_ms;
    const bool fresh_status = last_status_msg_ms > 0 && (now - last_status_msg_ms) <= stale_timeout_ms;

    snapshot.connected = fresh_joint || fresh_status;
    snapshot.last_update_ms = max_update_time(last_joint_msg_ms, last_status_msg_ms, cached.last_update_ms);

    if (halt_requested) {
        snapshot.motion_enabled = false;
        snapshot.dry_run_only = true;
        if (snapshot.last_error.empty()) {
            set_status_error_fields(
                snapshot,
                "software halt requested; motion commands blocked until re-enabled",
                0,
                "");
        }
    } else if (!snapshot.connected && snapshot.last_error.empty()) {
        set_status_error_fields(snapshot, "D1 feedback stale", snapshot.error_code, snapshot.error_kind);
    }

    return snapshot;
}

}  // namespace detail

namespace {

#if D1_TRANSPORT_HAS_UNITREE_SDK
using D1ArmStringMessage = unitree_arm::msg::dds_::ArmString_;
using D1ServoInfoMessage = unitree_arm::msg::dds_::PubServoInfo_;
using D1ArmFeedbackSubscriber = unitree::robot::ChannelSubscriber<D1ArmStringMessage>;
using D1ServoInfoSubscriber = unitree::robot::ChannelSubscriber<D1ServoInfoMessage>;
using D1ArmCommandPublisher = unitree::robot::ChannelPublisher<D1ArmStringMessage>;
#endif

class DDSBackend final : public D1TransportBackend {
public:
    explicit DDSBackend(D1TransportOptions options)
        : options_(std::move(options)),
          validation_(default_command_validation()) {
        for (auto& limit : validation_.joint_limits) {
            limit.min_deg = options_.joint_min_deg;
            limit.max_deg = options_.joint_max_deg;
        }
        validation_.max_joint_delta_deg = options_.max_joint_delta_deg;
        validation_.command_rate_limit_hz = options_.command_rate_limit_hz;

        latest_status_.backend = "dds";
        latest_status_.controller_owner = "d1_bridge";
        latest_status_.mode = "dds-readonly";
        latest_status_.dry_run_only = true;
        latest_status_.motion_enabled = false;
        latest_status_.controller_lock_held = false;
        set_status_error_fields(latest_status_, "awaiting D1 DDS feedback", 0, "");
    }

    bool connect() override {
#if D1_TRANSPORT_HAS_UNITREE_SDK
        halt_requested_.store(false);
        motion_requested_enabled_.store(false);

        std::string ownership_failure;
        if (!dds_ownership_guard().acquire(latest_status_.controller_owner, ownership_failure)) {
            std::lock_guard<std::mutex> lock(status_mutex_);
            latest_status_.controller_lock_held = false;
            latest_status_.connected = false;
            latest_status_.dry_run_only = true;
            latest_status_.motion_enabled = false;
            latest_status_.mode = "dds-unavailable";
            set_status_error_fields(latest_status_, ownership_failure, error::kOwnershipDenied, "ownership_denied");
            return false;
        }

        owner_lock_held_.store(true);
        {
            std::lock_guard<std::mutex> lock(status_mutex_);
            latest_status_.controller_lock_held = true;
        }
        log_line("INFO", "DDS ownership acquired by " + latest_status_.controller_owner + "; Python remains socket-only");

        if (!channel_factory_guard().init(options_.interface_name)) {
            {
                std::lock_guard<std::mutex> lock(status_mutex_);
                latest_status_.connected = false;
                latest_status_.dry_run_only = true;
                latest_status_.motion_enabled = false;
                latest_status_.mode = "dds-unavailable";
                set_status_error_fields(
                    latest_status_,
                    "Unitree SDK2 ChannelFactory init failed: " + channel_factory_guard().last_error(),
                    error::kSdkUnavailable,
                    "sdk_unavailable");
            }
            close();
            return false;
        }

        try {
            joint_subscriber_ = std::make_unique<D1ServoInfoSubscriber>(options_.servo_topic);
            joint_subscriber_->InitChannel(
                std::bind(&DDSBackend::handle_servo_info, this, std::placeholders::_1),
                1);

            feedback_subscriber_ = std::make_unique<D1ArmFeedbackSubscriber>(options_.feedback_topic);
            feedback_subscriber_->InitChannel(
                std::bind(&DDSBackend::handle_feedback, this, std::placeholders::_1, options_.feedback_topic),
                1);

            if (!options_.feedback_topic_fallback.empty() &&
                options_.feedback_topic_fallback != options_.feedback_topic) {
                feedback_fallback_subscriber_ = std::make_unique<D1ArmFeedbackSubscriber>(options_.feedback_topic_fallback);
                feedback_fallback_subscriber_->InitChannel(
                    std::bind(
                        &DDSBackend::handle_feedback,
                        this,
                        std::placeholders::_1,
                        options_.feedback_topic_fallback),
                    1);
            }
            subscribers_ready_.store(true);
        } catch (const std::exception& exc) {
            {
                std::lock_guard<std::mutex> lock(status_mutex_);
                latest_status_.connected = false;
                latest_status_.dry_run_only = true;
                latest_status_.motion_enabled = false;
                latest_status_.mode = "dds-unavailable";
                set_status_error_fields(
                    latest_status_,
                    "Failed to initialize D1 DDS subscribers: " + std::string(exc.what()),
                    error::kTransportInitFailed,
                    "transport_init_failed");
            }
            close();
            return false;
        } catch (...) {
            {
                std::lock_guard<std::mutex> lock(status_mutex_);
                latest_status_.connected = false;
                latest_status_.dry_run_only = true;
                latest_status_.motion_enabled = false;
                latest_status_.mode = "dds-unavailable";
                set_status_error_fields(
                    latest_status_,
                    "Failed to initialize D1 DDS subscribers",
                    error::kTransportInitFailed,
                    "transport_init_failed");
            }
            close();
            return false;
        }

        try {
            command_publisher_ = std::make_unique<D1ArmCommandPublisher>(options_.command_topic);
            command_publisher_->InitChannel();
            command_channel_ready_.store(true);
        } catch (const std::exception& exc) {
            command_channel_ready_.store(false);
            {
                std::lock_guard<std::mutex> lock(status_mutex_);
                latest_status_.mode = options_.dry_run_fallback ? "dds-feedback" : "dds-unavailable";
                latest_status_.dry_run_only = true;
                latest_status_.motion_enabled = false;
                set_status_error_fields(
                    latest_status_,
                    "D1 command publisher unavailable: " + std::string(exc.what()),
                    error::kPublisherUnavailable,
                    "publisher_unavailable");
            }
            if (!options_.dry_run_fallback) {
                close();
                return false;
            }
        } catch (...) {
            command_channel_ready_.store(false);
            {
                std::lock_guard<std::mutex> lock(status_mutex_);
                latest_status_.mode = options_.dry_run_fallback ? "dds-feedback" : "dds-unavailable";
                latest_status_.dry_run_only = true;
                latest_status_.motion_enabled = false;
                set_status_error_fields(
                    latest_status_,
                    "D1 command publisher unavailable",
                    error::kPublisherUnavailable,
                    "publisher_unavailable");
            }
            if (!options_.dry_run_fallback) {
                close();
                return false;
            }
        }

        log_line(
            "INFO",
            "Initialized DDS backend: servo='" + options_.servo_topic +
                "', feedback='" + options_.feedback_topic +
                "', fallback='" + options_.feedback_topic_fallback +
                "', command='" + options_.command_topic + "'");
        return true;
#else
        std::lock_guard<std::mutex> lock(status_mutex_);
        latest_status_.connected = false;
        latest_status_.dry_run_only = true;
        latest_status_.motion_enabled = false;
        latest_status_.mode = "dds-unavailable";
        set_status_error_fields(
            latest_status_,
            "Official D1 DDS backend unavailable: install unitree_sdk2 and the D1 msg headers",
            error::kSdkUnavailable,
            "sdk_unavailable");
        return false;
#endif
    }

    void close() override {
#if D1_TRANSPORT_HAS_UNITREE_SDK
        if (joint_subscriber_) {
            joint_subscriber_->CloseChannel();
            joint_subscriber_.reset();
        }
        if (feedback_subscriber_) {
            feedback_subscriber_->CloseChannel();
            feedback_subscriber_.reset();
        }
        if (feedback_fallback_subscriber_) {
            feedback_fallback_subscriber_->CloseChannel();
            feedback_fallback_subscriber_.reset();
        }
        command_publisher_.reset();
#endif
        if (owner_lock_held_.exchange(false)) {
            dds_ownership_guard().release(latest_status_.controller_owner);
        }

        subscribers_ready_.store(false);
        command_channel_ready_.store(false);
        motion_requested_enabled_.store(false);
        halt_requested_.store(false);
        last_joint_msg_ms_.store(0);
        last_status_msg_ms_.store(0);

        std::lock_guard<std::mutex> status_lock(status_mutex_);
        latest_status_.connected = false;
        latest_status_.motion_enabled = false;
        latest_status_.dry_run_only = true;
        latest_status_.controller_lock_held = false;
        latest_status_.mode = "dds-unavailable";
    }

    bool is_connected() const override {
        std::lock_guard<std::mutex> lock(status_mutex_);
        return detail::apply_status_freshness(
                   latest_status_,
                   last_joint_msg_ms_.load(),
                   last_status_msg_ms_.load(),
                   options_.stale_timeout_ms,
                   now_ms(),
                   halt_requested_.load())
            .connected;
    }

    JointState read_joint_state() override {
        std::lock_guard<std::mutex> lock(joint_mutex_);
        return detail::apply_joint_freshness(
            latest_joint_,
            last_joint_msg_ms_.load(),
            options_.stale_timeout_ms,
            now_ms());
    }

    ArmStatus read_status() override {
        std::lock_guard<std::mutex> lock(status_mutex_);
        ArmStatus snapshot = detail::apply_status_freshness(
            latest_status_,
            last_joint_msg_ms_.load(),
            last_status_msg_ms_.load(),
            options_.stale_timeout_ms,
            now_ms(),
            halt_requested_.load());

        snapshot.backend = "dds";
        snapshot.controller_owner = latest_status_.controller_owner;
        snapshot.controller_lock_held = owner_lock_held_.load();
        const bool real_publish_ready = snapshot.connected && command_channel_ready_.load() && snapshot.controller_lock_held && !snapshot.estop;
        snapshot.motion_enabled = motion_requested_enabled_.load() && real_publish_ready && !halt_requested_.load();
        snapshot.dry_run_only = !snapshot.motion_enabled;

        if (snapshot.motion_enabled) {
            snapshot.mode = "dds-active";
        } else if (command_channel_ready_.load()) {
            snapshot.mode = "dds-readonly";
        } else if (subscribers_ready_.load()) {
            snapshot.mode = "dds-feedback";
        } else {
            snapshot.mode = "dds-unavailable";
        }

        return snapshot;
    }

    D1CommandResult set_motion_enabled(bool enabled) override {
        if (!enabled) {
            motion_requested_enabled_.store(false);
            halt_requested_.store(false);
            if (can_publish_commands()) {
                D1Command disable_command;
                disable_command.type = D1CommandType::DisableMotion;
                const auto publish_result = publish_command(disable_command);
                if (!publish_result.ok) {
                    return publish_result;
                }
            }

            std::lock_guard<std::mutex> lock(status_mutex_);
            latest_status_.motion_enabled = false;
            latest_status_.dry_run_only = true;
            latest_status_.mode = command_channel_ready_.load() ? "dds-readonly" : "dds-feedback";
            clear_status_error_fields(latest_status_);
            latest_status_.last_update_ms = now_ms();
            return success_result("motion disabled", false, true);
        }

        if (!options_.enable_motion) {
            return precondition_error(
                error::kMotionDisabledByConfig,
                "motion_disabled_by_config",
                "bridge motion publishing is disabled by configuration",
                false,
                true);
        }
        if (!is_connected()) {
            return precondition_error(
                error::kArmDisconnected,
                "arm_disconnected",
                "D1 feedback is not connected; motion enable rejected",
                false,
                true);
        }
        {
            std::lock_guard<std::mutex> lock(status_mutex_);
            if (latest_status_.estop) {
                return precondition_error(
                    error::kEstopActive,
                    "estop_active",
                    "D1 reported ESTOP; motion enable rejected",
                    false,
                    true);
            }
        }
        if (!owner_lock_held_.load()) {
            return precondition_error(
                error::kControllerLockMissing,
                "controller_lock_missing",
                "DDS controller ownership is not held by the bridge",
                false,
                true);
        }
        if (!command_channel_ready_.load()) {
            return precondition_error(
                error::kPublisherUnavailable,
                "publisher_unavailable",
                "D1 command publisher is unavailable; bridge stays dry-run only",
                false,
                true);
        }

        D1Command enable_command;
        enable_command.type = D1CommandType::EnableMotion;
        const auto publish_result = publish_command(enable_command);
        if (!publish_result.ok) {
            return publish_result;
        }

        motion_requested_enabled_.store(true);
        halt_requested_.store(false);
        std::lock_guard<std::mutex> lock(status_mutex_);
        latest_status_.motion_enabled = true;
        latest_status_.dry_run_only = false;
        latest_status_.mode = "dds-active";
        clear_status_error_fields(latest_status_);
        latest_status_.last_update_ms = now_ms();
        return success_result("motion enabled", true, false);
    }

    D1CommandResult send_command(const D1Command& command) override {
        if (command.type == D1CommandType::EnableMotion) {
            return set_motion_enabled(true);
        }
        if (command.type == D1CommandType::DisableMotion) {
            return set_motion_enabled(false);
        }
        if (command.type == D1CommandType::Halt) {
            stop_motion();
            return success_result("halt requested", false, true);
        }

        const auto preflight = validate_motion_preconditions();
        if (!preflight.ok) {
            return preflight;
        }

        auto current_angles = latest_servo_positions();
        if (!current_angles) {
            return precondition_error(
                error::kMissingFreshState,
                "missing_fresh_state",
                "fresh servo feedback is required before publishing motion commands",
                motion_requested_enabled_.load(),
                true);
        }

        D1Command normalized = command;
        D1CommandResult validation_result;
        if (!validate_command_payload(normalized, *current_angles, validation_result)) {
            return validation_result;
        }

        const auto spacing_ms = min_command_spacing_ms(validation_.command_rate_limit_hz);
        const auto now = now_ms();
        const auto last_command = last_command_ms_.load();
        if (spacing_ms > 0 && last_command > 0 && (now - last_command) < spacing_ms) {
            std::ostringstream message;
            message << "command rate limited; minimum spacing is " << spacing_ms << " ms";
            return precondition_error(
                error::kRateLimited,
                "rate_limited",
                message.str(),
                true,
                true);
        }

        const auto publish_result = publish_command(normalized);
        if (!publish_result.ok) {
            return publish_result;
        }
        last_command_ms_.store(now);

        std::lock_guard<std::mutex> lock(status_mutex_);
        latest_status_.motion_enabled = true;
        latest_status_.dry_run_only = false;
        latest_status_.mode = "dds-active";
        clear_status_error_fields(latest_status_);
        latest_status_.last_update_ms = now;
        return success_result("command published", true, false);
    }

    bool stop_motion() override {
        halt_requested_.store(true);
        motion_requested_enabled_.store(false);

        if (can_publish_commands()) {
            D1Command halt_command;
            halt_command.type = D1CommandType::Halt;
            (void)publish_command(halt_command);
        }

        std::lock_guard<std::mutex> lock(status_mutex_);
        latest_status_.motion_enabled = false;
        latest_status_.dry_run_only = true;
        latest_status_.mode = command_channel_ready_.load() ? "dds-readonly" : "dds-feedback";
        set_status_error_fields(latest_status_, "software halt requested", 0, "");
        return true;
    }

private:
    bool can_publish_commands() const {
        return is_connected() && owner_lock_held_.load() && command_channel_ready_.load();
    }

    std::optional<std::array<double, kD1CommandJointCount>> latest_servo_positions() const {
        std::lock_guard<std::mutex> lock(servo_mutex_);
        const auto age_ms = now_ms() - last_joint_msg_ms_.load();
        if (!have_servo_positions_ || age_ms > options_.stale_timeout_ms) {
            return std::nullopt;
        }
        return latest_servo_positions_deg_;
    }

    D1CommandResult validate_motion_preconditions() const {
        if (!options_.enable_motion) {
            return precondition_error(
                error::kMotionDisabledByConfig,
                "motion_disabled_by_config",
                "bridge motion publishing is disabled by configuration",
                false,
                true);
        }
        if (!is_connected()) {
            return precondition_error(
                error::kArmDisconnected,
                "arm_disconnected",
                "D1 feedback is not connected; motion command rejected",
                motion_requested_enabled_.load(),
                true);
        }
        if (!motion_requested_enabled_.load() || halt_requested_.load()) {
            return precondition_error(
                error::kMotionNotEnabled,
                "motion_not_enabled",
                "motion command rejected because enable_motion has not been granted",
                false,
                true);
        }
        {
            std::lock_guard<std::mutex> lock(status_mutex_);
            if (latest_status_.estop) {
                return precondition_error(
                    error::kEstopActive,
                    "estop_active",
                    "D1 reported ESTOP; motion command rejected",
                    false,
                    true);
            }
        }
        if (!owner_lock_held_.load()) {
            return precondition_error(
                error::kControllerLockMissing,
                "controller_lock_missing",
                "DDS controller ownership is not held by the bridge",
                false,
                true);
        }
        if (!command_channel_ready_.load()) {
            return precondition_error(
                error::kPublisherUnavailable,
                "publisher_unavailable",
                "D1 command publisher is unavailable; bridge stays dry-run only",
                false,
                true);
        }
        return success_result("validated", true, false);
    }

    bool validate_command_payload(
        D1Command& command,
        const std::array<double, kD1CommandJointCount>& current_angles_deg,
        D1CommandResult& out_result) const {
        switch (command.type) {
            case D1CommandType::SetJointAngle:
                if (!validate_joint_limit(command.joint_id, command.angle_deg, validation_, out_result)) {
                    return false;
                }
                return validate_joint_delta(command.joint_id, command.angle_deg, current_angles_deg, validation_, out_result);

            case D1CommandType::SetMultiJointAngle: {
                if (command.angle_count != kD1StateJointCount && command.angle_count != kD1CommandJointCount) {
                    out_result = precondition_error(
                        error::kBadPayload,
                        "bad_payload",
                        "angles_deg must contain 6 or 7 values",
                        false,
                        true);
                    return false;
                }
                if (command.angle_count == kD1StateJointCount) {
                    command.angles_deg[kD1CommandJointCount - 1] = current_angles_deg[kD1CommandJointCount - 1];
                }
                for (std::size_t idx = 0; idx < kD1CommandJointCount; ++idx) {
                    if (!validate_joint_limit(static_cast<int>(idx), command.angles_deg[idx], validation_, out_result)) {
                        return false;
                    }
                    if (!validate_joint_delta(
                            static_cast<int>(idx),
                            command.angles_deg[idx],
                            current_angles_deg,
                            validation_,
                            out_result)) {
                        return false;
                    }
                }
                if (command.mode != 0 && command.mode != 1) {
                    out_result = precondition_error(
                        error::kBadPayload,
                        "bad_payload",
                        "multi joint mode must be 0 or 1",
                        false,
                        true);
                    return false;
                }
                return true;
            }

            case D1CommandType::ZeroArm:
                return true;

            case D1CommandType::Halt:
            case D1CommandType::EnableMotion:
            case D1CommandType::DisableMotion:
                return true;
        }

        out_result = precondition_error(error::kBadPayload, "bad_payload", "unsupported command type", false, true);
        return false;
    }

    D1CommandResult publish_command(const D1Command& command) {
#if D1_TRANSPORT_HAS_UNITREE_SDK
        if (!command_publisher_) {
            return precondition_error(
                error::kPublisherUnavailable,
                "publisher_unavailable",
                "D1 command publisher is unavailable",
                false,
                true);
        }

        D1ArmStringMessage message;
        message.data_() = serialize_command_payload(command, command_seq_.fetch_add(1));
        try {
            command_publisher_->Write(message);
        } catch (const std::exception& exc) {
            std::lock_guard<std::mutex> lock(status_mutex_);
            latest_status_.motion_enabled = false;
            latest_status_.dry_run_only = true;
            latest_status_.mode = "dds-feedback";
            set_status_error_fields(
                latest_status_,
                "DDS command publish failed: " + std::string(exc.what()),
                error::kPublisherUnavailable,
                "publisher_unavailable");
            return precondition_error(
                error::kPublisherUnavailable,
                "publisher_unavailable",
                latest_status_.last_error_message,
                false,
                true);
        } catch (...) {
            std::lock_guard<std::mutex> lock(status_mutex_);
            latest_status_.motion_enabled = false;
            latest_status_.dry_run_only = true;
            latest_status_.mode = "dds-feedback";
            set_status_error_fields(
                latest_status_,
                "DDS command publish failed",
                error::kPublisherUnavailable,
                "publisher_unavailable");
            return precondition_error(
                error::kPublisherUnavailable,
                "publisher_unavailable",
                latest_status_.last_error_message,
                false,
                true);
        }

        return success_result("command published", motion_requested_enabled_.load(), !motion_requested_enabled_.load());
#else
        (void)command;
        return precondition_error(
            error::kSdkUnavailable,
            "sdk_unavailable",
            "D1 DDS publisher is unavailable in this build",
            false,
            true);
#endif
    }

#if D1_TRANSPORT_HAS_UNITREE_SDK
    void handle_servo_info(const void* message) {
        if (message == nullptr) {
            return;
        }

        const auto* servo_info = static_cast<const D1ServoInfoMessage*>(message);
        JointState next;
        std::array<double, kD1CommandJointCount> servo_positions{};
        servo_positions[0] = servo_info->servo0_data_();
        servo_positions[1] = servo_info->servo1_data_();
        servo_positions[2] = servo_info->servo2_data_();
        servo_positions[3] = servo_info->servo3_data_();
        servo_positions[4] = servo_info->servo4_data_();
        servo_positions[5] = servo_info->servo5_data_();
        servo_positions[6] = servo_info->servo6_data_();

        for (std::size_t idx = 0; idx < kD1StateJointCount; ++idx) {
            next.q[idx] = servo_positions[idx];
            next.dq[idx] = 0.0;
            next.tau[idx] = 0.0;
        }
        next.valid = true;
        next.stamp_ms = now_ms();

        {
            std::lock_guard<std::mutex> joint_lock(joint_mutex_);
            latest_joint_ = next;
        }
        {
            std::lock_guard<std::mutex> servo_lock(servo_mutex_);
            latest_servo_positions_deg_ = servo_positions;
            have_servo_positions_ = true;
        }
        last_joint_msg_ms_.store(next.stamp_ms);
    }

    void handle_feedback(const void* message, const std::string& topic_name) {
        if (message == nullptr) {
            return;
        }

        const auto* feedback = static_cast<const D1ArmStringMessage*>(message);
        const auto parsed_at_ms = now_ms();

        ArmStatus previous;
        {
            std::lock_guard<std::mutex> lock(status_mutex_);
            previous = latest_status_;
        }

        auto parsed = detail::parse_arm_feedback_json(feedback->data_(), previous, parsed_at_ms);
        {
            std::lock_guard<std::mutex> lock(status_mutex_);
            if (parsed.parsed) {
                latest_status_ = parsed.status;
                latest_status_.backend = "dds";
                latest_status_.controller_owner = previous.controller_owner;
                latest_status_.controller_lock_held = owner_lock_held_.load();
            } else {
                latest_status_.backend = "dds";
                latest_status_.controller_owner = previous.controller_owner;
                latest_status_.controller_lock_held = owner_lock_held_.load();
                set_status_error_fields(
                    latest_status_,
                    parsed.error_message,
                    previous.error_code,
                    previous.error_kind);
            }
        }
        last_status_msg_ms_.store(parsed_at_ms);

        if (!first_feedback_log_.exchange(true)) {
            log_line("INFO", "Received first D1 status feedback from '" + topic_name + "'");
        }
    }

    std::unique_ptr<D1ServoInfoSubscriber> joint_subscriber_;
    std::unique_ptr<D1ArmFeedbackSubscriber> feedback_subscriber_;
    std::unique_ptr<D1ArmFeedbackSubscriber> feedback_fallback_subscriber_;
    std::unique_ptr<D1ArmCommandPublisher> command_publisher_;
#endif

    D1TransportOptions options_;
    D1CommandValidation validation_;
    mutable std::mutex joint_mutex_;
    mutable std::mutex servo_mutex_;
    mutable std::mutex status_mutex_;
    JointState latest_joint_{};
    std::array<double, kD1CommandJointCount> latest_servo_positions_deg_{};
    bool have_servo_positions_{false};
    ArmStatus latest_status_{};
    std::atomic<std::int64_t> last_joint_msg_ms_{0};
    std::atomic<std::int64_t> last_status_msg_ms_{0};
    std::atomic<std::int64_t> last_command_ms_{0};
    std::atomic<bool> halt_requested_{false};
    std::atomic<bool> motion_requested_enabled_{false};
    std::atomic<bool> subscribers_ready_{false};
    std::atomic<bool> command_channel_ready_{false};
    std::atomic<bool> owner_lock_held_{false};
    std::atomic<bool> first_feedback_log_{false};
    std::atomic<std::uint64_t> command_seq_{1};
};

class MockBackend final : public D1TransportBackend {
public:
    explicit MockBackend(D1TransportOptions options)
        : options_(std::move(options)),
          validation_(default_command_validation()) {
        for (auto& limit : validation_.joint_limits) {
            limit.min_deg = options_.joint_min_deg;
            limit.max_deg = options_.joint_max_deg;
        }
        validation_.max_joint_delta_deg = options_.max_joint_delta_deg;
        validation_.command_rate_limit_hz = options_.command_rate_limit_hz;

        status_.backend = "mock";
        status_.controller_owner = "d1_bridge";
        status_.controller_lock_held = true;
        status_.mode = "mock";
        status_.dry_run_only = true;
        status_.motion_enabled = false;
        clear_status_error_fields(status_);
    }

    bool connect() override {
        connected_ = true;
        status_.connected = true;
        status_.mode = "mock";
        status_.dry_run_only = true;
        status_.motion_enabled = false;
        status_.last_update_ms = now_ms();
        clear_status_error_fields(status_);
        commanded_angles_.fill(0.0);
        current_angles_.fill(0.0);
        current_velocities_.fill(0.0);
        log_line("INFO", "Selected MockBackend");
        return true;
    }

    void close() override {
        connected_ = false;
        motion_requested_enabled_ = false;
        status_.connected = false;
        status_.motion_enabled = false;
        status_.dry_run_only = true;
        status_.last_update_ms = now_ms();
    }

    bool is_connected() const override {
        return connected_;
    }

    JointState read_joint_state() override {
        const auto now = now_ms();
        const double dt = last_read_ms_ > 0 ? static_cast<double>(now - last_read_ms_) / 1000.0 : 0.1;
        last_read_ms_ = now;

        for (std::size_t idx = 0; idx < current_angles_.size(); ++idx) {
            const double error = commanded_angles_[idx] - current_angles_[idx];
            const double velocity = std::clamp(error * 3.0, -0.6, 0.6);
            current_velocities_[idx] = velocity;
            current_angles_[idx] += velocity * dt;
            current_torques_[idx] = 0.05 * std::sin(static_cast<double>(now) / 1000.0 + static_cast<double>(idx) * 0.4);
        }

        JointState state;
        for (std::size_t idx = 0; idx < kD1StateJointCount; ++idx) {
            state.q[idx] = current_angles_[idx];
            state.dq[idx] = current_velocities_[idx];
            state.tau[idx] = current_torques_[idx];
        }
        state.valid = connected_;
        state.stamp_ms = now;
        status_.last_update_ms = now;
        return state;
    }

    ArmStatus read_status() override {
        status_.connected = connected_;
        status_.motion_enabled = motion_requested_enabled_;
        status_.dry_run_only = true;
        status_.mode = "mock";
        status_.last_update_ms = now_ms();
        return status_;
    }

    D1CommandResult set_motion_enabled(bool enabled) override {
        if (enabled && !options_.enable_motion) {
            return precondition_error(
                error::kMotionDisabledByConfig,
                "motion_disabled_by_config",
                "mock bridge motion simulation is disabled by configuration",
                false,
                true);
        }
        motion_requested_enabled_ = enabled && connected_;
        status_.motion_enabled = motion_requested_enabled_;
        status_.dry_run_only = true;
        status_.last_update_ms = now_ms();
        clear_status_error_fields(status_);
        return success_result(enabled ? "mock motion gate enabled" : "mock motion gate disabled", motion_requested_enabled_, true);
    }

    D1CommandResult send_command(const D1Command& command) override {
        if (command.type == D1CommandType::EnableMotion) {
            return set_motion_enabled(true);
        }
        if (command.type == D1CommandType::DisableMotion) {
            return set_motion_enabled(false);
        }
        if (command.type == D1CommandType::Halt) {
            stop_motion();
            return success_result("mock halt requested", false, true);
        }
        if (!options_.enable_motion) {
            return precondition_error(
                error::kMotionDisabledByConfig,
                "motion_disabled_by_config",
                "mock bridge motion simulation is disabled by configuration",
                false,
                true);
        }
        if (!connected_) {
            return precondition_error(
                error::kArmDisconnected,
                "arm_disconnected",
                "mock backend is not connected",
                false,
                true);
        }
        if (!motion_requested_enabled_) {
            return precondition_error(
                error::kMotionNotEnabled,
                "motion_not_enabled",
                "mock backend requires enable_motion before accepting commands",
                false,
                true);
        }

        D1CommandResult validation_result;
        switch (command.type) {
            case D1CommandType::SetJointAngle:
                if (!validate_joint_limit(command.joint_id, command.angle_deg, validation_, validation_result)) {
                    return validation_result;
                }
                if (!validate_joint_delta(command.joint_id, command.angle_deg, current_angles_, validation_, validation_result)) {
                    return validation_result;
                }
                commanded_angles_[static_cast<std::size_t>(command.joint_id)] = command.angle_deg;
                break;

            case D1CommandType::SetMultiJointAngle:
                if (command.angle_count != kD1StateJointCount && command.angle_count != kD1CommandJointCount) {
                    return precondition_error(
                        error::kBadPayload,
                        "bad_payload",
                        "angles_deg must contain 6 or 7 values",
                        false,
                        true);
                }
                for (std::size_t idx = 0; idx < command.angle_count; ++idx) {
                    if (!validate_joint_limit(static_cast<int>(idx), command.angles_deg[idx], validation_, validation_result)) {
                        return validation_result;
                    }
                    if (!validate_joint_delta(static_cast<int>(idx), command.angles_deg[idx], current_angles_, validation_, validation_result)) {
                        return validation_result;
                    }
                    commanded_angles_[idx] = command.angles_deg[idx];
                }
                break;

            case D1CommandType::ZeroArm:
                commanded_angles_.fill(0.0);
                break;

            case D1CommandType::Halt:
            case D1CommandType::EnableMotion:
            case D1CommandType::DisableMotion:
                break;
        }

        status_.last_update_ms = now_ms();
        clear_status_error_fields(status_);
        return success_result("accepted in mock backend", motion_requested_enabled_, true);
    }

    bool stop_motion() override {
        motion_requested_enabled_ = false;
        status_.motion_enabled = false;
        status_.dry_run_only = true;
        status_.last_update_ms = now_ms();
        set_status_error_fields(status_, "mock halt requested", 0, "");
        return true;
    }

private:
    D1TransportOptions options_;
    D1CommandValidation validation_;
    bool connected_{false};
    bool motion_requested_enabled_{false};
    std::array<double, kD1CommandJointCount> current_angles_{};
    std::array<double, kD1CommandJointCount> current_velocities_{};
    std::array<double, kD1CommandJointCount> current_torques_{};
    std::array<double, kD1CommandJointCount> commanded_angles_{};
    std::int64_t last_read_ms_{0};
    ArmStatus status_{};
};

}  // namespace

D1Transport::D1Transport(D1TransportOptions options)
    : options_(std::move(options)) {
    if (options_.mock_mode) {
        backend_ = std::make_unique<MockBackend>(options_);
    } else {
        backend_ = std::make_unique<DDSBackend>(options_);
    }
}

D1Transport::~D1Transport() = default;

bool D1Transport::connect() {
    return backend_->connect();
}

void D1Transport::close() {
    backend_->close();
}

bool D1Transport::is_connected() const {
    return backend_->is_connected();
}

JointState D1Transport::read_joint_state() {
    return backend_->read_joint_state();
}

ArmStatus D1Transport::read_status() {
    return backend_->read_status();
}

D1CommandResult D1Transport::set_motion_enabled(bool enabled) {
    return backend_->set_motion_enabled(enabled);
}

D1CommandResult D1Transport::send_command(const D1Command& command) {
    return backend_->send_command(command);
}

bool D1Transport::stop_motion() {
    return backend_->stop_motion();
}

}  // namespace d1
