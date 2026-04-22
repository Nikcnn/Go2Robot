// generated from rosidl_generator_c/resource/idl__struct.h.em
// with input from go2_interfaces:srv/MissionControl.idl
// generated code does not contain a copyright notice

#ifndef GO2_INTERFACES__SRV__DETAIL__MISSION_CONTROL__STRUCT_H_
#define GO2_INTERFACES__SRV__DETAIL__MISSION_CONTROL__STRUCT_H_

#ifdef __cplusplus
extern "C"
{
#endif

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>


// Constants defined in the message

// Include directives for member types
// Member 'command'
// Member 'mission_path'
// Member 'mission_json'
#include "rosidl_runtime_c/string.h"

// Struct defined in srv/MissionControl in the package go2_interfaces.
typedef struct go2_interfaces__srv__MissionControl_Request
{
  rosidl_runtime_c__String command;
  rosidl_runtime_c__String mission_path;
  rosidl_runtime_c__String mission_json;
} go2_interfaces__srv__MissionControl_Request;

// Struct for a sequence of go2_interfaces__srv__MissionControl_Request.
typedef struct go2_interfaces__srv__MissionControl_Request__Sequence
{
  go2_interfaces__srv__MissionControl_Request * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} go2_interfaces__srv__MissionControl_Request__Sequence;


// Constants defined in the message

// Include directives for member types
// Member 'message'
// Member 'mission_id'
// Member 'state_json'
// already included above
// #include "rosidl_runtime_c/string.h"

// Struct defined in srv/MissionControl in the package go2_interfaces.
typedef struct go2_interfaces__srv__MissionControl_Response
{
  bool success;
  rosidl_runtime_c__String message;
  rosidl_runtime_c__String mission_id;
  rosidl_runtime_c__String state_json;
} go2_interfaces__srv__MissionControl_Response;

// Struct for a sequence of go2_interfaces__srv__MissionControl_Response.
typedef struct go2_interfaces__srv__MissionControl_Response__Sequence
{
  go2_interfaces__srv__MissionControl_Response * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} go2_interfaces__srv__MissionControl_Response__Sequence;

#ifdef __cplusplus
}
#endif

#endif  // GO2_INTERFACES__SRV__DETAIL__MISSION_CONTROL__STRUCT_H_
