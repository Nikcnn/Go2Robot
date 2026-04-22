# generated from rosidl_generator_py/resource/_idl.py.em
# with input from go2_interfaces:srv/CheckpointCapture.idl
# generated code does not contain a copyright notice


# Import statements for member types

import rosidl_parser.definition  # noqa: E402, I100


class Metaclass_CheckpointCapture_Request(type):
    """Metaclass of message 'CheckpointCapture_Request'."""

    _CREATE_ROS_MESSAGE = None
    _CONVERT_FROM_PY = None
    _CONVERT_TO_PY = None
    _DESTROY_ROS_MESSAGE = None
    _TYPE_SUPPORT = None

    __constants = {
    }

    @classmethod
    def __import_type_support__(cls):
        try:
            from rosidl_generator_py import import_type_support
            module = import_type_support('go2_interfaces')
        except ImportError:
            import logging
            import traceback
            logger = logging.getLogger(
                'go2_interfaces.srv.CheckpointCapture_Request')
            logger.debug(
                'Failed to import needed modules for type support:\n' +
                traceback.format_exc())
        else:
            cls._CREATE_ROS_MESSAGE = module.create_ros_message_msg__srv__checkpoint_capture__request
            cls._CONVERT_FROM_PY = module.convert_from_py_msg__srv__checkpoint_capture__request
            cls._CONVERT_TO_PY = module.convert_to_py_msg__srv__checkpoint_capture__request
            cls._TYPE_SUPPORT = module.type_support_msg__srv__checkpoint_capture__request
            cls._DESTROY_ROS_MESSAGE = module.destroy_ros_message_msg__srv__checkpoint_capture__request

    @classmethod
    def __prepare__(cls, name, bases, **kwargs):
        # list constant names here so that they appear in the help text of
        # the message class under "Data and other attributes defined here:"
        # as well as populate each message instance
        return {
        }


class CheckpointCapture_Request(metaclass=Metaclass_CheckpointCapture_Request):
    """Message class 'CheckpointCapture_Request'."""

    __slots__ = [
        '_waypoint_id',
    ]

    _fields_and_field_types = {
        'waypoint_id': 'string',
    }

    SLOT_TYPES = (
        rosidl_parser.definition.UnboundedString(),  # noqa: E501
    )

    def __init__(self, **kwargs):
        assert all('_' + key in self.__slots__ for key in kwargs.keys()), \
            'Invalid arguments passed to constructor: %s' % \
            ', '.join(sorted(k for k in kwargs.keys() if '_' + k not in self.__slots__))
        self.waypoint_id = kwargs.get('waypoint_id', str())

    def __repr__(self):
        typename = self.__class__.__module__.split('.')
        typename.pop()
        typename.append(self.__class__.__name__)
        args = []
        for s, t in zip(self.__slots__, self.SLOT_TYPES):
            field = getattr(self, s)
            fieldstr = repr(field)
            # We use Python array type for fields that can be directly stored
            # in them, and "normal" sequences for everything else.  If it is
            # a type that we store in an array, strip off the 'array' portion.
            if (
                isinstance(t, rosidl_parser.definition.AbstractSequence) and
                isinstance(t.value_type, rosidl_parser.definition.BasicType) and
                t.value_type.typename in ['float', 'double', 'int8', 'uint8', 'int16', 'uint16', 'int32', 'uint32', 'int64', 'uint64']
            ):
                if len(field) == 0:
                    fieldstr = '[]'
                else:
                    assert fieldstr.startswith('array(')
                    prefix = "array('X', "
                    suffix = ')'
                    fieldstr = fieldstr[len(prefix):-len(suffix)]
            args.append(s[1:] + '=' + fieldstr)
        return '%s(%s)' % ('.'.join(typename), ', '.join(args))

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        if self.waypoint_id != other.waypoint_id:
            return False
        return True

    @classmethod
    def get_fields_and_field_types(cls):
        from copy import copy
        return copy(cls._fields_and_field_types)

    @property
    def waypoint_id(self):
        """Message field 'waypoint_id'."""
        return self._waypoint_id

    @waypoint_id.setter
    def waypoint_id(self, value):
        if __debug__:
            assert \
                isinstance(value, str), \
                "The 'waypoint_id' field must be of type 'str'"
        self._waypoint_id = value


