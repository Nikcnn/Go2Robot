// generated from rosidl_generator_cpp/resource/idl__builder.hpp.em
// with input from go2_interfaces:srv/CheckpointCapture.idl
// generated code does not contain a copyright notice

#ifndef GO2_INTERFACES__SRV__DETAIL__CHECKPOINT_CAPTURE__BUILDER_HPP_
#define GO2_INTERFACES__SRV__DETAIL__CHECKPOINT_CAPTURE__BUILDER_HPP_

#include "go2_interfaces/srv/detail/checkpoint_capture__struct.hpp"
#include <rosidl_runtime_cpp/message_initialization.hpp>
#include <algorithm>
#include <utility>


namespace go2_interfaces
{

namespace srv
{

namespace builder
{

class Init_CheckpointCapture_Request_waypoint_id
{
public:
  Init_CheckpointCapture_Request_waypoint_id()
  : msg_(::rosidl_runtime_cpp::MessageInitialization::SKIP)
  {}
  ::go2_interfaces::srv::CheckpointCapture_Request waypoint_id(::go2_interfaces::srv::CheckpointCapture_Request::_waypoint_id_type arg)
  {
    msg_.waypoint_id = std::move(arg);
    return std::move(msg_);
  }

private:
  ::go2_interfaces::srv::CheckpointCapture_Request msg_;
};

}  // namespace builder

}  // namespace srv

template<typename MessageType>
auto build();

template<>
inline
auto build<::go2_interfaces::srv::CheckpointCapture_Request>()
{
  return go2_interfaces::srv::builder::Init_CheckpointCapture_Request_waypoint_id();
}

}  // namespace go2_interfaces


namespace go2_interfaces
{

namespace srv
{

namespace builder
{

class Init_CheckpointCapture_Response_pose_json
{
public:
  explicit Init_CheckpointCapture_Response_pose_json(::go2_interfaces::srv::CheckpointCapture_Response & msg)
  : msg_(msg)
  {}
  ::go2_interfaces::srv::CheckpointCapture_Response pose_json(::go2_interfaces::srv::CheckpointCapture_Response::_pose_json_type arg)
  {
    msg_.pose_json = std::move(arg);
    return std::move(msg_);
  }

private:
  ::go2_interfaces::srv::CheckpointCapture_Response msg_;
};

class Init_CheckpointCapture_Response_robot_state_json
{
public:
  explicit Init_CheckpointCapture_Response_robot_state_json(::go2_interfaces::srv::CheckpointCapture_Response & msg)
  : msg_(msg)
  {}
  Init_CheckpointCapture_Response_pose_json robot_state_json(::go2_interfaces::srv::CheckpointCapture_Response::_robot_state_json_type arg)
  {
    msg_.robot_state_json = std::move(arg);
    return Init_CheckpointCapture_Response_pose_json(msg_);
  }

private:
  ::go2_interfaces::srv::CheckpointCapture_Response msg_;
};

class Init_CheckpointCapture_Response_image_jpeg
{
public:
  explicit Init_CheckpointCapture_Response_image_jpeg(::go2_interfaces::srv::CheckpointCapture_Response & msg)
  : msg_(msg)
  {}
  Init_CheckpointCapture_Response_robot_state_json image_jpeg(::go2_interfaces::srv::CheckpointCapture_Response::_image_jpeg_type arg)
  {
    msg_.image_jpeg = std::move(arg);
    return Init_CheckpointCapture_Response_robot_state_json(msg_);
  }

private:
  ::go2_interfaces::srv::CheckpointCapture_Response msg_;
};

class Init_CheckpointCapture_Response_message
{
public:
  explicit Init_CheckpointCapture_Response_message(::go2_interfaces::srv::CheckpointCapture_Response & msg)
  : msg_(msg)
  {}
  Init_CheckpointCapture_Response_image_jpeg message(::go2_interfaces::srv::CheckpointCapture_Response::_message_type arg)
  {
    msg_.message = std::move(arg);
    return Init_CheckpointCapture_Response_image_jpeg(msg_);
  }

private:
  ::go2_interfaces::srv::CheckpointCapture_Response msg_;
};

class Init_CheckpointCapture_Response_success
{
public:
  Init_CheckpointCapture_Response_success()
  : msg_(::rosidl_runtime_cpp::MessageInitialization::SKIP)
  {}
  Init_CheckpointCapture_Response_message success(::go2_interfaces::srv::CheckpointCapture_Response::_success_type arg)
  {
    msg_.success = std::move(arg);
    return Init_CheckpointCapture_Response_message(msg_);
  }

private:
  ::go2_interfaces::srv::CheckpointCapture_Response msg_;
};

}  // namespace builder

}  // namespace srv

template<typename MessageType>
auto build();

template<>
inline
auto build<::go2_interfaces::srv::CheckpointCapture_Response>()
{
  return go2_interfaces::srv::builder::Init_CheckpointCapture_Response_success();
}

}  // namespace go2_interfaces

#endif  // GO2_INTERFACES__SRV__DETAIL__CHECKPOINT_CAPTURE__BUILDER_HPP_
