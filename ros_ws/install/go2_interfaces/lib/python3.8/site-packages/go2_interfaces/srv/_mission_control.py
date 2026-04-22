# generated from rosidl_generator_py/resource/_idl.py.em
# with input from go2_interfaces:srv/MissionControl.idl
# generated code does not contain a copyright notice


# Import statements for member types

import rosidl_parser.definition  # noqa: E402, I100


class Metaclass_MissionControl_Request(type):
    """Metaclass of message 'MissionControl_Request'."""

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
                'go2_interfaces.srv.MissionControl_Request')
            logger.debug(
                'Failed to import needed modules for type support:\n' +
                traceback.format_exc())
        else:
            cls._CREATE_ROS_MESSAGE = module.create_ros_message_msg__srv__mission_control__request
            cls._CONVERT_FROM_PY = module.convert_from_py_msg__srv__mission_control__request
            cls._CONVERT_TO_PY = module.convert_to_py_msg__srv__mission_control__request
            cls._TYPE_SUPPORT = module.type_support_msg__srv__mission_control__request
            cls._DESTROY_ROS_MESSAGE = module.destroy_ros_message_msg__srv__mission_control__request

    @classmethod
    def __prepare__(cls, name, bases, **kwargs):
        # list constant names here so that they appear in the help text of
        # the message class under "Data and other attributes defined here:"
        # as well as populate each message instance
        return {
        }


class MissionControl_Request(metaclass=Metaclass_MissionControl_Request):
    """Message class 'MissionControl_Request'."""

    __slots__ = [
        '_command',
        '_mission_path',
        '_mission_json',
    ]

    _fields_and_field_types = {
        'command': 'string',
        'mission_path': 'string',
        'mission_json': 'string',
    }

    SLOT_TYPES = (
        rosidl_parser.definition.UnboundedString(),  # noqa: E501
        rosidl_parser.definition.UnboundedString(),  # noqa: E501
        rosidl_parser.definition.UnboundedString(),  # noqa: E501
    )

    def __init__(self, **kwargs):
        assert all('_' + key in self.__slots__ for key in kwargs.keys()), \
            'Invalid arguments passed to constructor: %s' % \
            ', '.join(sorted(k for k in kwargs.keys() if '_' + k not in self.__slots__))
        self.command = kwargs.get('command', str())
        self.mission_path = kwargs.get('mission_path', str())
        self.mission_json = kwargs.get('mission_json', str())

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
        if self.command != other.command:
            return False
        if self.mission_path != other.mission_path:
            return False
        if self.mission_json != other.mission_json:
            return False
        return True

    @classmethod
    def get_fields_and_field_types(cls):
        from copy import copy
        return copy(cls._fields_and_field_types)

    @property
    def command(self):
        """Message field 'command'."""
        return self._command

    @command.setter
    def command(self, value):
        if __debug__:
            assert \
                isinstance(value, str), \
                "The 'command' field must be of type 'str'"
        self._command = value

    @property
    def mission_path(self):
        """Message field 'mission_path'."""
        return self._mission_path

    @mission_path.setter
    def mission_path(self, value):
        if __debug__:
            assert \
                isinstance(value, str), \
                "The 'mission_path' field must be of type 'str'"
        self._mission_path = value

    @property
    def mission_json(self):
        """Message field 'mission_json'."""
        return self._mission_json

    @mission_json.setter
    def mission_json(self, value):
        if __debug__:
            assert \
                isinstance(value, str), \
                "The 'mission_json' field must be of type 'str'"
        self._mission_json = value


# Import statements for member types

# already imported above
# import rosidl_parser.definition


class Metaclass_MissionControl_Response(type):
    """Metaclass of message 'MissionControl_Response'."""

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
                'go2_interfaces.srv.MissionControl_Response')
            logger.debug(
                'Failed to import needed modules for type support:\n' +
                traceback.format_exc())
        else:
            cls._CREATE_ROS_MESSAGE = module.create_ros_message_msg__srv__mission_control__response
            cls._CONVERT_FROM_PY = module.convert_from_py_msg__srv__mission_control__response
            cls._CONVERT_TO_PY = module.convert_to_py_msg__srv__mission_control__response
            cls._TYPE_SUPPORT = module.type_support_msg__srv__mission_control__response
            cls._DESTROY_ROS_MESSAGE = module.destroy_ros_message_msg__srv__mission_control__response

    @classmethod
    def __prepare__(cls, name, bases, **kwargs):
        # list constant names here so that they appear in the help text of
        # the message class under "Data and other attributes defined here:"
        # as well as populate each message instance
        return {
        }


class MissionControl_Response(metaclass=Metaclass_MissionControl_Response):
    """Message class 'MissionControl_Response'."""

    __slots__ = [
        '_success',
        '_message',
        '_mission_id',
        '_state_json',
    ]

    _fields_and_field_types = {
        'success': 'boolean',
        'message': 'string',
        'mission_id': 'string',
        'state_json': 'string',
    }

    SLOT_TYPES = (
        rosidl_parser.definition.BasicType('boolean'),  # noqa: E501
        rosidl_parser.definition.UnboundedString(),  # noqa: E501
        rosidl_parser.definition.UnboundedString(),  # noqa: E501
        rosidl_parser.definition.UnboundedString(),  # noqa: E501
    )

    def __init__(self, **kwargs):
        assert all('_' + key in self.__slots__ for key in kwargs.keys()), \
            'Invalid arguments passed to constructor: %s' % \
            ', '.join(sorted(k for k in kwargs.keys() if '_' + k not in self.__slots__))
        self.success = kwargs.get('success', bool())
        self.message = kwargs.get('message', str())
        self.mission_id = kwargs.get('mission_id', str())
        self.state_json = kwargs.get('state_json', str())

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
        if self.mission_id != other.mission_id:
            return False
        if self.state_json != other.state_json:
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
    def mission_id(self):
        """Message field 'mission_id'."""
        return self._mission_id

    @mission_id.setter
    def mission_id(self, value):
        if __debug__:
            assert \
                isinstance(value, str), \
                "The 'mission_id' field must be of type 'str'"
        self._mission_id = value

    @property
    def state_json(self):
        """Message field 'state_json'."""
        return self._state_json

    @state_json.setter
    def state_json(self, value):
        if __debug__:
            assert \
                isinstance(value, str), \
                "The 'state_json' field must be of type 'str'"
        self._state_json = value


class Metaclass_MissionControl(type):
    """Metaclass of service 'MissionControl'."""

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
                'go2_interfaces.srv.MissionControl')
            logger.debug(
                'Failed to import needed modules for type support:\n' +
                traceback.format_exc())
        else:
            cls._TYPE_SUPPORT = module.type_support_srv__srv__mission_control

            from go2_interfaces.srv import _mission_control
            if _mission_control.Metaclass_MissionControl_Request._TYPE_SUPPORT is None:
                _mission_control.Metaclass_MissionControl_Request.__import_type_support__()
            if _mission_control.Metaclass_MissionControl_Response._TYPE_SUPPORT is None:
                _mission_control.Metaclass_MissionControl_Response.__import_type_support__()


class MissionControl(metaclass=Metaclass_MissionControl):
    from go2_interfaces.srv._mission_control import MissionControl_Request as Request
    from go2_interfaces.srv._mission_control import MissionControl_Response as Response

    def __init__(self):
        raise NotImplementedError('Service classes can not be instantiated')
