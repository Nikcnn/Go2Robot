// generated from rosidl_generator_cpp/resource/idl__struct.hpp.em
// with input from go2_interfaces:srv/CheckpointCapture.idl
// generated code does not contain a copyright notice

#ifndef GO2_INTERFACES__SRV__DETAIL__CHECKPOINT_CAPTURE__STRUCT_HPP_
#define GO2_INTERFACES__SRV__DETAIL__CHECKPOINT_CAPTURE__STRUCT_HPP_

#include <rosidl_runtime_cpp/bounded_vector.hpp>
#include <rosidl_runtime_cpp/message_initialization.hpp>
#include <algorithm>
#include <array>
#include <memory>
#include <string>
#include <vector>


#ifndef _WIN32
# define DEPRECATED__go2_interfaces__srv__CheckpointCapture_Request __attribute__((deprecated))
#else
# define DEPRECATED__go2_interfaces__srv__CheckpointCapture_Request __declspec(deprecated)
#endif

namespace go2_interfaces
{

namespace srv
{

// message struct
template<class ContainerAllocator>
struct CheckpointCapture_Request_
{
  using Type = CheckpointCapture_Request_<ContainerAllocator>;

  explicit CheckpointCapture_Request_(rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  {
    if (rosidl_runtime_cpp::MessageInitialization::ALL == _init ||
      rosidl_runtime_cpp::MessageInitialization::ZERO == _init)
    {
      this->waypoint_id = "";
    }
  }

  explicit CheckpointCapture_Request_(const ContainerAllocator & _alloc, rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  : waypoint_id(_alloc)
  {
    if (rosidl_runtime_cpp::MessageInitialization::ALL == _init ||
      rosidl_runtime_cpp::MessageInitialization::ZERO == _init)
    {
      this->waypoint_id = "";
    }
  }

  // field types and members
  using _waypoint_id_type =
    std::basic_string<char, std::char_traits<char>, typename ContainerAllocator::template rebind<char>::other>;
  _waypoint_id_type waypoint_id;

  // setters for named parameter idiom
  Type & set__waypoint_id(
    const std::basic_string<char, std::char_traits<char>, typename ContainerAllocator::template rebind<char>::other> & _arg)
  {
    this->waypoint_id = _arg;
    return *this;
  }

  // constant declarations

  // pointer types
  using RawPtr =
    go2_interfaces::srv::CheckpointCapture_Request_<ContainerAllocator> *;
  using ConstRawPtr =
    const go2_interfaces::srv::CheckpointCapture_Request_<ContainerAllocator> *;
  using SharedPtr =
    std::shared_ptr<go2_interfaces::srv::CheckpointCapture_Request_<ContainerAllocator>>;
  using ConstSharedPtr =
    std::shared_ptr<go2_interfaces::srv::CheckpointCapture_Request_<ContainerAllocator> const>;

  template<typename Deleter = std::default_delete<
      go2_interfaces::srv::CheckpointCapture_Request_<ContainerAllocator>>>
  using UniquePtrWithDeleter =
    std::unique_ptr<go2_interfaces::srv::CheckpointCapture_Request_<ContainerAllocator>, Deleter>;

  using UniquePtr = UniquePtrWithDeleter<>;

  template<typename Deleter = std::default_delete<
      go2_interfaces::srv::CheckpointCapture_Request_<ContainerAllocator>>>
  using ConstUniquePtrWithDeleter =
    std::unique_ptr<go2_interfaces::srv::CheckpointCapture_Request_<ContainerAllocator> const, Deleter>;
  using ConstUniquePtr = ConstUniquePtrWithDeleter<>;

  using WeakPtr =
    std::weak_ptr<go2_interfaces::srv::CheckpointCapture_Request_<ContainerAllocator>>;
  using ConstWeakPtr =
    std::weak_ptr<go2_interfaces::srv::CheckpointCapture_Request_<ContainerAllocator> const>;

  // pointer types similar to ROS 1, use SharedPtr / ConstSharedPtr instead
  // NOTE: Can't use 'using' here because GNU C++ can't parse attributes properly
  typedef DEPRECATED__go2_interfaces__srv__CheckpointCapture_Request
    std::shared_ptr<go2_interfaces::srv::CheckpointCapture_Request_<ContainerAllocator>>
    Ptr;
  typedef DEPRECATED__go2_interfaces__srv__CheckpointCapture_Request
    std::shared_ptr<go2_interfaces::srv::CheckpointCapture_Request_<ContainerAllocator> const>
    ConstPtr;

  // comparison operators
  bool operator==(const CheckpointCapture_Request_ & other) const
  {
    if (this->waypoint_id != other.waypoint_id) {
      return false;
    }
    return true;
  }
  bool operator!=(const CheckpointCapture_Request_ & other) const
  {
    return !this->operator==(other);
  }
};  // struct CheckpointCapture_Request_

// alias to use template instance with default allocator
using CheckpointCapture_Request =
  go2_interfaces::srv::CheckpointCapture_Request_<std::allocator<void>>;

// constant definitions

}  // namespace srv

}  // namespace go2_interfaces


#ifndef _WIN32
# define DEPRECATED__go2_interfaces__srv__CheckpointCapture_Response __attribute__((deprecated))
#else
# define DEPRECATED__go2_interfaces__srv__CheckpointCapture_Response __declspec(deprecated)
#endif

namespace go2_interfaces
{

namespace srv
{

// message struct
template<class ContainerAllocator>
struct CheckpointCapture_Response_
{
  using Type = CheckpointCapture_Response_<ContainerAllocator>;

