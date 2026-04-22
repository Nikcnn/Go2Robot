// generated from rosidl_generator_cpp/resource/idl__struct.hpp.em
// with input from go2_interfaces:srv/MissionControl.idl
// generated code does not contain a copyright notice

#ifndef GO2_INTERFACES__SRV__DETAIL__MISSION_CONTROL__STRUCT_HPP_
#define GO2_INTERFACES__SRV__DETAIL__MISSION_CONTROL__STRUCT_HPP_

#include <rosidl_runtime_cpp/bounded_vector.hpp>
#include <rosidl_runtime_cpp/message_initialization.hpp>
#include <algorithm>
#include <array>
#include <memory>
#include <string>
#include <vector>


#ifndef _WIN32
# define DEPRECATED__go2_interfaces__srv__MissionControl_Request __attribute__((deprecated))
#else
# define DEPRECATED__go2_interfaces__srv__MissionControl_Request __declspec(deprecated)
#endif

namespace go2_interfaces
{

namespace srv
{

// message struct
template<class ContainerAllocator>
struct MissionControl_Request_
{
  using Type = MissionControl_Request_<ContainerAllocator>;

  explicit MissionControl_Request_(rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  {
    if (rosidl_runtime_cpp::MessageInitialization::ALL == _init ||
      rosidl_runtime_cpp::MessageInitialization::ZERO == _init)
    {
      this->command = "";
      this->mission_path = "";
      this->mission_json = "";
    }
  }

  explicit MissionControl_Request_(const ContainerAllocator & _alloc, rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  : command(_alloc),
    mission_path(_alloc),
    mission_json(_alloc)
  {
    if (rosidl_runtime_cpp::MessageInitialization::ALL == _init ||
      rosidl_runtime_cpp::MessageInitialization::ZERO == _init)
    {
      this->command = "";
      this->mission_path = "";
      this->mission_json = "";
    }
  }

  // field types and members
  using _command_type =
    std::basic_string<char, std::char_traits<char>, typename ContainerAllocator::template rebind<char>::other>;
  _command_type command;
  using _mission_path_type =
    std::basic_string<char, std::char_traits<char>, typename ContainerAllocator::template rebind<char>::other>;
  _mission_path_type mission_path;
  using _mission_json_type =
    std::basic_string<char, std::char_traits<char>, typename ContainerAllocator::template rebind<char>::other>;
  _mission_json_type mission_json;

  // setters for named parameter idiom
  Type & set__command(
    const std::basic_string<char, std::char_traits<char>, typename ContainerAllocator::template rebind<char>::other> & _arg)
  {
    this->command = _arg;
    return *this;
  }
  Type & set__mission_path(
    const std::basic_string<char, std::char_traits<char>, typename ContainerAllocator::template rebind<char>::other> & _arg)
  {
    this->mission_path = _arg;
    return *this;
  }
  Type & set__mission_json(
    const std::basic_string<char, std::char_traits<char>, typename ContainerAllocator::template rebind<char>::other> & _arg)
  {
    this->mission_json = _arg;
    return *this;
  }

  // constant declarations

  // pointer types
  using RawPtr =
    go2_interfaces::srv::MissionControl_Request_<ContainerAllocator> *;
  using ConstRawPtr =
    const go2_interfaces::srv::MissionControl_Request_<ContainerAllocator> *;
  using SharedPtr =
    std::shared_ptr<go2_interfaces::srv::MissionControl_Request_<ContainerAllocator>>;
  using ConstSharedPtr =
    std::shared_ptr<go2_interfaces::srv::MissionControl_Request_<ContainerAllocator> const>;

  template<typename Deleter = std::default_delete<
      go2_interfaces::srv::MissionControl_Request_<ContainerAllocator>>>
  using UniquePtrWithDeleter =
    std::unique_ptr<go2_interfaces::srv::MissionControl_Request_<ContainerAllocator>, Deleter>;

  using UniquePtr = UniquePtrWithDeleter<>;

  template<typename Deleter = std::default_delete<
      go2_interfaces::srv::MissionControl_Request_<ContainerAllocator>>>
  using ConstUniquePtrWithDeleter =
    std::unique_ptr<go2_interfaces::srv::MissionControl_Request_<ContainerAllocator> const, Deleter>;
  using ConstUniquePtr = ConstUniquePtrWithDeleter<>;

  using WeakPtr =
    std::weak_ptr<go2_interfaces::srv::MissionControl_Request_<ContainerAllocator>>;
  using ConstWeakPtr =
    std::weak_ptr<go2_interfaces::srv::MissionControl_Request_<ContainerAllocator> const>;

  // pointer types similar to ROS 1, use SharedPtr / ConstSharedPtr instead
  // NOTE: Can't use 'using' here because GNU C++ can't parse attributes properly
  typedef DEPRECATED__go2_interfaces__srv__MissionControl_Request
    std::shared_ptr<go2_interfaces::srv::MissionControl_Request_<ContainerAllocator>>
    Ptr;
  typedef DEPRECATED__go2_interfaces__srv__MissionControl_Request
    std::shared_ptr<go2_interfaces::srv::MissionControl_Request_<ContainerAllocator> const>
    ConstPtr;

  // comparison operators
  bool operator==(const MissionControl_Request_ & other) const
  {
    if (this->command != other.command) {
      return false;
    }
    if (this->mission_path != other.mission_path) {
      return false;
    }
    if (this->mission_json != other.mission_json) {
      return false;
    }
    return true;
  }
  bool operator!=(const MissionControl_Request_ & other) const
  {
    return !this->operator==(other);
  }
};  // struct MissionControl_Request_

// alias to use template instance with default allocator
using MissionControl_Request =
  go2_interfaces::srv::MissionControl_Request_<std::allocator<void>>;

// constant definitions

}  // namespace srv

}  // namespace go2_interfaces


#ifndef _WIN32
# define DEPRECATED__go2_interfaces__srv__MissionControl_Response __attribute__((deprecated))
#else
# define DEPRECATED__go2_interfaces__srv__MissionControl_Response __declspec(deprecated)
#endif

namespace go2_interfaces
{

namespace srv
{

// message struct
template<class ContainerAllocator>
struct MissionControl_Response_
{
  using Type = MissionControl_Response_<ContainerAllocator>;

