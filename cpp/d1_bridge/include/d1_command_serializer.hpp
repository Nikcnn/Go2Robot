#pragma once

#include <cstdint>
#include <string>

#include "d1_command_model.hpp"

namespace d1 {

std::string serialize_command_payload(const D1Command& command, std::uint64_t seq);

}  // namespace d1
