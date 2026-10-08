cmake_minimum_required(VERSION 3.16)

project(prohand_demo LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Demo include directory
set(PROHAND_DEMO_INCLUDE_DIR ${CMAKE_CURRENT_SOURCE_DIR}/include)

# ============================================================================
# ProHand SDK - Add as subdirectory
# ============================================================================
add_subdirectory(${CMAKE_CURRENT_SOURCE_DIR}/../../prohand_sdk/cpp
                 ${CMAKE_CURRENT_BINARY_DIR}/prohand_sdk)

# ============================================================================
# ProGlove SDK - Add as subdirectory
# ============================================================================
add_subdirectory(${CMAKE_CURRENT_SOURCE_DIR}/../../proglove_sdk/cpp
                 ${CMAKE_CURRENT_BINARY_DIR}/proglove_sdk)

# ============================================================================
# ProWristCam SDK - Add as subdirectory
# ============================================================================
add_subdirectory(${CMAKE_CURRENT_SOURCE_DIR}/../../prowrist_sdk/cpp
                 ${CMAKE_CURRENT_BINARY_DIR}/prowrist_sdk)

# ============================================================================
# cxxopts - Command line argument parsing
# ============================================================================
include(FetchContent)
FetchContent_Declare(
  cxxopts
  GIT_REPOSITORY https://github.com/jarro2783/cxxopts.git
  GIT_TAG v3.1.1
  GIT_SHALLOW TRUE)
FetchContent_MakeAvailable(cxxopts)

# ============================================================================
# Demo Executables
# ============================================================================

# Individual demos
add_executable(connect src/connect.cpp)
target_include_directories(connect PRIVATE ${PROHAND_DEMO_INCLUDE_DIR})
target_link_libraries(connect PRIVATE prohand_client_sdk cxxopts::cxxopts)

add_executable(ping src/ping.cpp)
target_include_directories(ping PRIVATE ${PROHAND_DEMO_INCLUDE_DIR})
target_link_libraries(ping PRIVATE prohand_client_sdk cxxopts::cxxopts)

# ============================================================================
# test_hand Demo
# ============================================================================
add_executable(test_hand src/test_hand.cpp)
target_include_directories(test_hand PRIVATE ${PROHAND_DEMO_INCLUDE_DIR})
target_link_libraries(test_hand PRIVATE prohand_client_sdk cxxopts::cxxopts)

# ============================================================================
# cyclic_motion Demo
# ============================================================================
add_executable(cyclic_motion src/cyclic_motion.cpp)
target_include_directories(cyclic_motion PRIVATE ${PROHAND_DEMO_INCLUDE_DIR})
target_link_libraries(cyclic_motion PRIVATE prohand_client_sdk cxxopts::cxxopts)

# ============================================================================
# kapandji Demo (requires yaml-cpp)
# ============================================================================
find_package(yaml-cpp QUIET)
# Check for modern target first, then fallback to older-style target or
# variables
if(TARGET yaml-cpp::yaml-cpp)
  # Modern CMake target (from newer yaml-cpp or when built from source)
  add_executable(kapandji src/kapandji.cpp)
  target_include_directories(kapandji PRIVATE ${PROHAND_DEMO_INCLUDE_DIR})
  target_compile_definitions(kapandji PRIVATE YAML_CPP_FOUND)
  target_link_libraries(kapandji PRIVATE prohand_client_sdk cxxopts::cxxopts
                                         yaml-cpp::yaml-cpp)
  message(STATUS "  kapandji: Enabled (yaml-cpp::yaml-cpp target found)")
elseif(TARGET yaml-cpp)
  # Older-style target (some package managers provide this)
  add_executable(kapandji src/kapandji.cpp)
  target_include_directories(kapandji PRIVATE ${PROHAND_DEMO_INCLUDE_DIR})
  target_compile_definitions(kapandji PRIVATE YAML_CPP_FOUND)
  target_link_libraries(kapandji PRIVATE prohand_client_sdk cxxopts::cxxopts
                                         yaml-cpp)
  message(STATUS "  kapandji: Enabled (yaml-cpp target found)")
elseif(yaml-cpp_FOUND AND YAML_CPP_LIBRARIES)
  # Fallback: use variables (older find_package style)
  add_executable(kapandji src/kapandji.cpp)
  target_include_directories(kapandji PRIVATE ${PROHAND_DEMO_INCLUDE_DIR}
                                              ${YAML_CPP_INCLUDE_DIRS})
  target_compile_definitions(kapandji PRIVATE YAML_CPP_FOUND)
  target_link_libraries(kapandji PRIVATE prohand_client_sdk cxxopts::cxxopts
                                         ${YAML_CPP_LIBRARIES})
  message(STATUS "  kapandji: Enabled (yaml-cpp found via variables)")
else()
  # Build without yaml-cpp support
  add_executable(kapandji src/kapandji.cpp)
  target_include_directories(kapandji PRIVATE ${PROHAND_DEMO_INCLUDE_DIR})
  target_link_libraries(kapandji PRIVATE prohand_client_sdk cxxopts::cxxopts)
  if(yaml-cpp_FOUND)
    message(
      STATUS
        "  kapandji: Placeholder mode (yaml-cpp package found but no usable target/variables)"
    )
  else()
    message(STATUS "  kapandji: Placeholder mode (yaml-cpp not found)")
  endif()
endif()

# ============================================================================
# ProGlove Demos
# ============================================================================

# connect_glove Demo - Basic connection test
add_executable(connect_glove src/connect_glove.cpp)
target_include_directories(connect_glove PRIVATE ${PROHAND_DEMO_INCLUDE_DIR})
target_link_libraries(connect_glove PRIVATE proglove_client_sdk
                                            cxxopts::cxxopts)

# test_glove Demo - Tactile sensor monitoring
add_executable(test_glove src/test_glove.cpp)
target_include_directories(test_glove PRIVATE ${PROHAND_DEMO_INCLUDE_DIR})
target_link_libraries(test_glove PRIVATE proglove_client_sdk cxxopts::cxxopts)

# ============================================================================
# ProWristCam Demos
# ============================================================================

# connect_wristcam Demo - Basic connection test
add_executable(connect_wristcam src/connect_wristcam.cpp)
target_include_directories(connect_wristcam PRIVATE ${PROHAND_DEMO_INCLUDE_DIR})
target_link_libraries(connect_wristcam PRIVATE prowristcam_client_sdk
                                               cxxopts::cxxopts)

# test_wristcam Demo - Frame monitor
add_executable(test_wristcam src/test_wristcam.cpp)
target_include_directories(test_wristcam PRIVATE ${PROHAND_DEMO_INCLUDE_DIR})
target_link_libraries(test_wristcam PRIVATE prowristcam_client_sdk
                                            cxxopts::cxxopts)

# ============================================================================
# Installation
# ============================================================================
install(
  TARGETS connect
          ping
          test_hand
          cyclic_motion
          kapandji
          connect_glove
          test_glove
          connect_wristcam
          test_wristcam
  RUNTIME DESTINATION bin)

install(DIRECTORY include/ DESTINATION include)

# ============================================================================
# Build Info
# ============================================================================
message(STATUS "SDK Demo Configuration:")
message(STATUS "  C++ Standard: ${CMAKE_CXX_STANDARD}")
message(STATUS "  cxxopts: ${cxxopts_SOURCE_DIR}")
message(STATUS "")
message(STATUS "Using ProHand SDK from ../../prohand_sdk/cpp/")
message(STATUS "Using ProGlove SDK from ../../proglove_sdk/cpp/")
message(STATUS "Using ProWristCam SDK from ../../prowrist_sdk/cpp/")
