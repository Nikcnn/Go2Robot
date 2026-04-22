// generated from rosidl_typesupport_fastrtps_c/resource/idl__type_support_c.cpp.em
// with input from go2_interfaces:srv/CheckpointCapture.idl
// generated code does not contain a copyright notice
#include "go2_interfaces/srv/detail/checkpoint_capture__rosidl_typesupport_fastrtps_c.h"


#include <cassert>
#include <limits>
#include <string>
#include "rosidl_typesupport_fastrtps_c/identifier.h"
#include "rosidl_typesupport_fastrtps_c/wstring_conversion.hpp"
#include "rosidl_typesupport_fastrtps_cpp/message_type_support.h"
#include "go2_interfaces/msg/rosidl_typesupport_fastrtps_c__visibility_control.h"
#include "go2_interfaces/srv/detail/checkpoint_capture__struct.h"
#include "go2_interfaces/srv/detail/checkpoint_capture__functions.h"
#include "fastcdr/Cdr.h"

#ifndef _WIN32
# pragma GCC diagnostic push
# pragma GCC diagnostic ignored "-Wunused-parameter"
# ifdef __clang__
#  pragma clang diagnostic ignored "-Wdeprecated-register"
#  pragma clang diagnostic ignored "-Wreturn-type-c-linkage"
# endif
#endif
#ifndef _WIN32
# pragma GCC diagnostic pop
#endif

// includes and forward declarations of message dependencies and their conversion functions

#if defined(__cplusplus)
extern "C"
{
#endif

#include "rosidl_runtime_c/string.h"  // waypoint_id
#include "rosidl_runtime_c/string_functions.h"  // waypoint_id

// forward declare type support functions


using _CheckpointCapture_Request__ros_msg_type = go2_interfaces__srv__CheckpointCapture_Request;

static bool _CheckpointCapture_Request__cdr_serialize(
  const void * untyped_ros_message,
  eprosima::fastcdr::Cdr & cdr)
{
  if (!untyped_ros_message) {
    fprintf(stderr, "ros message handle is null\n");
    return false;
  }
  const _CheckpointCapture_Request__ros_msg_type * ros_message = static_cast<const _CheckpointCapture_Request__ros_msg_type *>(untyped_ros_message);
  // Field name: waypoint_id
  {
    const rosidl_runtime_c__String * str = &ros_message->waypoint_id;
    if (str->capacity == 0 || str->capacity <= str->size) {
      fprintf(stderr, "string capacity not greater than size\n");
      return false;
    }
    if (str->data[str->size] != '\0') {
      fprintf(stderr, "string not null-terminated\n");
      return false;
    }
    cdr << str->data;
  }

  return true;
}

static bool _CheckpointCapture_Request__cdr_deserialize(
  eprosima::fastcdr::Cdr & cdr,
  void * untyped_ros_message)
{
  if (!untyped_ros_message) {
    fprintf(stderr, "ros message handle is null\n");
    return false;
  }
  _CheckpointCapture_Request__ros_msg_type * ros_message = static_cast<_CheckpointCapture_Request__ros_msg_type *>(untyped_ros_message);
  // Field name: waypoint_id
  {
    std::string tmp;
    cdr >> tmp;
    if (!ros_message->waypoint_id.data) {
      rosidl_runtime_c__String__init(&ros_message->waypoint_id);
    }
    bool succeeded = rosidl_runtime_c__String__assign(
      &ros_message->waypoint_id,
      tmp.c_str());
    if (!succeeded) {
      fprintf(stderr, "failed to assign string into field 'waypoint_id'\n");
      return false;
    }
  }

  return true;
}

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_go2_interfaces
size_t get_serialized_size_go2_interfaces__srv__CheckpointCapture_Request(
  const void * untyped_ros_message,
  size_t current_alignment)
{
  const _CheckpointCapture_Request__ros_msg_type * ros_message = static_cast<const _CheckpointCapture_Request__ros_msg_type *>(untyped_ros_message);
  (void)ros_message;
  size_t initial_alignment = current_alignment;

  const size_t padding = 4;
  const size_t wchar_size = 4;
  (void)padding;
  (void)wchar_size;

  // field.name waypoint_id
  current_alignment += padding +
    eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
    (ros_message->waypoint_id.size + 1);

  return current_alignment - initial_alignment;
}

static uint32_t _CheckpointCapture_Request__get_serialized_size(const void * untyped_ros_message)
{
  return static_cast<uint32_t>(
    get_serialized_size_go2_interfaces__srv__CheckpointCapture_Request(
      untyped_ros_message, 0));
}

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_go2_interfaces
size_t max_serialized_size_go2_interfaces__srv__CheckpointCapture_Request(
  bool & full_bounded,
  size_t current_alignment)
{
  size_t initial_alignment = current_alignment;

  const size_t padding = 4;
  const size_t wchar_size = 4;
  (void)padding;
  (void)wchar_size;
  (void)full_bounded;

  // member: waypoint_id
  {
    size_t array_size = 1;

    full_bounded = false;
    for (size_t index = 0; index < array_size; ++index) {
      current_alignment += padding +
        eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
        1;
    }
  }

  return current_alignment - initial_alignment;
}

static size_t _CheckpointCapture_Request__max_serialized_size(bool & full_bounded)
{
  return max_serialized_size_go2_interfaces__srv__CheckpointCapture_Request(
    full_bounded, 0);
}


static message_type_support_callbacks_t __callbacks_CheckpointCapture_Request = {
  "go2_interfaces::srv",
  "CheckpointCapture_Request",
  _CheckpointCapture_Request__cdr_serialize,
  _CheckpointCapture_Request__cdr_deserialize,
  _CheckpointCapture_Request__get_serialized_size,
  _CheckpointCapture_Request__max_serialized_size
};

static rosidl_message_type_support_t _CheckpointCapture_Request__type_support = {
  rosidl_typesupport_fastrtps_c__identifier,
  &__callbacks_CheckpointCapture_Request,
  get_message_typesupport_handle_function,
};

const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, go2_interfaces, srv, CheckpointCapture_Request)() {
  return &_CheckpointCapture_Request__type_support;
}

