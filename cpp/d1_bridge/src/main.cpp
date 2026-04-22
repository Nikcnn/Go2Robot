#include "d1_bridge_server.hpp"

#include <atomic>
#include <chrono>
#include <csignal>
#include <cstdlib>
#include <iostream>
#include <optional>
#include <string>
#include <thread>

namespace {

std::atomic<bool> g_shutdown_requested{false};

void handle_signal(int /*signum*/) {
    g_shutdown_requested.store(true);
}

std::optional<std::string> env_string(const char* name) {
    const char* raw = std::getenv(name);
    if (raw == nullptr || *raw == '\0') {
        return std::nullopt;
    }
    return std::string(raw);
}

bool parse_bool(const std::string& value, bool fallback) {
    if (value == "1" || value == "true" || value == "TRUE" || value == "yes" || value == "on") {
        return true;
    }
    if (value == "0" || value == "false" || value == "FALSE" || value == "no" || value == "off") {
        return false;
    }
    return fallback;
}

template <typename Numeric, typename Parser>
Numeric env_number(const char* name, Numeric fallback, Parser parser) {
    const auto value = env_string(name);
    if (!value) {
        return fallback;
    }
    try {
        return parser(*value);
    } catch (...) {
        return fallback;
    }
}

void load_env_defaults(d1::D1BridgeServerOptions& options) {
    options.socket_path = env_string("D1_BRIDGE_SOCKET").value_or(options.socket_path);
    options.interface_name = env_string("D1_INTERFACE_NAME").value_or(options.interface_name);
    options.servo_topic = env_string("D1_SERVO_TOPIC").value_or(options.servo_topic);
    options.feedback_topic = env_string("D1_FEEDBACK_TOPIC_PRIMARY").value_or(options.feedback_topic);
    options.feedback_topic_fallback = env_string("D1_FEEDBACK_TOPIC_FALLBACK").value_or(options.feedback_topic_fallback);
    options.command_topic = env_string("D1_COMMAND_TOPIC").value_or(options.command_topic);
    if (const auto value = env_string("D1_ENABLE_MOTION")) {
        options.enable_motion = parse_bool(*value, options.enable_motion);
    }
    if (const auto value = env_string("D1_DRY_RUN_FALLBACK")) {
        options.dry_run_fallback = parse_bool(*value, options.dry_run_fallback);
    }
    options.max_joint_delta_deg = env_number<double>("D1_MAX_JOINT_DELTA_DEG", options.max_joint_delta_deg, [](const std::string& text) {
        return std::stod(text);
    });
    options.command_rate_limit_hz = env_number<double>("D1_COMMAND_RATE_LIMIT_HZ", options.command_rate_limit_hz, [](const std::string& text) {
        return std::stod(text);
    });
    options.joint_min_deg = env_number<double>("D1_JOINT_MIN_DEG", options.joint_min_deg, [](const std::string& text) {
        return std::stod(text);
    });
    options.joint_max_deg = env_number<double>("D1_JOINT_MAX_DEG", options.joint_max_deg, [](const std::string& text) {
        return std::stod(text);
    });
    options.stale_timeout_ms = env_number<std::int64_t>("D1_STALE_TIMEOUT_MS", options.stale_timeout_ms, [](const std::string& text) {
        return std::stoll(text);
    });
    options.poll_period_ms = env_number<std::int64_t>("D1_POLL_MS", options.poll_period_ms, [](const std::string& text) {
        return std::stoll(text);
    });
    options.watchdog_timeout_ms = env_number<std::int64_t>("D1_WATCHDOG_MS", options.watchdog_timeout_ms, [](const std::string& text) {
        return std::stoll(text);
    });
}

void print_usage(const char* executable) {
    std::cout
        << "Usage: " << executable << "\n"
        << "  [--socket PATH] [--mock] [--interface NIC]\n"
        << "  [--servo-topic TOPIC] [--feedback-topic TOPIC] [--feedback-topic-fallback TOPIC] [--command-topic TOPIC]\n"
        << "  [--enable-motion] [--disable-motion] [--dry-run-fallback] [--no-dry-run-fallback]\n"
        << "  [--max-joint-delta-deg N] [--command-rate-limit-hz N] [--joint-min-deg N] [--joint-max-deg N]\n"
        << "  [--stale-timeout-ms N] [--poll-ms N] [--watchdog-ms N]\n\n"
        << "Defaults remain safety-first: mock mode is opt-in and real motion publishing is OFF until --enable-motion\n"
        << "or D1_ENABLE_MOTION=true is set. Even then, clients must still send the explicit enable_motion socket command.\n";
}

}  // namespace