  explicit MissionControl_Response_(rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  {
    if (rosidl_runtime_cpp::MessageInitialization::ALL == _init ||
      rosidl_runtime_cpp::MessageInitialization::ZERO == _init)
    {
      this->success = false;
      this->message = "";
      this->mission_id = "";
      this->state_json = "";
    }
  }

  explicit MissionControl_Response_(const ContainerAllocator & _alloc, rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  : message(_alloc),
    mission_id(_alloc),
    state_json(_alloc)
  {
    if (rosidl_runtime_cpp::MessageInitialization::ALL == _init ||
      rosidl_runtime_cpp::MessageInitialization::ZERO == _init)
    {
      this->success = false;
      this->message = "";
      this->mission_id = "";
      this->state_json = "";
    }
  }

  // field types and members
  using _success_type =
    bool;
  _success_type success;
  using _message_type =
    std::basic_string<char, std::char_traits<char>, typename ContainerAllocator::template rebind<char>::other>;
  _message_type message;
  using _mission_id_type =
    std::basic_string<char, std::char_traits<char>, typename ContainerAllocator::template rebind<char>::other>;
  _mission_id_type mission_id;
  using _state_json_type =
    std::basic_string<char, std::char_traits<char>, typename ContainerAllocator::template rebind<char>::other>;
  _state_json_type state_json;

  // setters for named parameter idiom
  Type & set__success(
    const bool & _arg)
  {
    this->success = _arg;
    return *this;
  }
  Type & set__message(
    const std::basic_string<char, std::char_traits<char>, typename ContainerAllocator::template rebind<char>::other> & _arg)
  {
    this->message = _arg;
    return *this;
  }
  Type & set__mission_id(
    const std::basic_string<char, std::char_traits<char>, typename ContainerAllocator::template rebind<char>::other> & _arg)
  {
    this->mission_id = _arg;
    return *this;
  }
  Type & set__state_json(
    const std::basic_string<char, std::char_traits<char>, typename ContainerAllocator::template rebind<char>::other> & _arg)
  {
    this->state_json = _arg;
    return *this;
  }

  // constant declarations

  // pointer types
  using RawPtr =
    go2_interfaces::srv::MissionControl_Response_<ContainerAllocator> *;
  using ConstRawPtr =
    const go2_interfaces::srv::MissionControl_Response_<ContainerAllocator> *;
  using SharedPtr =
    std::shared_ptr<go2_interfaces::srv::MissionControl_Response_<ContainerAllocator>>;
  using ConstSharedPtr =
    std::shared_ptr<go2_interfaces::srv::MissionControl_Response_<ContainerAllocator> const>;

  template<typename Deleter = std::default_delete<
      go2_interfaces::srv::MissionControl_Response_<ContainerAllocator>>>
  using UniquePtrWithDeleter =
    std::unique_ptr<go2_interfaces::srv::MissionControl_Response_<ContainerAllocator>, Deleter>;

  using UniquePtr = UniquePtrWithDeleter<>;

  template<typename Deleter = std::default_delete<
      go2_interfaces::srv::MissionControl_Response_<ContainerAllocator>>>
  using ConstUniquePtrWithDeleter =
    std::unique_ptr<go2_interfaces::srv::MissionControl_Response_<ContainerAllocator> const, Deleter>;
  using ConstUniquePtr = ConstUniquePtrWithDeleter<>;

  using WeakPtr =
    std::weak_ptr<go2_interfaces::srv::MissionControl_Response_<ContainerAllocator>>;
  using ConstWeakPtr =
    std::weak_ptr<go2_interfaces::srv::MissionControl_Response_<ContainerAllocator> const>;

  // pointer types similar to ROS 1, use SharedPtr / ConstSharedPtr instead
  // NOTE: Can't use 'using' here because GNU C++ can't parse attributes properly
  typedef DEPRECATED__go2_interfaces__srv__MissionControl_Response
    std::shared_ptr<go2_interfaces::srv::MissionControl_Response_<ContainerAllocator>>
    Ptr;
  typedef DEPRECATED__go2_interfaces__srv__MissionControl_Response
    std::shared_ptr<go2_interfaces::srv::MissionControl_Response_<ContainerAllocator> const>
    ConstPtr;

  // comparison operators
  bool operator==(const MissionControl_Response_ & other) const
  {
    if (this->success != other.success) {
      return false;
    }
    if (this->message != other.message) {
      return false;
    }
    if (this->mission_id != other.mission_id) {
      return false;
    }
    if (this->state_json != other.state_json) {
      return false;
    }
    return true;
  }
  bool operator!=(const MissionControl_Response_ & other) const
  {
    return !this->operator==(other);
  }
};  // struct MissionControl_Response_

// alias to use template instance with default allocator
using MissionControl_Response =
  go2_interfaces::srv::MissionControl_Response_<std::allocator<void>>;

// constant definitions

}  // namespace srv

}  // namespace go2_interfaces

namespace go2_interfaces
{

namespace srv
{

struct MissionControl
{
  using Request = go2_interfaces::srv::MissionControl_Request;
  using Response = go2_interfaces::srv::MissionControl_Response;
};

}  // namespace srv

}  // namespace go2_interfaces

#endif  // GO2_INTERFACES__SRV__DETAIL__MISSION_CONTROL__STRUCT_HPP_