#if defined(__cplusplus)
}
#endif

// already included above
// #include <cassert>
// already included above
// #include <limits>
// already included above
// #include <string>
// already included above
// #include "rosidl_typesupport_fastrtps_c/identifier.h"
// already included above
// #include "rosidl_typesupport_fastrtps_c/wstring_conversion.hpp"
// already included above
// #include "rosidl_typesupport_fastrtps_cpp/message_type_support.h"
// already included above
// #include "go2_interfaces/msg/rosidl_typesupport_fastrtps_c__visibility_control.h"
// already included above
// #include "go2_interfaces/srv/detail/checkpoint_capture__struct.h"
// already included above
// #include "go2_interfaces/srv/detail/checkpoint_capture__functions.h"
// already included above
// #include "fastcdr/Cdr.h"

#ifndef _WIN32
# pragma GCC diagnostic push
# pragma GCC diagnostic ignored "-Wunused-parameter"
# ifdef __clang__
#  pragma clang diagnostic ignored "-Wdeprecated-register"
#  pragma clang diagnostic ignored "-Wreturn-type-c-linkage"
# endif
#endif
#ifndef _WIN32
# pragma GCC diagnostic pop
#endif

// includes and forward declarations of message dependencies and their conversion functions

#if defined(__cplusplus)
extern "C"
{
#endif

#include "rosidl_runtime_c/primitives_sequence.h"  // image_jpeg
#include "rosidl_runtime_c/primitives_sequence_functions.h"  // image_jpeg
// already included above
// #include "rosidl_runtime_c/string.h"  // message, pose_json, robot_state_json
// already included above
// #include "rosidl_runtime_c/string_functions.h"  // message, pose_json, robot_state_json

// forward declare type support functions


using _CheckpointCapture_Response__ros_msg_type = go2_interfaces__srv__CheckpointCapture_Response;

static bool _CheckpointCapture_Response__cdr_serialize(
  const void * untyped_ros_message,
  eprosima::fastcdr::Cdr & cdr)
{
  if (!untyped_ros_message) {
    fprintf(stderr, "ros message handle is null\n");
    return false;
  }
  const _CheckpointCapture_Response__ros_msg_type * ros_message = static_cast<const _CheckpointCapture_Response__ros_msg_type *>(untyped_ros_message);
  // Field name: success
  {
    cdr << (ros_message->success ? true : false);
  }

  // Field name: message
  {
    const rosidl_runtime_c__String * str = &ros_message->message;
    if (str->capacity == 0 || str->capacity <= str->size) {
      fprintf(stderr, "string capacity not greater than size\n");
      return false;
    }
    if (str->data[str->size] != '\0') {
      fprintf(stderr, "string not null-terminated\n");
      return false;
    }
    cdr << str->data;
  }

  // Field name: image_jpeg
  {
    size_t size = ros_message->image_jpeg.size;
    auto array_ptr = ros_message->image_jpeg.data;
    cdr << static_cast<uint32_t>(size);
    cdr.serializeArray(array_ptr, size);
  }

  // Field name: robot_state_json
  {
    const rosidl_runtime_c__String * str = &ros_message->robot_state_json;
    if (str->capacity == 0 || str->capacity <= str->size) {
      fprintf(stderr, "string capacity not greater than size\n");
      return false;
    }
    if (str->data[str->size] != '\0') {
      fprintf(stderr, "string not null-terminated\n");
      return false;
    }
    cdr << str->data;
  }

  // Field name: pose_json
  {
    const rosidl_runtime_c__String * str = &ros_message->pose_json;
    if (str->capacity == 0 || str->capacity <= str->size) {
      fprintf(stderr, "string capacity not greater than size\n");
      return false;
    }
    if (str->data[str->size] != '\0') {
      fprintf(stderr, "string not null-terminated\n");
      return false;
    }
    cdr << str->data;
  }

  return true;
}

static bool _CheckpointCapture_Response__cdr_deserialize(
  eprosima::fastcdr::Cdr & cdr,
  void * untyped_ros_message)
{
  if (!untyped_ros_message) {
    fprintf(stderr, "ros message handle is null\n");
    return false;
  }
  _CheckpointCapture_Response__ros_msg_type * ros_message = static_cast<_CheckpointCapture_Response__ros_msg_type *>(untyped_ros_message);
  // Field name: success
  {
    uint8_t tmp;
    cdr >> tmp;
    ros_message->success = tmp ? true : false;
  }

  // Field name: message
  {
    std::string tmp;
    cdr >> tmp;
    if (!ros_message->message.data) {
      rosidl_runtime_c__String__init(&ros_message->message);
    }
    bool succeeded = rosidl_runtime_c__String__assign(
      &ros_message->message,
      tmp.c_str());
    if (!succeeded) {
      fprintf(stderr, "failed to assign string into field 'message'\n");
      return false;
    }
  }

  // Field name: image_jpeg
  {
    uint32_t cdrSize;
    cdr >> cdrSize;
    size_t size = static_cast<size_t>(cdrSize);
    if (ros_message->image_jpeg.data) {
      rosidl_runtime_c__uint8__Sequence__fini(&ros_message->image_jpeg);
    }
    if (!rosidl_runtime_c__uint8__Sequence__init(&ros_message->image_jpeg, size)) {
      return "failed to create array for field 'image_jpeg'";
    }
    auto array_ptr = ros_message->image_jpeg.data;
    cdr.deserializeArray(array_ptr, size);
  }

  // Field name: robot_state_json
  {
    std::string tmp;
    cdr >> tmp;
    if (!ros_message->robot_state_json.data) {
      rosidl_runtime_c__String__init(&ros_message->robot_state_json);
    }
    bool succeeded = rosidl_runtime_c__String__assign(
      &ros_message->robot_state_json,
      tmp.c_str());
    if (!succeeded) {
      fprintf(stderr, "failed to assign string into field 'robot_state_json'\n");
      return false;
    }
  }

  // Field name: pose_json
  {
    std::string tmp;
    cdr >> tmp;
    if (!ros_message->pose_json.data) {
      rosidl_runtime_c__String__init(&ros_message->pose_json);
    }
    bool succeeded = rosidl_runtime_c__String__assign(
      &ros_message->pose_json,
      tmp.c_str());
    if (!succeeded) {
      fprintf(stderr, "failed to assign string into field 'pose_json'\n");
      return false;
    }
  }

  return true;
}

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_go2_interfaces
size_t get_serialized_size_go2_interfaces__srv__CheckpointCapture_Response(
  const void * untyped_ros_message,
  size_t current_alignment)
{
  const _CheckpointCapture_Response__ros_msg_type * ros_message = static_cast<const _CheckpointCapture_Response__ros_msg_type *>(untyped_ros_message);
  (void)ros_message;
  size_t initial_alignment = current_alignment;

  const size_t padding = 4;
  const size_t wchar_size = 4;
  (void)padding;
  (void)wchar_size;

  // field.name success
  {
    size_t item_size = sizeof(ros_message->success);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }
  // field.name message
  current_alignment += padding +
    eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
    (ros_message->message.size + 1);
  // field.name image_jpeg
  {
    size_t array_size = ros_message->image_jpeg.size;
    auto array_ptr = ros_message->image_jpeg.data;
    current_alignment += padding +
      eprosima::fastcdr::Cdr::alignment(current_alignment, padding);
    (void)array_ptr;
    size_t item_size = sizeof(array_ptr[0]);
    current_alignment += array_size * item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }
  // field.name robot_state_json
  current_alignment += padding +
    eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
    (ros_message->robot_state_json.size + 1);
  // field.name pose_json
  current_alignment += padding +
    eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
    (ros_message->pose_json.size + 1);

  return current_alignment - initial_alignment;
}

static uint32_t _CheckpointCapture_Response__get_serialized_size(const void * untyped_ros_message)
{
  return static_cast<uint32_t>(
    get_serialized_size_go2_interfaces__srv__CheckpointCapture_Response(
      untyped_ros_message, 0));
}

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_go2_interfaces
size_t max_serialized_size_go2_interfaces__srv__CheckpointCapture_Response(
  bool & full_bounded,
  size_t current_alignment)
{
  size_t initial_alignment = current_alignment;

  const size_t padding = 4;
  const size_t wchar_size = 4;
  (void)padding;
  (void)wchar_size;
  (void)full_bounded;

  // member: success
  {
    size_t array_size = 1;

    current_alignment += array_size * sizeof(uint8_t);
  }
  // member: message
  {
    size_t array_size = 1;

    full_bounded = false;
    for (size_t index = 0; index < array_size; ++index) {
      current_alignment += padding +
        eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
        1;
    }
  }
  // member: image_jpeg
  {
    size_t array_size = 0;
    full_bounded = false;
    current_alignment += padding +
      eprosima::fastcdr::Cdr::alignment(current_alignment, padding);

    current_alignment += array_size * sizeof(uint8_t);
  }
  // member: robot_state_json
  {
    size_t array_size = 1;

    full_bounded = false;
    for (size_t index = 0; index < array_size; ++index) {
      current_alignment += padding +
        eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
        1;
    }
  }
  // member: pose_json
  {
    size_t array_size = 1;

    full_bounded = false;
    for (size_t index = 0; index < array_size; ++index) {
      current_alignment += padding +
        eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
        1;
    }
  }

  return current_alignment - initial_alignment;
}

static size_t _CheckpointCapture_Response__max_serialized_size(bool & full_bounded)
{
  return max_serialized_size_go2_interfaces__srv__CheckpointCapture_Response(
    full_bounded, 0);
}


static message_type_support_callbacks_t __callbacks_CheckpointCapture_Response = {
  "go2_interfaces::srv",
  "CheckpointCapture_Response",
  _CheckpointCapture_Response__cdr_serialize,
  _CheckpointCapture_Response__cdr_deserialize,
  _CheckpointCapture_Response__get_serialized_size,
  _CheckpointCapture_Response__max_serialized_size
};

static rosidl_message_type_support_t _CheckpointCapture_Response__type_support = {
  rosidl_typesupport_fastrtps_c__identifier,
  &__callbacks_CheckpointCapture_Response,
  get_message_typesupport_handle_function,
};

const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, go2_interfaces, srv, CheckpointCapture_Response)() {
  return &_CheckpointCapture_Response__type_support;
}

#if defined(__cplusplus)
}
#endif

#include "rosidl_typesupport_fastrtps_cpp/service_type_support.h"
#include "rosidl_typesupport_cpp/service_type_support.hpp"
// already included above
// #include "rosidl_typesupport_fastrtps_c/identifier.h"
// already included above
// #include "go2_interfaces/msg/rosidl_typesupport_fastrtps_c__visibility_control.h"
#include "go2_interfaces/srv/checkpoint_capture.h"

#if defined(__cplusplus)
extern "C"
{
#endif

static service_type_support_callbacks_t CheckpointCapture__callbacks = {
  "go2_interfaces::srv",
  "CheckpointCapture",
  ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, go2_interfaces, srv, CheckpointCapture_Request)(),
  ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, go2_interfaces, srv, CheckpointCapture_Response)(),
};

static rosidl_service_type_support_t CheckpointCapture__handle = {
  rosidl_typesupport_fastrtps_c__identifier,
  &CheckpointCapture__callbacks,
  get_service_typesupport_handle_function,
};

const rosidl_service_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__SERVICE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, go2_interfaces, srv, CheckpointCapture)() {
  return &CheckpointCapture__handle;
}

#if defined(__cplusplus)
}
#endif
