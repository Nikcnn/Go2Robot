#include "d1_command_serializer.hpp"

#include <iomanip>
#include <sstream>
#include <stdexcept>

namespace d1 {

namespace {

void write_number_field(std::ostringstream& out, const char* key, double value, bool last = false) {
    out << "\"" << key << "\":" << std::fixed << std::setprecision(6) << value;
    if (!last) {
        out << ",";
    }
}

}  // namespace

std::string serialize_command_payload(const D1Command& command, std::uint64_t seq) {
    std::ostringstream out;
    out << "{"
        << "\"seq\":" << seq << ","
        << "\"address\":1,";

    switch (command.type) {
        case D1CommandType::EnableMotion:
            out << "\"funcode\":5,"
                << "\"data\":{\"mode\":1}"
                << "}";
            return out.str();

        case D1CommandType::DisableMotion:
        case D1CommandType::Halt:
            out << "\"funcode\":5,"
                << "\"data\":{\"mode\":0}"
                << "}";
            return out.str();

        case D1CommandType::SetJointAngle:
            out << "\"funcode\":1,"
                << "\"data\":{"
                << "\"id\":" << command.joint_id << ","
                << "\"angle\":" << std::fixed << std::setprecision(6) << command.angle_deg << ","
                << "\"delay_ms\":" << command.delay_ms
                << "}"
                << "}";
            return out.str();

        case D1CommandType::SetMultiJointAngle:
            out << "\"funcode\":2,"
                << "\"data\":{"
                << "\"mode\":" << command.mode << ",";
            for (std::size_t idx = 0; idx < kD1CommandJointCount; ++idx) {
                write_number_field(out, ("angle" + std::to_string(idx)).c_str(), command.angles_deg[idx], idx + 1 == kD1CommandJointCount);
            }
            out << "}"
                << "}";
            return out.str();

        case D1CommandType::ZeroArm:
            out << "\"funcode\":7"
                << "}";
            return out.str();
    }

    throw std::runtime_error("unsupported D1 command type");
}

}  // namespace d1