  explicit CheckpointCapture_Response_(rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  {
    if (rosidl_runtime_cpp::MessageInitialization::ALL == _init ||
      rosidl_runtime_cpp::MessageInitialization::ZERO == _init)
    {
      this->success = false;
      this->message = "";
      this->robot_state_json = "";
      this->pose_json = "";
    }
  }

  explicit CheckpointCapture_Response_(const ContainerAllocator & _alloc, rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  : message(_alloc),
    robot_state_json(_alloc),
    pose_json(_alloc)
  {
    if (rosidl_runtime_cpp::MessageInitialization::ALL == _init ||
      rosidl_runtime_cpp::MessageInitialization::ZERO == _init)
    {
      this->success = false;
      this->message = "";
      this->robot_state_json = "";
      this->pose_json = "";
    }
  }

  // field types and members
  using _success_type =
    bool;
  _success_type success;
  using _message_type =
    std::basic_string<char, std::char_traits<char>, typename ContainerAllocator::template rebind<char>::other>;
  _message_type message;
  using _image_jpeg_type =
    std::vector<uint8_t, typename ContainerAllocator::template rebind<uint8_t>::other>;
  _image_jpeg_type image_jpeg;
  using _robot_state_json_type =
    std::basic_string<char, std::char_traits<char>, typename ContainerAllocator::template rebind<char>::other>;
  _robot_state_json_type robot_state_json;
  using _pose_json_type =
    std::basic_string<char, std::char_traits<char>, typename ContainerAllocator::template rebind<char>::other>;
  _pose_json_type pose_json;

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
  Type & set__image_jpeg(
    const std::vector<uint8_t, typename ContainerAllocator::template rebind<uint8_t>::other> & _arg)
  {
    this->image_jpeg = _arg;
    return *this;
  }
  Type & set__robot_state_json(
    const std::basic_string<char, std::char_traits<char>, typename ContainerAllocator::template rebind<char>::other> & _arg)
  {
    this->robot_state_json = _arg;
    return *this;
  }
  Type & set__pose_json(
    const std::basic_string<char, std::char_traits<char>, typename ContainerAllocator::template rebind<char>::other> & _arg)
  {
    this->pose_json = _arg;
    return *this;
  }

  // constant declarations

  // pointer types
  using RawPtr =
    go2_interfaces::srv::CheckpointCapture_Response_<ContainerAllocator> *;
  using ConstRawPtr =
    const go2_interfaces::srv::CheckpointCapture_Response_<ContainerAllocator> *;
  using SharedPtr =
    std::shared_ptr<go2_interfaces::srv::CheckpointCapture_Response_<ContainerAllocator>>;
  using ConstSharedPtr =
    std::shared_ptr<go2_interfaces::srv::CheckpointCapture_Response_<ContainerAllocator> const>;

  template<typename Deleter = std::default_delete<
      go2_interfaces::srv::CheckpointCapture_Response_<ContainerAllocator>>>
  using UniquePtrWithDeleter =
    std::unique_ptr<go2_interfaces::srv::CheckpointCapture_Response_<ContainerAllocator>, Deleter>;

  using UniquePtr = UniquePtrWithDeleter<>;

  template<typename Deleter = std::default_delete<
      go2_interfaces::srv::CheckpointCapture_Response_<ContainerAllocator>>>
  using ConstUniquePtrWithDeleter =
    std::unique_ptr<go2_interfaces::srv::CheckpointCapture_Response_<ContainerAllocator> const, Deleter>;
  using ConstUniquePtr = ConstUniquePtrWithDeleter<>;

  using WeakPtr =
    std::weak_ptr<go2_interfaces::srv::CheckpointCapture_Response_<ContainerAllocator>>;
  using ConstWeakPtr =
    std::weak_ptr<go2_interfaces::srv::CheckpointCapture_Response_<ContainerAllocator> const>;

  // pointer types similar to ROS 1, use SharedPtr / ConstSharedPtr instead
  // NOTE: Can't use 'using' here because GNU C++ can't parse attributes properly
  typedef DEPRECATED__go2_interfaces__srv__CheckpointCapture_Response
    std::shared_ptr<go2_interfaces::srv::CheckpointCapture_Response_<ContainerAllocator>>
    Ptr;
  typedef DEPRECATED__go2_interfaces__srv__CheckpointCapture_Response
    std::shared_ptr<go2_interfaces::srv::CheckpointCapture_Response_<ContainerAllocator> const>
    ConstPtr;

  // comparison operators
  bool operator==(const CheckpointCapture_Response_ & other) const
  {
    if (this->success != other.success) {
      return false;
    }
    if (this->message != other.message) {
      return false;
    }
    if (this->image_jpeg != other.image_jpeg) {
      return false;
    }
    if (this->robot_state_json != other.robot_state_json) {
      return false;
    }
    if (this->pose_json != other.pose_json) {
      return false;
    }
    return true;
  }
  bool operator!=(const CheckpointCapture_Response_ & other) const
  {
    return !this->operator==(other);
  }
};  // struct CheckpointCapture_Response_

// alias to use template instance with default allocator
using CheckpointCapture_Response =
  go2_interfaces::srv::CheckpointCapture_Response_<std::allocator<void>>;

// constant definitions

}  // namespace srv

}  // namespace go2_interfaces

namespace go2_interfaces
{

namespace srv
{

struct CheckpointCapture
{
  using Request = go2_interfaces::srv::CheckpointCapture_Request;
  using Response = go2_interfaces::srv::CheckpointCapture_Response;
};

}  // namespace srv

}  // namespace go2_interfaces

#endif  // GO2_INTERFACES__SRV__DETAIL__CHECKPOINT_CAPTURE__STRUCT_HPP_
