cmake_minimum_required(VERSION 3.16)

project(prohand_client LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Cap'n Proto and ZeroMQ from the system (brew, apt) or from any toolchain
# file the caller passes; nothing here needs a particular package manager.
find_package(CapnProto CONFIG REQUIRED)
# cppzmq ships a CMake config on Debian and in vcpkg; Homebrew ships only the
# header and libzmq's pkg-config file, so fall back to those.
find_package(cppzmq CONFIG QUIET)
if(NOT TARGET cppzmq)
  find_package(PkgConfig REQUIRED)
  pkg_check_modules(LIBZMQ REQUIRED IMPORTED_TARGET libzmq)
  find_path(ZMQ_HPP_DIR zmq.hpp HINTS ${LIBZMQ_INCLUDE_DIRS})
  if(NOT ZMQ_HPP_DIR)
    message(FATAL_ERROR "zmq.hpp (cppzmq) not found; install cppzmq or set ZMQ_HPP_DIR")
  endif()
  add_library(cppzmq INTERFACE IMPORTED GLOBAL)
  target_include_directories(cppzmq INTERFACE "${ZMQ_HPP_DIR}")
  target_link_libraries(cppzmq INTERFACE PkgConfig::LIBZMQ)
endif()
find_program(CAPNP_EXECUTABLE capnp REQUIRED)
find_program(CAPNPC_CXX_EXECUTABLE capnpc-c++ REQUIRED)

# The public schema: PROHAND_SCHEMA_DIR when given; inside the monorepo its
# public edition, so an in-tree build never reads a stale vendored copy; in
# the shipped package the copy vendored beside the reference clients.
set(PROHAND_SCHEMA_DIR "" CACHE PATH "Directory holding prohand_sdk.capnp")
if(PROHAND_SCHEMA_DIR STREQUAL "")
  set(MONOREPO_SCHEMA
      "${CMAKE_CURRENT_SOURCE_DIR}/../../../../../../schemas/capnp/schema/prohand/public")
  if(EXISTS "${MONOREPO_SCHEMA}/prohand_sdk.capnp")
    set(PROHAND_SCHEMA_DIR "${MONOREPO_SCHEMA}")
  else()
    set(PROHAND_SCHEMA_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../../../schema/prohand")
  endif()
endif()
get_filename_component(PROHAND_SCHEMA_DIR "${PROHAND_SCHEMA_DIR}" ABSOLUTE)
set(ROOT_SCHEMA "${PROHAND_SCHEMA_DIR}/prohand_sdk.capnp")
if(NOT EXISTS "${ROOT_SCHEMA}")
  message(FATAL_ERROR "prohand_sdk.capnp not found under ${PROHAND_SCHEMA_DIR}; set PROHAND_SCHEMA_DIR")
endif()

# Every msg/*.capnp the root imports, transitively. capnp emits one header per
# file it is given and the generated root includes one per import, so this
# list must match the schema's imports.
set(MSG_CAPNP_NAMES
    alert
    calibration
    current_sense
    envelope
    hand
    imu
    joint
    linear
    motion
    rotary
    sync)
set(GEN_DIR "${CMAKE_CURRENT_BINARY_DIR}/gen")
file(MAKE_DIRECTORY "${GEN_DIR}/msg")
set(MSG_SCHEMAS "")
set(MSG_GEN_CPPS "")
foreach(name ${MSG_CAPNP_NAMES})
  list(APPEND MSG_SCHEMAS "${PROHAND_SCHEMA_DIR}/msg/${name}.capnp")
  list(APPEND MSG_GEN_CPPS "${GEN_DIR}/msg/${name}.capnp.c++")
endforeach()
add_custom_command(
  OUTPUT "${GEN_DIR}/prohand_sdk.capnp.h" "${GEN_DIR}/prohand_sdk.capnp.c++" ${MSG_GEN_CPPS}
  COMMAND ${CAPNP_EXECUTABLE} compile --src-prefix=${PROHAND_SCHEMA_DIR}
          -o${CAPNPC_CXX_EXECUTABLE}:${GEN_DIR} -I ${PROHAND_SCHEMA_DIR} ${ROOT_SCHEMA} ${MSG_SCHEMAS}
  DEPENDS ${ROOT_SCHEMA} ${MSG_SCHEMAS}
  COMMENT "Generating Cap'n Proto C++ from ${ROOT_SCHEMA}"
  VERBATIM)

add_library(prohand_client STATIC src/prohand_client.cpp "${GEN_DIR}/prohand_sdk.capnp.c++"
                                  ${MSG_GEN_CPPS})
target_include_directories(prohand_client PUBLIC "${CMAKE_CURRENT_SOURCE_DIR}/include" "${GEN_DIR}")
target_link_libraries(prohand_client PUBLIC CapnProto::capnp CapnProto::kj cppzmq)

add_executable(quickstart examples/quickstart.cpp)
target_link_libraries(quickstart PRIVATE prohand_client)

option(PROHAND_CLIENT_TESTS "Build the wire-contract test" ON)
if(PROHAND_CLIENT_TESTS)
  enable_testing()
  add_executable(decode_fixtures tests/decode_fixtures.cpp)
  target_link_libraries(decode_fixtures PRIVATE prohand_client)
  add_test(NAME decode_fixtures COMMAND decode_fixtures "${CMAKE_CURRENT_SOURCE_DIR}/../fixtures")
endif()
