cmake_minimum_required(VERSION 3.16)

project(prowristcam_client_sdk LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ============================================================================
# ProWristCam SDK - C/C++ Interface Library
# ============================================================================
# This is an INTERFACE library that provides: - C header:        prowrist_sdk.h
# - C++ RAII header: WristCamClient.hpp - Dynamic library:
# libprowristcam_client_sdk.{so,dylib,dll} (or _aarch64.so on aarch64)
# ============================================================================

# Determine SDK paths
get_filename_component(PROWRIST_SDK_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/.."
                       ABSOLUTE)
set(PROWRIST_SDK_INCLUDE_DIR "${PROWRIST_SDK_ROOT}/cpp/include")
set(PROWRIST_SDK_LIB_DIR "${PROWRIST_SDK_ROOT}/lib")

# Determine library name based on platform and architecture
if(CMAKE_SYSTEM_NAME MATCHES "Linux")
  if(CMAKE_SYSTEM_PROCESSOR MATCHES "aarch64|arm64")
    set(PROWRIST_SDK_LIB_NAME "prowristcam_client_sdk_aarch64")
    set(PROWRIST_SDK_LIB_FILE "libprowristcam_client_sdk_aarch64.so")
  else()
    set(PROWRIST_SDK_LIB_NAME "prowristcam_client_sdk")
    set(PROWRIST_SDK_LIB_FILE "libprowristcam_client_sdk.so")
  endif()
elseif(CMAKE_SYSTEM_NAME MATCHES "Darwin")
  set(PROWRIST_SDK_LIB_NAME "prowristcam_client_sdk")
  set(PROWRIST_SDK_LIB_FILE "libprowristcam_client_sdk.dylib")
elseif(CMAKE_SYSTEM_NAME MATCHES "Windows")
  set(PROWRIST_SDK_LIB_NAME "prowristcam_client_sdk")
  set(PROWRIST_SDK_LIB_FILE "prowristcam_client_sdk.dll")
else()
  message(
    FATAL_ERROR
      "Unsupported platform: ${CMAKE_SYSTEM_NAME} (${CMAKE_SYSTEM_PROCESSOR})\n"
      "Supported platforms: Linux, Darwin (macOS), Windows")
endif()

# Find the actual library file
find_library(
  PROWRIST_SDK_LIBRARY
  NAMES ${PROWRIST_SDK_LIB_NAME}
  PATHS ${PROWRIST_SDK_LIB_DIR}
  NO_DEFAULT_PATH REQUIRED)

# Create INTERFACE library for the SDK
add_library(prowristcam_client_sdk INTERFACE)

# Set include directories
target_include_directories(prowristcam_client_sdk
                           INTERFACE ${PROWRIST_SDK_INCLUDE_DIR})

# Link with the actual library file (full path)
target_link_libraries(prowristcam_client_sdk INTERFACE ${PROWRIST_SDK_LIBRARY})

# ============================================================================
# Installation (optional)
# ============================================================================
include(GNUInstallDirs)

install(
  TARGETS prowristcam_client_sdk
  EXPORT prowristcam_client_sdkTargets
  ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
  LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
  RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})

install(
  DIRECTORY ${PROWRIST_SDK_INCLUDE_DIR}/
  DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}
  FILES_MATCHING
  PATTERN "*.h"
  PATTERN "*.hpp")

install(
  FILES ${PROWRIST_SDK_LIB_DIR}/${PROWRIST_SDK_LIB_FILE}
  DESTINATION ${CMAKE_INSTALL_LIBDIR}
  OPTIONAL)

install(
  EXPORT prowristcam_client_sdkTargets
  FILE prowristcam_client_sdkTargets.cmake
  NAMESPACE prowristcam_client_sdk::
  DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/prowristcam_client_sdk)

# ============================================================================
# Build Info
# ============================================================================
message(STATUS "ProWristCam Client SDK Configuration:")
message(STATUS "  Include: ${PROWRIST_SDK_INCLUDE_DIR}")
message(STATUS "  Library: ${PROWRIST_SDK_LIB_DIR}/${PROWRIST_SDK_LIB_FILE}")
message(STATUS "  Library Name: ${PROWRIST_SDK_LIB_NAME}")
