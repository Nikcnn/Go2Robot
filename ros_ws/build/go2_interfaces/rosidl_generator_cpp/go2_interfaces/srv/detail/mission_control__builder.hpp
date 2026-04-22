// generated from rosidl_generator_cpp/resource/idl__builder.hpp.em
// with input from go2_interfaces:srv/MissionControl.idl
// generated code does not contain a copyright notice

#ifndef GO2_INTERFACES__SRV__DETAIL__MISSION_CONTROL__BUILDER_HPP_
#define GO2_INTERFACES__SRV__DETAIL__MISSION_CONTROL__BUILDER_HPP_

#include "go2_interfaces/srv/detail/mission_control__struct.hpp"
#include <rosidl_runtime_cpp/message_initialization.hpp>
#include <algorithm>
#include <utility>


namespace go2_interfaces
{

namespace srv
{

namespace builder
{

class Init_MissionControl_Request_mission_json
{
public:
  explicit Init_MissionControl_Request_mission_json(::go2_interfaces::srv::MissionControl_Request & msg)
  : msg_(msg)
  {}
  ::go2_interfaces::srv::MissionControl_Request mission_json(::go2_interfaces::srv::MissionControl_Request::_mission_json_type arg)
  {
    msg_.mission_json = std::move(arg);
    return std::move(msg_);
  }

private:
  ::go2_interfaces::srv::MissionControl_Request msg_;
};

class Init_MissionControl_Request_mission_path
{
public:
  explicit Init_MissionControl_Request_mission_path(::go2_interfaces::srv::MissionControl_Request & msg)
  : msg_(msg)
  {}
  Init_MissionControl_Request_mission_json mission_path(::go2_interfaces::srv::MissionControl_Request::_mission_path_type arg)
  {
    msg_.mission_path = std::move(arg);
    return Init_MissionControl_Request_mission_json(msg_);
  }

private:
  ::go2_interfaces::srv::MissionControl_Request msg_;
};

class Init_MissionControl_Request_command
{
public:
  Init_MissionControl_Request_command()
  : msg_(::rosidl_runtime_cpp::MessageInitialization::SKIP)
  {}
  Init_MissionControl_Request_mission_path command(::go2_interfaces::srv::MissionControl_Request::_command_type arg)
  {
    msg_.command = std::move(arg);
    return Init_MissionControl_Request_mission_path(msg_);
  }

private:
  ::go2_interfaces::srv::MissionControl_Request msg_;
};

}  // namespace builder

}  // namespace srv

template<typename MessageType>
auto build();

template<>
inline
auto build<::go2_interfaces::srv::MissionControl_Request>()
{
  return go2_interfaces::srv::builder::Init_MissionControl_Request_command();
}

}  // namespace go2_interfaces


namespace go2_interfaces
{

namespace srv
{

namespace builder
{

class Init_MissionControl_Response_state_json
{
public:
  explicit Init_MissionControl_Response_state_json(::go2_interfaces::srv::MissionControl_Response & msg)
  : msg_(msg)
  {}
  ::go2_interfaces::srv::MissionControl_Response state_json(::go2_interfaces::srv::MissionControl_Response::_state_json_type arg)
  {
    msg_.state_json = std::move(arg);
    return std::move(msg_);
  }

private:
  ::go2_interfaces::srv::MissionControl_Response msg_;
};

class Init_MissionControl_Response_mission_id
{
public:
  explicit Init_MissionControl_Response_mission_id(::go2_interfaces::srv::MissionControl_Response & msg)
  : msg_(msg)
  {}
  Init_MissionControl_Response_state_json mission_id(::go2_interfaces::srv::MissionControl_Response::_mission_id_type arg)
  {
    msg_.mission_id = std::move(arg);
    return Init_MissionControl_Response_state_json(msg_);
  }

private:
  ::go2_interfaces::srv::MissionControl_Response msg_;
};

class Init_MissionControl_Response_message
{
public:
  explicit Init_MissionControl_Response_message(::go2_interfaces::srv::MissionControl_Response & msg)
  : msg_(msg)
  {}
  Init_MissionControl_Response_mission_id message(::go2_interfaces::srv::MissionControl_Response::_message_type arg)
  {
    msg_.message = std::move(arg);
    return Init_MissionControl_Response_mission_id(msg_);
  }

private:
  ::go2_interfaces::srv::MissionControl_Response msg_;
};

class Init_MissionControl_Response_success
{
public:
  Init_MissionControl_Response_success()
  : msg_(::rosidl_runtime_cpp::MessageInitialization::SKIP)
  {}
  Init_MissionControl_Response_message success(::go2_interfaces::srv::MissionControl_Response::_success_type arg)
  {
    msg_.success = std::move(arg);
    return Init_MissionControl_Response_message(msg_);
  }

private:
  ::go2_interfaces::srv::MissionControl_Response msg_;
};

}  // namespace builder

}  // namespace srv

template<typename MessageType>
auto build();

template<>
inline
auto build<::go2_interfaces::srv::MissionControl_Response>()
{
  return go2_interfaces::srv::builder::Init_MissionControl_Response_success();
}

}  // namespace go2_interfaces

#endif  // GO2_INTERFACES__SRV__DETAIL__MISSION_CONTROL__BUILDER_HPP_