# Import statements for member types

# Member 'image_jpeg'
import array  # noqa: E402, I100

# already imported above
# import rosidl_parser.definition


class Metaclass_CheckpointCapture_Response(type):
    """Metaclass of message 'CheckpointCapture_Response'."""

    _CREATE_ROS_MESSAGE = None
    _CONVERT_FROM_PY = None
    _CONVERT_TO_PY = None
    _DESTROY_ROS_MESSAGE = None
    _TYPE_SUPPORT = None

    __constants = {
    }

    @classmethod
    def __import_type_support__(cls):
        try:
            from rosidl_generator_py import import_type_support
            module = import_type_support('go2_interfaces')
        except ImportError:
            import logging
            import traceback
            logger = logging.getLogger(
                'go2_interfaces.srv.CheckpointCapture_Response')
            logger.debug(
                'Failed to import needed modules for type support:\n' +
                traceback.format_exc())
        else:
            cls._CREATE_ROS_MESSAGE = module.create_ros_message_msg__srv__checkpoint_capture__response
            cls._CONVERT_FROM_PY = module.convert_from_py_msg__srv__checkpoint_capture__response
            cls._CONVERT_TO_PY = module.convert_to_py_msg__srv__checkpoint_capture__response
            cls._TYPE_SUPPORT = module.type_support_msg__srv__checkpoint_capture__response
            cls._DESTROY_ROS_MESSAGE = module.destroy_ros_message_msg__srv__checkpoint_capture__response

    @classmethod
    def __prepare__(cls, name, bases, **kwargs):
        # list constant names here so that they appear in the help text of
        # the message class under "Data and other attributes defined here:"
        # as well as populate each message instance
        return {
        }


