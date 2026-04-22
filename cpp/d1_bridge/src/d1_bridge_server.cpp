#include "d1_bridge_server.hpp"

#include <cctype>
#include <cerrno>
#include <cstdio>
#include <chrono>
#include <cmath>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <iomanip>
#include <iostream>
#include <optional>
#include <poll.h>
#include <sstream>
#include <string>
#include <vector>
#include <sys/socket.h>
#include <sys/un.h>
#include <thread>
#include <unistd.h>

namespace d1 {

namespace {

constexpr std::size_t kMaxRequestBytes = 64 * 1024;

void log_line(const char* level, const std::string& message) {
    const auto now = std::chrono::system_clock::now();
    const auto time = std::chrono::system_clock::to_time_t(now);
    std::tm tm_snapshot{};
#if defined(_WIN32)
    localtime_s(&tm_snapshot, &time);
#else
    localtime_r(&time, &tm_snapshot);
#endif

    std::ostringstream line;
    line << std::put_time(&tm_snapshot, "%Y-%m-%d %H:%M:%S")
         << " [" << level << "] " << message;
    std::cerr << line.str() << std::endl;
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

std::string json_escape(const std::string& value) {
    std::ostringstream escaped;
    for (const char ch : value) {
        switch (ch) {
            case '\\':
                escaped << "\\\\";
                break;
            case '"':
                escaped << "\\\"";
                break;
            case '\n':
                escaped << "\\n";
                break;
            case '\r':
                escaped << "\\r";
                break;
            case '\t':
                escaped << "\\t";
                break;
            default:
                escaped << ch;
                break;
        }
    }
    return escaped.str();
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

    auto cursor = *key_end;
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

    auto cursor = *key_end;
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

std::optional<std::string> extract_array_field(const std::string& text, const std::string& key) {
    const auto key_end = find_json_key(text, key);
    if (!key_end) {
        return std::nullopt;
    }

    auto cursor = *key_end;
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
    if (cursor >= text.size() || text[cursor] != '[') {
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
        } else if (ch == '[') {
            ++depth;
        } else if (ch == ']') {
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

    auto cursor = *key_end;
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

    auto cursor = *key_end;
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

std::optional<std::vector<double>> parse_double_array(const std::string& text) {
    const auto trimmed = trim_copy(text);
    if (trimmed.size() < 2 || trimmed.front() != '[' || trimmed.back() != ']') {
        return std::nullopt;
    }

    std::vector<double> values;
    std::size_t cursor = 1;
    while (cursor < trimmed.size() - 1) {
        while (cursor < trimmed.size() - 1 &&
               (std::isspace(static_cast<unsigned char>(trimmed[cursor])) != 0 || trimmed[cursor] == ',')) {
            ++cursor;
        }
        if (cursor >= trimmed.size() - 1) {
            break;
        }

        char* end = nullptr;
        const double value = std::strtod(trimmed.c_str() + cursor, &end);
        if (end == trimmed.c_str() + cursor || !std::isfinite(value)) {
            return std::nullopt;
        }
        values.push_back(value);
        cursor = static_cast<std::size_t>(end - trimmed.c_str());
    }

    return values;
}

template <typename ArrayType>
std::string array_to_json(const ArrayType& values) {
    std::ostringstream out;
    out << "[";
    for (std::size_t idx = 0; idx < values.size(); ++idx) {
        if (idx > 0) {
            out << ",";
        }
        out << std::fixed << std::setprecision(6) << values[idx];
    }
    out << "]";
    return out.str();
}

std::string joint_state_response(const JointState& state) {
    std::ostringstream out;
    out << "{"
        << "\"ok\":true,"
        << "\"joint_state\":{"
        << "\"q\":" << array_to_json(state.q) << ","
        << "\"dq\":" << array_to_json(state.dq) << ","
        << "\"tau\":" << array_to_json(state.tau) << ","
        << "\"valid\":" << (state.valid ? "true" : "false") << ","
        << "\"stamp_ms\":" << state.stamp_ms
        << "}"
        << "}";
    return out.str();
}

std::string status_response(const ArmStatus& status) {
    std::ostringstream out;
    out << "{"
        << "\"ok\":true,"
        << "\"status\":{"
        << "\"connected\":" << (status.connected ? "true" : "false") << ","
        << "\"estop\":" << (status.estop ? "true" : "false") << ","
        << "\"motion_enabled\":" << (status.motion_enabled ? "true" : "false") << ","
        << "\"dry_run_only\":" << (status.dry_run_only ? "true" : "false") << ","
        << "\"controller_lock_held\":" << (status.controller_lock_held ? "true" : "false") << ","
        << "\"error_code\":" << status.error_code << ","
        << "\"error_kind\":\"" << json_escape(status.error_kind) << "\","
        << "\"mode\":\"" << json_escape(status.mode) << "\","
        << "\"backend\":\"" << json_escape(status.backend) << "\","
        << "\"controller_owner\":\"" << json_escape(status.controller_owner) << "\","
        << "\"last_update_ms\":" << status.last_update_ms << ","
        << "\"last_error\":\"" << json_escape(status.last_error) << "\","
        << "\"last_error_message\":\"" << json_escape(status.last_error_message) << "\""
        << "}"
        << "}";
    return out.str();
}

std::string message_response(
    bool ok,
    const std::string& message,
    int error_code = 0,
    const std::string& error_kind = {},
    bool accepted = false,
    bool motion_enabled = false,
    bool dry_run_only = true) {
    std::ostringstream out;
    out << "{"
        << "\"ok\":" << (ok ? "true" : "false") << ","
        << "\"message\":\"" << json_escape(message) << "\","
        << "\"error_code\":" << error_code << ","
        << "\"error_kind\":\"" << json_escape(error_kind) << "\","
        << "\"accepted\":" << (accepted ? "true" : "false") << ","
        << "\"motion_enabled\":" << (motion_enabled ? "true" : "false") << ","
        << "\"dry_run_only\":" << (dry_run_only ? "true" : "false")
        << "}";
    return out.str();
}

std::string command_response(const D1CommandResult& result) {
    return message_response(
        result.ok,
        result.message,
        result.error_code,
        result.error_kind,
        result.accepted,
        result.motion_enabled,
        result.dry_run_only);
}

}  // namespace

D1TransportOptions D1BridgeServer::make_transport_options(const D1BridgeServerOptions& options) {
    D1TransportOptions transport_options;
    transport_options.mock_mode = options.mock_mode;
    transport_options.endpoint = "local";
    transport_options.interface_name = options.interface_name;
    transport_options.servo_topic = options.servo_topic;
    transport_options.feedback_topic = options.feedback_topic;
    transport_options.feedback_topic_fallback = options.feedback_topic_fallback;
    transport_options.command_topic = options.command_topic;
    transport_options.enable_motion = options.enable_motion;
    transport_options.dry_run_fallback = options.dry_run_fallback;
    transport_options.max_joint_delta_deg = options.max_joint_delta_deg;
    transport_options.command_rate_limit_hz = options.command_rate_limit_hz;
    transport_options.joint_min_deg = options.joint_min_deg;
    transport_options.joint_max_deg = options.joint_max_deg;
    transport_options.stale_timeout_ms = options.stale_timeout_ms;
    return transport_options;
}

D1BridgeServer::D1BridgeServer(D1BridgeServerOptions options)
    : options_(std::move(options)),
      transport_(make_transport_options(options_)),
      safety_(options_.watchdog_timeout_ms) {
    latest_status_.backend = options_.mock_mode ? "mock" : "dds";
    latest_status_.controller_owner = "d1_bridge";
    latest_status_.mode = options_.mock_mode ? "mock" : "dds-unavailable";
    latest_status_.dry_run_only = true;
    latest_status_.motion_enabled = false;
    latest_status_.last_update_ms = 0;
    latest_joint_state_.stamp_ms = 0;
}

D1BridgeServer::~D1BridgeServer() {
    stop();
}

bool D1BridgeServer::run() {
    if (running_.load()) {
        return false;
    }
    if (!setup_socket()) {
        return false;
    }

    running_.store(true);
    poll_thread_ = std::thread(&D1BridgeServer::poll_loop, this);

    log_line("INFO", "D1 bridge server listening on " + options_.socket_path);

    while (running_.load()) {
        pollfd server_poll{};
        server_poll.fd = server_fd_;
        server_poll.events = POLLIN;

        const int rc = ::poll(&server_poll, 1, 200);
        if (rc < 0) {
            if (errno == EINTR) {
                continue;
            }
            log_line("ERROR", "Socket poll failed: " + std::string(std::strerror(errno)));
            break;
        }
        if (rc == 0) {
            continue;
        }
        if ((server_poll.revents & POLLIN) == 0) {
            continue;
        }

        const int client_fd = ::accept(server_fd_, nullptr, nullptr);
        if (client_fd < 0) {
            if (errno == EINTR) {
                continue;
            }
            log_line("WARN", "Accept failed: " + std::string(std::strerror(errno)));
            continue;
        }
        handle_client(client_fd);
        ::close(client_fd);
    }

    stop();
    return true;
}

void D1BridgeServer::stop() {
    const bool was_running = running_.exchange(false);

    if (server_fd_ >= 0) {
        ::close(server_fd_);
        server_fd_ = -1;
    }

    if (poll_thread_.joinable()) {
        poll_thread_.join();
    }

    transport_.close();
    cleanup_socket();

    if (was_running) {
        log_line("INFO", "D1 bridge server stopped");
    }
}

bool D1BridgeServer::setup_socket() {
    const std::filesystem::path socket_path(options_.socket_path);
    const auto parent = socket_path.parent_path();
    if (!parent.empty()) {
        std::error_code ec;
        std::filesystem::create_directories(parent, ec);
        if (ec) {
            log_line("ERROR", "Failed to create socket directory " + parent.string() + ": " + ec.message());
            return false;
        }
    }

    cleanup_socket();

    server_fd_ = ::socket(AF_UNIX, SOCK_STREAM, 0);
    if (server_fd_ < 0) {
        log_line("ERROR", "Failed to create UNIX socket: " + std::string(std::strerror(errno)));
        return false;
    }

    sockaddr_un address{};
    address.sun_family = AF_UNIX;
    if (options_.socket_path.size() >= sizeof(address.sun_path)) {
        log_line("ERROR", "UNIX socket path is too long: " + options_.socket_path);
        ::close(server_fd_);
        server_fd_ = -1;
        return false;
    }
    std::snprintf(address.sun_path, sizeof(address.sun_path), "%s", options_.socket_path.c_str());

    if (::bind(server_fd_, reinterpret_cast<sockaddr*>(&address), sizeof(address)) < 0) {
        log_line("ERROR", "Failed to bind UNIX socket " + options_.socket_path + ": " + std::string(std::strerror(errno)));
        ::close(server_fd_);
        server_fd_ = -1;
        return false;
    }

    if (::listen(server_fd_, 8) < 0) {
        log_line("ERROR", "Failed to listen on UNIX socket: " + std::string(std::strerror(errno)));
        ::close(server_fd_);
        server_fd_ = -1;
        cleanup_socket();
        return false;
    }

    return true;
}

void D1BridgeServer::cleanup_socket() {
    if (!options_.socket_path.empty()) {
        ::unlink(options_.socket_path.c_str());
    }
}

void D1BridgeServer::poll_loop() {
    std::int64_t last_connect_attempt_ms = 0;
    bool last_transport_connected = false;

    while (running_.load()) {
        const auto cycle_start_ms = now_ms();
        JointState next_joint_state;
        ArmStatus next_status;

        bool transport_connected = false;
        {
            std::lock_guard<std::mutex> transport_lock(transport_mutex_);
            transport_connected = transport_.is_connected();
        }
        if (!transport_connected && (cycle_start_ms - last_connect_attempt_ms) >= 1000) {
            last_connect_attempt_ms = cycle_start_ms;
            bool connected = false;
            {
                std::lock_guard<std::mutex> transport_lock(transport_mutex_);
                connected = transport_.connect();
            }
            log_line(
                connected ? "INFO" : "WARN",
                connected ? "D1 transport connected" : "D1 transport connect() did not establish a live link");
        }

        try {
            {
                std::lock_guard<std::mutex> transport_lock(transport_mutex_);
                next_joint_state = transport_.read_joint_state();
                next_status = transport_.read_status();
            }

            if (next_status.last_update_ms <= 0) {
                next_status.last_update_ms = cycle_start_ms;
            }
            if (next_joint_state.stamp_ms <= 0) {
                next_joint_state.stamp_ms = cycle_start_ms;
            }

            safety_.note_poll_success(cycle_start_ms);
            safety_.set_estop(next_status.estop);
        } catch (const std::exception& exc) {
            safety_.note_poll_failure(exc.what(), cycle_start_ms);
            next_joint_state.valid = false;
            next_joint_state.stamp_ms = cycle_start_ms;
            next_status.connected = false;
            next_status.estop = safety_.estop();
            next_status.motion_enabled = false;
            next_status.dry_run_only = true;
            next_status.error_code = error::kTransportInitFailed;
            next_status.error_kind = "transport_failure";
            next_status.backend = options_.mock_mode ? "mock" : "dds";
            next_status.mode = options_.mock_mode ? "mock" : "dds-unavailable";
            next_status.controller_owner = "d1_bridge";
            next_status.last_update_ms = cycle_start_ms;
            next_status.last_error = exc.what();
            next_status.last_error_message = exc.what();
        }

        if (safety_.halt_requested()) {
            bool stopped = false;
            {
                std::lock_guard<std::mutex> transport_lock(transport_mutex_);
                stopped = transport_.stop_motion();
            }
            if (!stopped) {
                log_line("WARN", "Transport stop_motion() reported failure during halt request");
            }
            next_status.motion_enabled = false;
            next_status.dry_run_only = true;
        }

        if (safety_.update_watchdog(cycle_start_ms)) {
            next_status.connected = false;
            if (next_status.error_code == 0) {
                next_status.error_code = error::kWatchdogExpired;
                next_status.error_kind = "watchdog_expired";
            }
            if (next_status.last_error.empty()) {
                next_status.last_error = "D1 bridge watchdog expired";
                next_status.last_error_message = next_status.last_error;
            }
        }

        {
            std::lock_guard<std::mutex> lock(state_mutex_);
            latest_joint_state_ = next_joint_state;
            latest_status_ = next_status;
        }

        if (const auto transition = safety_.consume_transition_message()) {
            log_line("WARN", *transition);
        }

        if (next_status.connected != last_transport_connected) {
            log_line(next_status.connected ? "INFO" : "WARN",
                     next_status.connected ? "D1 status now connected" : "D1 status now disconnected");
            last_transport_connected = next_status.connected;
        }

        const auto elapsed_ms = now_ms() - cycle_start_ms;
        const auto sleep_ms = options_.poll_period_ms - elapsed_ms;
        if (sleep_ms > 0) {
            std::this_thread::sleep_for(std::chrono::milliseconds(sleep_ms));
        }
    }
}

void D1BridgeServer::handle_client(int client_fd) {
    std::string request;
    request.reserve(1024);

    char buffer[4096];
    while (request.size() < kMaxRequestBytes) {
        const ssize_t received = ::recv(client_fd, buffer, sizeof(buffer), 0);
        if (received == 0) {
            break;
        }
        if (received < 0) {
            if (errno == EINTR) {
                continue;
            }
            log_line("WARN", "Client recv failed: " + std::string(std::strerror(errno)));
            return;
        }

        request.append(buffer, static_cast<std::size_t>(received));
        if (request.find('\n') != std::string::npos) {
            break;
        }
    }

    if (request.size() >= kMaxRequestBytes) {
        const std::string response = message_response(false, "request exceeds maximum size", error::kMalformedRequest, "malformed_request");
        ::send(client_fd, response.data(), response.size(), 0);
        return;
    }

    const std::string response = handle_request(trim_copy(request)) + "\n";
    ::send(client_fd, response.data(), response.size(), 0);
}

std::string D1BridgeServer::handle_request_for_test(const std::string& request_text) {
    return handle_request(trim_copy(request_text));
}

std::string D1BridgeServer::handle_request(const std::string& request_text) {
    if (request_text.empty()) {
        return message_response(false, "empty request", error::kMalformedRequest, "malformed_request");
    }

    const auto cmd = extract_string_field(request_text, "cmd");
    if (!cmd) {
        return message_response(false, "missing request cmd", error::kMalformedRequest, "malformed_request");
    }

    if (*cmd == "ping") {
        return message_response(true, "pong", 0, "", true, false, true);
    }

    if (*cmd == "status" || *cmd == "refresh") {
        std::lock_guard<std::mutex> lock(state_mutex_);
        return status_response(latest_status_);
    }

    if (*cmd == "joints") {
        std::lock_guard<std::mutex> lock(state_mutex_);
        return joint_state_response(latest_joint_state_);
    }

    if (*cmd == "stop" || *cmd == "halt") {
        safety_.request_halt("remote halt command");
        ArmStatus refreshed_status;
        {
            std::lock_guard<std::mutex> transport_lock(transport_mutex_);
            transport_.stop_motion();
            refreshed_status = transport_.read_status();
        }
        std::lock_guard<std::mutex> lock(state_mutex_);
        latest_status_ = refreshed_status;
        latest_status_.motion_enabled = false;
        latest_status_.dry_run_only = true;
        latest_status_.last_update_ms = now_ms();
        return message_response(true, "halt requested", 0, "", true, false, true);
    }

    if (*cmd == "enable_motion") {
        safety_.clear_halt("remote enable_motion command");
        D1CommandResult result;
        ArmStatus refreshed_status;
        {
            std::lock_guard<std::mutex> transport_lock(transport_mutex_);
            result = transport_.set_motion_enabled(true);
            refreshed_status = transport_.read_status();
        }
        {
            std::lock_guard<std::mutex> lock(state_mutex_);
            latest_status_ = refreshed_status;
            latest_status_.last_update_ms = now_ms();
        }
        return command_response(result);
    }

    if (*cmd == "disable_motion") {
        safety_.request_halt("remote disable_motion command");
        D1CommandResult result;
        ArmStatus refreshed_status;
        {
            std::lock_guard<std::mutex> transport_lock(transport_mutex_);
            result = transport_.set_motion_enabled(false);
            refreshed_status = transport_.read_status();
        }
        {
            std::lock_guard<std::mutex> lock(state_mutex_);
            latest_status_ = refreshed_status;
            latest_status_.motion_enabled = false;
            latest_status_.dry_run_only = true;
            latest_status_.last_update_ms = now_ms();
        }
        return command_response(result);
    }

    if (*cmd == "set_joint_angle") {
        const auto payload = extract_object_field(request_text, "payload");
        if (!payload) {
            return message_response(false, "set_joint_angle payload must be a JSON object", error::kBadPayload, "bad_payload");
        }
        const auto joint_id = extract_int_field(*payload, "joint_id");
        const auto angle_deg = extract_double_field(*payload, "angle_deg");
        const auto delay_ms = extract_int_field(*payload, "delay_ms").value_or(0);
        if (!joint_id || !angle_deg) {
            return message_response(false, "set_joint_angle requires joint_id and angle_deg", error::kBadPayload, "bad_payload");
        }

        D1Command command;
        command.type = D1CommandType::SetJointAngle;
        command.joint_id = *joint_id;
        command.angle_deg = *angle_deg;
        command.delay_ms = delay_ms;

        D1CommandResult result;
        ArmStatus refreshed_status;
        {
            std::lock_guard<std::mutex> transport_lock(transport_mutex_);
            result = transport_.send_command(command);
            refreshed_status = transport_.read_status();
        }
        std::lock_guard<std::mutex> lock(state_mutex_);
        latest_status_ = refreshed_status;
        latest_status_.last_update_ms = now_ms();
        return command_response(result);
    }

    if (*cmd == "set_multi_joint_angle") {
        const auto payload = extract_object_field(request_text, "payload");
        if (!payload) {
            return message_response(false, "set_multi_joint_angle payload must be a JSON object", error::kBadPayload, "bad_payload");
        }
        auto raw_angles = extract_array_field(*payload, "angles_deg");
        if (!raw_angles) {
            raw_angles = extract_array_field(*payload, "angles");
        }
        if (!raw_angles) {
            return message_response(false, "set_multi_joint_angle requires angles_deg array", error::kBadPayload, "bad_payload");
        }
        const auto angles = parse_double_array(*raw_angles);
        if (!angles) {
            return message_response(false, "angles_deg must be an array of finite numbers", error::kBadPayload, "bad_payload");
        }

        D1Command command;
        command.type = D1CommandType::SetMultiJointAngle;
        command.mode = extract_int_field(*payload, "mode").value_or(1);
        command.angle_count = angles->size();
        if (command.angle_count > kD1CommandJointCount) {
            return message_response(false, "angles_deg may contain at most 7 values", error::kBadPayload, "bad_payload");
        }
        for (std::size_t idx = 0; idx < command.angle_count; ++idx) {
            command.angles_deg[idx] = (*angles)[idx];
        }

        D1CommandResult result;
        ArmStatus refreshed_status;
        {
            std::lock_guard<std::mutex> transport_lock(transport_mutex_);
            result = transport_.send_command(command);
            refreshed_status = transport_.read_status();
        }
        std::lock_guard<std::mutex> lock(state_mutex_);
        latest_status_ = refreshed_status;
        latest_status_.last_update_ms = now_ms();
        return command_response(result);
    }

    if (*cmd == "zero_arm") {
        D1Command command;
        command.type = D1CommandType::ZeroArm;

        D1CommandResult result;
        ArmStatus refreshed_status;
        {
            std::lock_guard<std::mutex> transport_lock(transport_mutex_);
            result = transport_.send_command(command);
            refreshed_status = transport_.read_status();
        }
        std::lock_guard<std::mutex> lock(state_mutex_);
        latest_status_ = refreshed_status;
        latest_status_.last_update_ms = now_ms();
        return command_response(result);
    }

    if (*cmd == "dry_run") {
        const auto payload = extract_object_field(request_text, "payload");
        if (!payload) {
            return message_response(false, "dry_run payload must be a JSON object", error::kBadPayload, "bad_payload");
        }
        const auto kind = extract_string_field(*payload, "kind");
        if (!kind || kind->empty()) {
            return message_response(false, "dry_run payload.kind is required", error::kBadPayload, "bad_payload");
        }

        {
            std::lock_guard<std::mutex> lock(state_mutex_);
            if (dry_run_queue_.size() >= options_.max_dry_run_queue) {
                dry_run_queue_.pop_front();
            }
            dry_run_queue_.push_back(*payload);
            latest_status_.last_update_ms = now_ms();
        }

        log_line("INFO", "Accepted dry-run payload kind=" + *kind);
        return message_response(true, "accepted in dry-run only", 0, "", true, false, true);
    }

    return message_response(false, "unknown command: " + *cmd, error::kMalformedRequest, "unknown_command");
}

}  // namespace d1
