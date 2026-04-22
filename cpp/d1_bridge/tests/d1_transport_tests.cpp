#include "d1_bridge_server.hpp"
#include "d1_transport.hpp"
#include "d1_transport_detail.hpp"

#include <cstdlib>
#include <iostream>
#include <string>

namespace {

void require_true(bool condition, const std::string& message) {
    if (!condition) {
        std::cerr << "FAILED: " << message << std::endl;
        std::exit(1);
    }
}

void test_feedback_json_parsing() {
    const d1::ArmStatus previous{};
    const auto parsed = d1::detail::parse_arm_feedback_json(
        "{\"seq\":10,\"address\":2,\"funcode\":3,\"data\":{\"enable_status\":1,\"power_status\":1,\"error_status\":1}}",
        previous,
        1000);

    require_true(parsed.parsed, "expected funcode=3 feedback JSON to parse");
    require_true(parsed.status.error_code == 0, "expected clean status feedback to keep error_code=0");
    require_true(parsed.status.last_error_message.empty(), "expected clean status feedback to clear last_error_message");

    const auto ack = d1::detail::parse_arm_feedback_json(
        "{\"seq\":3,\"address\":3,\"funcode\":2,\"data\":{\"exec_status\":0}}",
        previous,
        1000);

    require_true(ack.parsed, "expected exec ack JSON to parse");
    require_true(ack.status.error_code != 0, "expected failed exec ack to set a non-zero error_code");
    require_true(ack.status.last_error_message.find("exec_status") != std::string::npos,
                 "expected failed exec ack to mention exec_status");
}

void test_freshness_logic_marks_stale_data_invalid() {
    d1::JointState joint{};
    joint.valid = true;
    joint.stamp_ms = 1000;

    const auto stale_joint = d1::detail::apply_joint_freshness(joint, 1000, 1500, 3000);
    require_true(!stale_joint.valid, "expected stale joint feedback to become invalid");

    d1::ArmStatus status{};
    status.connected = true;
    status.last_update_ms = 1000;

    const auto stale_status = d1::detail::apply_status_freshness(status, 1000, 1000, 1500, 3000, false);
    require_true(!stale_status.connected, "expected stale status feedback to become disconnected");
    require_true(stale_status.last_error_message.find("stale") != std::string::npos,
                 "expected stale status to mention staleness");
}

void test_stop_motion_is_software_only() {
    d1::D1Transport transport(d1::D1TransportOptions{});

    require_true(transport.stop_motion(), "expected software-only stop_motion to succeed");

    const auto status = transport.read_status();
    require_true(status.motion_enabled == false, "expected stop_motion to keep motion disabled");
    require_true(status.dry_run_only, "expected stop_motion path to stay dry-run only");
    require_true(status.last_error_message.find("software halt") != std::string::npos,
                 "expected stop_motion to report a software halt message");
}

void test_mock_backend_status_and_joint_flow() {
    d1::D1TransportOptions options;
    options.mock_mode = true;
    options.enable_motion = true;
    d1::D1Transport transport(options);

    require_true(transport.connect(), "expected mock backend to connect");

    const auto status = transport.read_status();
    const auto joints = transport.read_joint_state();

    require_true(status.connected, "expected mock status to be connected");
    require_true(status.backend == "mock", "expected mock backend label");
    require_true(status.dry_run_only, "expected mock backend to remain dry-run");
    require_true(joints.valid, "expected mock joint state to be valid");
}

void test_motion_rejected_when_bridge_motion_config_is_disabled() {
    d1::D1TransportOptions options;
    options.mock_mode = true;
    options.enable_motion = false;
    d1::D1Transport transport(options);
    require_true(transport.connect(), "expected mock backend to connect");

    d1::D1Command command;
    command.type = d1::D1CommandType::SetJointAngle;
    command.joint_id = 1;
    command.angle_deg = 12.0;

    const auto result = transport.send_command(command);

    require_true(!result.ok, "expected motion command to be rejected when enable_motion=false");
    require_true(result.error_code == d1::error::kMotionDisabledByConfig,
                 "expected config gate rejection code");
}

void test_socket_protocol_rejects_malformed_payloads() {
    d1::D1BridgeServerOptions options;
    options.mock_mode = true;
    d1::D1BridgeServer server(options);

    const auto missing_payload = server.handle_request_for_test("{\"cmd\":\"set_joint_angle\"}");
    require_true(missing_payload.find("\"ok\":false") != std::string::npos,
                 "expected missing set_joint_angle payload to fail");
    require_true(missing_payload.find("bad_payload") != std::string::npos,
                 "expected missing payload error kind");

    const auto bad_multi = server.handle_request_for_test(
        "{\"cmd\":\"set_multi_joint_angle\",\"payload\":{\"angles_deg\":[0.0,1.0,bad]}}");
    require_true(bad_multi.find("\"ok\":false") != std::string::npos,
                 "expected malformed angles array to fail");
    require_true(bad_multi.find("bad_payload") != std::string::npos,
                 "expected malformed angles array error kind");
}

}  // namespace

int main() {
    test_feedback_json_parsing();
    test_freshness_logic_marks_stale_data_invalid();
    test_stop_motion_is_software_only();
    test_mock_backend_status_and_joint_flow();
    test_motion_rejected_when_bridge_motion_config_is_disabled();
    test_socket_protocol_rejects_malformed_payloads();
    std::cout << "d1_transport_tests passed" << std::endl;
    return 0;
}
