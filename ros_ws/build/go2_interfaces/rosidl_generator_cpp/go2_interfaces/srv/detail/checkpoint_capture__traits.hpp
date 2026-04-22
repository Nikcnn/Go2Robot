// generated from rosidl_generator_cpp/resource/idl__traits.hpp.em
// with input from go2_interfaces:srv/CheckpointCapture.idl
// generated code does not contain a copyright notice

#ifndef GO2_INTERFACES__SRV__DETAIL__CHECKPOINT_CAPTURE__TRAITS_HPP_
#define GO2_INTERFACES__SRV__DETAIL__CHECKPOINT_CAPTURE__TRAITS_HPP_

#include "go2_interfaces/srv/detail/checkpoint_capture__struct.hpp"
#include <rosidl_runtime_cpp/traits.hpp>
#include <stdint.h>
#include <type_traits>

namespace rosidl_generator_traits
{

template<>
inline const char * data_type<go2_interfaces::srv::CheckpointCapture_Request>()
{
  return "go2_interfaces::srv::CheckpointCapture_Request";
}

template<>
inline const char * name<go2_interfaces::srv::CheckpointCapture_Request>()
{
  return "go2_interfaces/srv/CheckpointCapture_Request";
}

template<>
struct has_fixed_size<go2_interfaces::srv::CheckpointCapture_Request>
  : std::integral_constant<bool, false> {};

template<>
struct has_bounded_size<go2_interfaces::srv::CheckpointCapture_Request>
  : std::integral_constant<bool, false> {};

template<>
struct is_message<go2_interfaces::srv::CheckpointCapture_Request>
  : std::true_type {};

}  // namespace rosidl_generator_traits

namespace rosidl_generator_traits
{

template<>
inline const char * data_type<go2_interfaces::srv::CheckpointCapture_Response>()
{
  return "go2_interfaces::srv::CheckpointCapture_Response";
}

template<>
inline const char * name<go2_interfaces::srv::CheckpointCapture_Response>()
{
  return "go2_interfaces/srv/CheckpointCapture_Response";
}

template<>
struct has_fixed_size<go2_interfaces::srv::CheckpointCapture_Response>
  : std::integral_constant<bool, false> {};

template<>
struct has_bounded_size<go2_interfaces::srv::CheckpointCapture_Response>
  : std::integral_constant<bool, false> {};

template<>
struct is_message<go2_interfaces::srv::CheckpointCapture_Response>
  : std::true_type {};

}  // namespace rosidl_generator_traits

namespace rosidl_generator_traits
{

template<>
inline const char * data_type<go2_interfaces::srv::CheckpointCapture>()
{
  return "go2_interfaces::srv::CheckpointCapture";
}

template<>
inline const char * name<go2_interfaces::srv::CheckpointCapture>()
{
  return "go2_interfaces/srv/CheckpointCapture";
}

template<>
struct has_fixed_size<go2_interfaces::srv::CheckpointCapture>
  : std::integral_constant<
    bool,
    has_fixed_size<go2_interfaces::srv::CheckpointCapture_Request>::value &&
    has_fixed_size<go2_interfaces::srv::CheckpointCapture_Response>::value
  >
{
};

template<>
struct has_bounded_size<go2_interfaces::srv::CheckpointCapture>
  : std::integral_constant<
    bool,
    has_bounded_size<go2_interfaces::srv::CheckpointCapture_Request>::value &&
    has_bounded_size<go2_interfaces::srv::CheckpointCapture_Response>::value
  >
{
};

template<>
struct is_service<go2_interfaces::srv::CheckpointCapture>
  : std::true_type
{
};

template<>
struct is_service_request<go2_interfaces::srv::CheckpointCapture_Request>
  : std::true_type
{
};

template<>
struct is_service_response<go2_interfaces::srv::CheckpointCapture_Response>
  : std::true_type
{
};

}  // namespace rosidl_generator_traits

#endif  // GO2_INTERFACES__SRV__DETAIL__CHECKPOINT_CAPTURE__TRAITS_HPP_
