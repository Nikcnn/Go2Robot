// generated from rosidl_generator_cpp/resource/idl__traits.hpp.em
// with input from go2_interfaces:srv/MissionControl.idl
// generated code does not contain a copyright notice

#ifndef GO2_INTERFACES__SRV__DETAIL__MISSION_CONTROL__TRAITS_HPP_
#define GO2_INTERFACES__SRV__DETAIL__MISSION_CONTROL__TRAITS_HPP_

#include "go2_interfaces/srv/detail/mission_control__struct.hpp"
#include <rosidl_runtime_cpp/traits.hpp>
#include <stdint.h>
#include <type_traits>

namespace rosidl_generator_traits
{

template<>
inline const char * data_type<go2_interfaces::srv::MissionControl_Request>()
{
  return "go2_interfaces::srv::MissionControl_Request";
}

template<>
inline const char * name<go2_interfaces::srv::MissionControl_Request>()
{
  return "go2_interfaces/srv/MissionControl_Request";
}

template<>
struct has_fixed_size<go2_interfaces::srv::MissionControl_Request>
  : std::integral_constant<bool, false> {};

template<>
struct has_bounded_size<go2_interfaces::srv::MissionControl_Request>
  : std::integral_constant<bool, false> {};

template<>
struct is_message<go2_interfaces::srv::MissionControl_Request>
  : std::true_type {};

}  // namespace rosidl_generator_traits

namespace rosidl_generator_traits
{

template<>
inline const char * data_type<go2_interfaces::srv::MissionControl_Response>()
{
  return "go2_interfaces::srv::MissionControl_Response";
}

template<>
inline const char * name<go2_interfaces::srv::MissionControl_Response>()
{
  return "go2_interfaces/srv/MissionControl_Response";
}

template<>
struct has_fixed_size<go2_interfaces::srv::MissionControl_Response>
  : std::integral_constant<bool, false> {};

template<>
struct has_bounded_size<go2_interfaces::srv::MissionControl_Response>
  : std::integral_constant<bool, false> {};

template<>
struct is_message<go2_interfaces::srv::MissionControl_Response>
  : std::true_type {};

}  // namespace rosidl_generator_traits

namespace rosidl_generator_traits
{

template<>
inline const char * data_type<go2_interfaces::srv::MissionControl>()
{
  return "go2_interfaces::srv::MissionControl";
}

template<>
inline const char * name<go2_interfaces::srv::MissionControl>()
{
  return "go2_interfaces/srv/MissionControl";
}

template<>
struct has_fixed_size<go2_interfaces::srv::MissionControl>
  : std::integral_constant<
    bool,
    has_fixed_size<go2_interfaces::srv::MissionControl_Request>::value &&
    has_fixed_size<go2_interfaces::srv::MissionControl_Response>::value
  >
{
};

template<>
struct has_bounded_size<go2_interfaces::srv::MissionControl>
  : std::integral_constant<
    bool,
    has_bounded_size<go2_interfaces::srv::MissionControl_Request>::value &&
    has_bounded_size<go2_interfaces::srv::MissionControl_Response>::value
  >
{
};

template<>
struct is_service<go2_interfaces::srv::MissionControl>
  : std::true_type
{
};

template<>
struct is_service_request<go2_interfaces::srv::MissionControl_Request>
  : std::true_type
{
};

template<>
struct is_service_response<go2_interfaces::srv::MissionControl_Response>
  : std::true_type
{
};

}  // namespace rosidl_generator_traits

#endif  // GO2_INTERFACES__SRV__DETAIL__MISSION_CONTROL__TRAITS_HPP_
