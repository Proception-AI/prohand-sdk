cmake_minimum_required(VERSION 3.16)

project(prohand_client_sdk LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ============================================================================
# ProHand SDK - C/C++ Interface Library
# ============================================================================
# This is an INTERFACE library that provides: - C header: prohand_sdk.h - C++
# wrapper: ProHandClient.hpp - Dynamic library:
# libprohand_client_sdk.{so,dylib,dll} (or _aarch64.so on aarch64)
# ============================================================================

# Determine SDK paths
get_filename_component(PROHAND_SDK_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/.."
                       ABSOLUTE)
set(PROHAND_SDK_INCLUDE_DIR "${PROHAND_SDK_ROOT}/cpp/include")
set(PROHAND_SDK_LIB_DIR "${PROHAND_SDK_ROOT}/lib")

# Determine library name based on platform and architecture
if(CMAKE_SYSTEM_NAME MATCHES "Linux")
  # On Linux, check architecture for aarch64
  if(CMAKE_SYSTEM_PROCESSOR MATCHES "aarch64|arm64")
    set(PROHAND_SDK_LIB_NAME "prohand_client_sdk_aarch64")
    set(PROHAND_SDK_LIB_FILE "libprohand_client_sdk_aarch64.so")
  else()
    set(PROHAND_SDK_LIB_NAME "prohand_client_sdk")
    set(PROHAND_SDK_LIB_FILE "libprohand_client_sdk.so")
  endif()
elseif(CMAKE_SYSTEM_NAME MATCHES "Darwin")
  set(PROHAND_SDK_LIB_NAME "prohand_client_sdk")
  set(PROHAND_SDK_LIB_FILE "libprohand_client_sdk.dylib")
elseif(CMAKE_SYSTEM_NAME MATCHES "Windows")
  set(PROHAND_SDK_LIB_NAME "prohand_client_sdk")
  set(PROHAND_SDK_LIB_FILE "prohand_client_sdk.dll")
else()
  message(
    FATAL_ERROR
      "Unsupported platform: ${CMAKE_SYSTEM_NAME} (${CMAKE_SYSTEM_PROCESSOR})\n"
      "Supported platforms: Linux, Darwin (macOS), Windows")
endif()

# Find the actual library file
find_library(
  PROHAND_SDK_LIBRARY
  NAMES ${PROHAND_SDK_LIB_NAME}
  PATHS ${PROHAND_SDK_LIB_DIR}
  NO_DEFAULT_PATH REQUIRED)

# Create INTERFACE library for the SDK
add_library(prohand_client_sdk INTERFACE)

# Set include directories
target_include_directories(prohand_client_sdk
                           INTERFACE ${PROHAND_SDK_INCLUDE_DIR})

# Link with the actual library file (full path)
target_link_libraries(prohand_client_sdk INTERFACE ${PROHAND_SDK_LIBRARY})

# ============================================================================
# Installation (optional)
# ============================================================================
include(GNUInstallDirs)

install(
  TARGETS prohand_client_sdk
  EXPORT prohand_client_sdkTargets
  ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
  LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
  RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})

install(
  DIRECTORY ${PROHAND_SDK_INCLUDE_DIR}/
  DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}
  FILES_MATCHING
  PATTERN "*.h"
  PATTERN "*.hpp")

install(
  FILES ${PROHAND_SDK_LIB_DIR}/${PROHAND_SDK_LIB_FILE}
  DESTINATION ${CMAKE_INSTALL_LIBDIR}
  OPTIONAL)

# Install CMake config for find_package support
install(
  EXPORT prohand_client_sdkTargets
  FILE prohand_client_sdkTargets.cmake
  NAMESPACE prohand_client_sdk::
  DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/prohand_client_sdk)

# ============================================================================
# Build Info
# ============================================================================
message(STATUS "ProHand Client SDK Configuration:")
message(STATUS "  Include: ${PROHAND_SDK_INCLUDE_DIR}")
message(STATUS "  Library: ${PROHAND_SDK_LIB_DIR}/${PROHAND_SDK_LIB_FILE}")
message(STATUS "  Library Name: ${PROHAND_SDK_LIB_NAME}")
