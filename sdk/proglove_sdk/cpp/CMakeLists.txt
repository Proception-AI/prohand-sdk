cmake_minimum_required(VERSION 3.16)

project(proglove_client_sdk LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ============================================================================
# ProGlove SDK - C/C++ Interface Library
# ============================================================================
# This is an INTERFACE library that provides: - C header: proglove_sdk.h -
# Dynamic library: libproglove_client_sdk.{so,dylib,dll} (or _aarch64.so on
# aarch64)
# ============================================================================

# Determine SDK paths
get_filename_component(PROGLOVE_SDK_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/.."
                       ABSOLUTE)
set(PROGLOVE_SDK_INCLUDE_DIR "${PROGLOVE_SDK_ROOT}/cpp/include")
set(PROGLOVE_SDK_LIB_DIR "${PROGLOVE_SDK_ROOT}/lib")

# Determine library name based on platform and architecture
if(CMAKE_SYSTEM_NAME MATCHES "Linux")
  # On Linux, check architecture for aarch64
  if(CMAKE_SYSTEM_PROCESSOR MATCHES "aarch64|arm64")
    set(PROGLOVE_SDK_LIB_NAME "proglove_client_sdk_aarch64")
    set(PROGLOVE_SDK_LIB_FILE "libproglove_client_sdk_aarch64.so")
  else()
    set(PROGLOVE_SDK_LIB_NAME "proglove_client_sdk")
    set(PROGLOVE_SDK_LIB_FILE "libproglove_client_sdk.so")
  endif()
elseif(CMAKE_SYSTEM_NAME MATCHES "Darwin")
  set(PROGLOVE_SDK_LIB_NAME "proglove_client_sdk")
  set(PROGLOVE_SDK_LIB_FILE "libproglove_client_sdk.dylib")
elseif(CMAKE_SYSTEM_NAME MATCHES "Windows")
  set(PROGLOVE_SDK_LIB_NAME "proglove_client_sdk")
  set(PROGLOVE_SDK_LIB_FILE "proglove_client_sdk.dll")
else()
  message(
    FATAL_ERROR
      "Unsupported platform: ${CMAKE_SYSTEM_NAME} (${CMAKE_SYSTEM_PROCESSOR})\n"
      "Supported platforms: Linux, Darwin (macOS), Windows")
endif()

# Find the actual library file
find_library(
  PROGLOVE_SDK_LIBRARY
  NAMES ${PROGLOVE_SDK_LIB_NAME}
  PATHS ${PROGLOVE_SDK_LIB_DIR}
  NO_DEFAULT_PATH REQUIRED)

# Create INTERFACE library for the SDK
add_library(proglove_client_sdk INTERFACE)

# Set include directories
target_include_directories(proglove_client_sdk
                           INTERFACE ${PROGLOVE_SDK_INCLUDE_DIR})

# Link with the actual library file (full path)
target_link_libraries(proglove_client_sdk INTERFACE ${PROGLOVE_SDK_LIBRARY})

# ============================================================================
# Installation (optional)
# ============================================================================
include(GNUInstallDirs)

install(
  TARGETS proglove_client_sdk
  EXPORT proglove_client_sdkTargets
  ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
  LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
  RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})

install(
  DIRECTORY ${PROGLOVE_SDK_INCLUDE_DIR}/
  DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}
  FILES_MATCHING
  PATTERN "*.h"
  PATTERN "*.hpp")

install(
  FILES ${PROGLOVE_SDK_LIB_DIR}/${PROGLOVE_SDK_LIB_FILE}
  DESTINATION ${CMAKE_INSTALL_LIBDIR}
  OPTIONAL)

# Install CMake config for find_package support
install(
  EXPORT proglove_client_sdkTargets
  FILE proglove_client_sdkTargets.cmake
  NAMESPACE proglove_client_sdk::
  DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/proglove_client_sdk)

# ============================================================================
# Build Info
# ============================================================================
message(STATUS "ProGlove Client SDK Configuration:")
message(STATUS "  Include: ${PROGLOVE_SDK_INCLUDE_DIR}")
message(STATUS "  Library: ${PROGLOVE_SDK_LIB_DIR}/${PROGLOVE_SDK_LIB_FILE}")
message(STATUS "  Library Name: ${PROGLOVE_SDK_LIB_NAME}")