class CheckpointCapture_Response(metaclass=Metaclass_CheckpointCapture_Response):
    """Message class 'CheckpointCapture_Response'."""

    __slots__ = [
        '_success',
        '_message',
        '_image_jpeg',
        '_robot_state_json',
        '_pose_json',
    ]

    _fields_and_field_types = {
        'success': 'boolean',
        'message': 'string',
        'image_jpeg': 'sequence<uint8>',
        'robot_state_json': 'string',
        'pose_json': 'string',
    }

    SLOT_TYPES = (
        rosidl_parser.definition.BasicType('boolean'),  # noqa: E501
        rosidl_parser.definition.UnboundedString(),  # noqa: E501
        rosidl_parser.definition.UnboundedSequence(rosidl_parser.definition.BasicType('uint8')),  # noqa: E501
        rosidl_parser.definition.UnboundedString(),  # noqa: E501
        rosidl_parser.definition.UnboundedString(),  # noqa: E501
    )

    def __init__(self, **kwargs):
        assert all('_' + key in self.__slots__ for key in kwargs.keys()), \
            'Invalid arguments passed to constructor: %s' % \
            ', '.join(sorted(k for k in kwargs.keys() if '_' + k not in self.__slots__))
        self.success = kwargs.get('success', bool())
        self.message = kwargs.get('message', str())
        self.image_jpeg = array.array('B', kwargs.get('image_jpeg', []))
        self.robot_state_json = kwargs.get('robot_state_json', str())
        self.pose_json = kwargs.get('pose_json', str())

    def __repr__(self):
        typename = self.__class__.__module__.split('.')
        typename.pop()
        typename.append(self.__class__.__name__)
        args = []
        for s, t in zip(self.__slots__, self.SLOT_TYPES):
            field = getattr(self, s)
            fieldstr = repr(field)
            # We use Python array type for fields that can be directly stored
            # in them, and "normal" sequences for everything else.  If it is
            # a type that we store in an array, strip off the 'array' portion.
            if (
                isinstance(t, rosidl_parser.definition.AbstractSequence) and
                isinstance(t.value_type, rosidl_parser.definition.BasicType) and
                t.value_type.typename in ['float', 'double', 'int8', 'uint8', 'int16', 'uint16', 'int32', 'uint32', 'int64', 'uint64']
            ):
                if len(field) == 0:
                    fieldstr = '[]'
                else:
                    assert fieldstr.startswith('array(')
                    prefix = "array('X', "
                    suffix = ')'
                    fieldstr = fieldstr[len(prefix):-len(suffix)]
            args.append(s[1:] + '=' + fieldstr)
        return '%s(%s)' % ('.'.join(typename), ', '.join(args))

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        if self.success != other.success:
            return False
        if self.message != other.message:
            return False
        if self.image_jpeg != other.image_jpeg:
            return False
        if self.robot_state_json != other.robot_state_json:
            return False
        if self.pose_json != other.pose_json:
            return False
        return True

    @classmethod
    def get_fields_and_field_types(cls):
        from copy import copy
        return copy(cls._fields_and_field_types)

    @property
    def success(self):
        """Message field 'success'."""
        return self._success

    @success.setter
    def success(self, value):
        if __debug__:
            assert \
                isinstance(value, bool), \
                "The 'success' field must be of type 'bool'"
        self._success = value

    @property
    def message(self):
        """Message field 'message'."""
        return self._message

    @message.setter
    def message(self, value):
        if __debug__:
            assert \
                isinstance(value, str), \
                "The 'message' field must be of type 'str'"
        self._message = value

    @property
    def image_jpeg(self):
        """Message field 'image_jpeg'."""
        return self._image_jpeg

    @image_jpeg.setter
    def image_jpeg(self, value):
        if isinstance(value, array.array):
            assert value.typecode == 'B', \
                "The 'image_jpeg' array.array() must have the type code of 'B'"
            self._image_jpeg = value
            return
        if __debug__:
            from collections.abc import Sequence
            from collections.abc import Set
            from collections import UserList
            from collections import UserString
            assert \
                ((isinstance(value, Sequence) or
                  isinstance(value, Set) or
                  isinstance(value, UserList)) and
                 not isinstance(value, str) and
                 not isinstance(value, UserString) and
                 all(isinstance(v, int) for v in value) and
                 all(val >= 0 and val < 256 for val in value)), \
                "The 'image_jpeg' field must be a set or sequence and each value of type 'int' and each unsigned integer in [0, 255]"
        self._image_jpeg = array.array('B', value)

    @property
    def robot_state_json(self):
        """Message field 'robot_state_json'."""
        return self._robot_state_json

    @robot_state_json.setter
    def robot_state_json(self, value):
        if __debug__:
            assert \
                isinstance(value, str), \
                "The 'robot_state_json' field must be of type 'str'"
        self._robot_state_json = value

    @property
    def pose_json(self):
        """Message field 'pose_json'."""
        return self._pose_json

    @pose_json.setter
    def pose_json(self, value):
        if __debug__:
            assert \
                isinstance(value, str), \
                "The 'pose_json' field must be of type 'str'"
        self._pose_json = value


class Metaclass_CheckpointCapture(type):
    """Metaclass of service 'CheckpointCapture'."""

    _TYPE_SUPPORT = None

    @classmethod
    def __import_type_support__(cls):
        try:
            from rosidl_generator_py import import_type_support
            module = import_type_support('go2_interfaces')
        except ImportError:
            import logging
            import traceback
            logger = logging.getLogger(
                'go2_interfaces.srv.CheckpointCapture')
            logger.debug(
                'Failed to import needed modules for type support:\n' +
                traceback.format_exc())
        else:
            cls._TYPE_SUPPORT = module.type_support_srv__srv__checkpoint_capture

            from go2_interfaces.srv import _checkpoint_capture
            if _checkpoint_capture.Metaclass_CheckpointCapture_Request._TYPE_SUPPORT is None:
                _checkpoint_capture.Metaclass_CheckpointCapture_Request.__import_type_support__()
            if _checkpoint_capture.Metaclass_CheckpointCapture_Response._TYPE_SUPPORT is None:
                _checkpoint_capture.Metaclass_CheckpointCapture_Response.__import_type_support__()


class CheckpointCapture(metaclass=Metaclass_CheckpointCapture):
    from go2_interfaces.srv._checkpoint_capture import CheckpointCapture_Request as Request
    from go2_interfaces.srv._checkpoint_capture import CheckpointCapture_Response as Response

    def __init__(self):
        raise NotImplementedError('Service classes can not be instantiated')
