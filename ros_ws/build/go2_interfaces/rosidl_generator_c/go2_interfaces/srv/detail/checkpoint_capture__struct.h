// generated from rosidl_generator_c/resource/idl__struct.h.em
// with input from go2_interfaces:srv/CheckpointCapture.idl
// generated code does not contain a copyright notice

#ifndef GO2_INTERFACES__SRV__DETAIL__CHECKPOINT_CAPTURE__STRUCT_H_
#define GO2_INTERFACES__SRV__DETAIL__CHECKPOINT_CAPTURE__STRUCT_H_

#ifdef __cplusplus
extern "C"
{
#endif

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>


// Constants defined in the message

// Include directives for member types
// Member 'waypoint_id'
#include "rosidl_runtime_c/string.h"

// Struct defined in srv/CheckpointCapture in the package go2_interfaces.
typedef struct go2_interfaces__srv__CheckpointCapture_Request
{
  rosidl_runtime_c__String waypoint_id;
} go2_interfaces__srv__CheckpointCapture_Request;

// Struct for a sequence of go2_interfaces__srv__CheckpointCapture_Request.
typedef struct go2_interfaces__srv__CheckpointCapture_Request__Sequence
{
  go2_interfaces__srv__CheckpointCapture_Request * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} go2_interfaces__srv__CheckpointCapture_Request__Sequence;


// Constants defined in the message

// Include directives for member types
// Member 'message'
// Member 'robot_state_json'
// Member 'pose_json'
// already included above
// #include "rosidl_runtime_c/string.h"
// Member 'image_jpeg'
#include "rosidl_runtime_c/primitives_sequence.h"

// Struct defined in srv/CheckpointCapture in the package go2_interfaces.
typedef struct go2_interfaces__srv__CheckpointCapture_Response
{
  bool success;
  rosidl_runtime_c__String message;
  rosidl_runtime_c__uint8__Sequence image_jpeg;
  rosidl_runtime_c__String robot_state_json;
  rosidl_runtime_c__String pose_json;
} go2_interfaces__srv__CheckpointCapture_Response;

// Struct for a sequence of go2_interfaces__srv__CheckpointCapture_Response.
typedef struct go2_interfaces__srv__CheckpointCapture_Response__Sequence
{
  go2_interfaces__srv__CheckpointCapture_Response * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} go2_interfaces__srv__CheckpointCapture_Response__Sequence;

#ifdef __cplusplus
}
#endif

#endif  // GO2_INTERFACES__SRV__DETAIL__CHECKPOINT_CAPTURE__STRUCT_H_