int main(int argc, char** argv) {
    d1::D1BridgeServerOptions options;
    load_env_defaults(options);

    for (int idx = 1; idx < argc; ++idx) {
        const std::string arg = argv[idx];
        if (arg == "--socket" && (idx + 1) < argc) {
            options.socket_path = argv[++idx];
            continue;
        }
        if (arg == "--mock") {
            options.mock_mode = true;
            continue;
        }
        if (arg == "--interface" && (idx + 1) < argc) {
            options.interface_name = argv[++idx];
            continue;
        }
        if (arg == "--servo-topic" && (idx + 1) < argc) {
            options.servo_topic = argv[++idx];
            continue;
        }
        if (arg == "--feedback-topic" && (idx + 1) < argc) {
            options.feedback_topic = argv[++idx];
            continue;
        }
        if (arg == "--feedback-topic-fallback" && (idx + 1) < argc) {
            options.feedback_topic_fallback = argv[++idx];
            continue;
        }
        if (arg == "--command-topic" && (idx + 1) < argc) {
            options.command_topic = argv[++idx];
            continue;
        }
        if (arg == "--enable-motion") {
            options.enable_motion = true;
            continue;
        }
        if (arg == "--disable-motion") {
            options.enable_motion = false;
            continue;
        }
        if (arg == "--dry-run-fallback") {
            options.dry_run_fallback = true;
            continue;
        }
        if (arg == "--no-dry-run-fallback") {
            options.dry_run_fallback = false;
            continue;
        }
        if (arg == "--max-joint-delta-deg" && (idx + 1) < argc) {
            options.max_joint_delta_deg = std::stod(argv[++idx]);
            continue;
        }
        if (arg == "--command-rate-limit-hz" && (idx + 1) < argc) {
            options.command_rate_limit_hz = std::stod(argv[++idx]);
            continue;
        }
        if (arg == "--joint-min-deg" && (idx + 1) < argc) {
            options.joint_min_deg = std::stod(argv[++idx]);
            continue;
        }
        if (arg == "--joint-max-deg" && (idx + 1) < argc) {
            options.joint_max_deg = std::stod(argv[++idx]);
            continue;
        }
        if (arg == "--stale-timeout-ms" && (idx + 1) < argc) {
            options.stale_timeout_ms = std::stoll(argv[++idx]);
            continue;
        }
        if (arg == "--poll-ms" && (idx + 1) < argc) {
            options.poll_period_ms = std::stoll(argv[++idx]);
            continue;
        }
        if (arg == "--watchdog-ms" && (idx + 1) < argc) {
            options.watchdog_timeout_ms = std::stoll(argv[++idx]);
            continue;
        }
        if (arg == "--help" || arg == "-h") {
            print_usage(argv[0]);
            return 0;
        }

        std::cerr << "Unknown argument: " << arg << "\n";
        print_usage(argv[0]);
        return 1;
    }

    std::signal(SIGINT, handle_signal);
    std::signal(SIGTERM, handle_signal);

    d1::D1BridgeServer server(options);
    std::thread signal_watcher([&server]() {
        while (!g_shutdown_requested.load()) {
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
        }
        server.stop();
    });

    const bool ok = server.run();
    g_shutdown_requested.store(true);

    if (signal_watcher.joinable()) {
        signal_watcher.join();
    }

    return ok ? 0 : 1;
}
