cmake_minimum_required(VERSION 3.16)

project(d1_bridge LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(Threads REQUIRED)

option(ENABLE_D1_SDK "Enable Unitree SDK2 read-only D1 DDS subscriptions when headers are available" ON)
set(D1_SDK_MSG_ROOT "" CACHE PATH "Path containing the D1 msg/ArmString_.hpp and msg/PubServoInfo_.hpp headers")

set(D1_TRANSPORT_HAS_UNITREE_SDK 0)

if(ENABLE_D1_SDK)
    find_package(unitree_sdk2 QUIET CONFIG)
    find_path(D1_SDK_MSG_INCLUDE_DIR
        NAMES msg/ArmString_.hpp
        HINTS
            ${D1_SDK_MSG_ROOT}
            ${D1_SDK_MSG_ROOT}/include
            /opt/unitree_robotics
            /opt/unitree_robotics/include
            /usr/local
            /usr/local/include
            /usr
            /usr/include
    )
    find_path(D1_SDK_SERVO_MSG_INCLUDE_DIR
        NAMES msg/PubServoInfo_.hpp
        HINTS
            ${D1_SDK_MSG_ROOT}
            ${D1_SDK_MSG_ROOT}/include
            /opt/unitree_robotics
            /opt/unitree_robotics/include
            /usr/local
            /usr/local/include
            /usr
            /usr/include
    )

    if(unitree_sdk2_FOUND AND D1_SDK_MSG_INCLUDE_DIR AND D1_SDK_SERVO_MSG_INCLUDE_DIR)
        set(D1_TRANSPORT_HAS_UNITREE_SDK 1)
        message(STATUS "D1 bridge: enabling official Unitree SDK2 read-only backend")
    else()
        message(STATUS "D1 bridge: Unitree SDK2 or D1 msg headers not found; official backend will stay unavailable and mock mode remains supported")
    endif()
endif()

add_executable(d1_bridge
    src/d1_command_serializer.cpp
    src/d1_transport.cpp
    src/d1_safety.cpp
    src/d1_bridge_server.cpp
    src/main.cpp
)

target_include_directories(d1_bridge PRIVATE include)
target_compile_options(d1_bridge PRIVATE -Wall -Wextra -Wpedantic)
target_compile_definitions(d1_bridge PRIVATE D1_TRANSPORT_HAS_UNITREE_SDK=${D1_TRANSPORT_HAS_UNITREE_SDK})
target_link_libraries(d1_bridge PRIVATE Threads::Threads)

if(D1_TRANSPORT_HAS_UNITREE_SDK)
    target_include_directories(d1_bridge PRIVATE ${D1_SDK_MSG_INCLUDE_DIR})
    target_link_libraries(d1_bridge PRIVATE unitree_sdk2)
endif()

install(TARGETS d1_bridge RUNTIME DESTINATION bin)

include(CTest)

if(BUILD_TESTING)
    add_executable(d1_transport_tests
        src/d1_command_serializer.cpp
        src/d1_transport.cpp
        src/d1_safety.cpp
        src/d1_bridge_server.cpp
        tests/d1_transport_tests.cpp
    )
    target_include_directories(d1_transport_tests PRIVATE include src)
    target_compile_options(d1_transport_tests PRIVATE -Wall -Wextra -Wpedantic)
    target_compile_definitions(d1_transport_tests PRIVATE D1_TRANSPORT_HAS_UNITREE_SDK=0)
    target_link_libraries(d1_transport_tests PRIVATE Threads::Threads)
    add_test(NAME d1_transport_tests COMMAND d1_transport_tests)
endif()
