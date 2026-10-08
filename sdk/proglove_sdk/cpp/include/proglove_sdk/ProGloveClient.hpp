/**
 * ProGlove Client C++ Wrapper
 *
 * RAII wrapper around the C API from proglove_sdk.h
 */

#pragma once

#include <cstdint>
#include <functional>
#include <optional>
#include <proglove_sdk/proglove_sdk.h>
#include <stdexcept>
#include <string>
#include <vector>

namespace proglove_sdk {

/**
 * Exception thrown by SDK operations
 */
class SdkException : public std::runtime_error {
public:
  explicit SdkException(const std::string &message)
      : std::runtime_error(message) {}
};

/**
 * USB Device information
 */
struct UsbDevice {
  std::string portName;
  std::string displayName;
};

/**
 * Tactile status data wrapper
 *
 * Contains tactile pressure values organized by joint segment.
 * Each finger has DIP (distal), MCP (metacarpal), and PIP (proximal) segments.
 */
struct TactileStatus {
  bool isValid;
  unsigned int timestamp;
  unsigned int uid;

  // Thumb segments (6+10+4 = 20 taxels)
  std::vector<uint16_t> t_dip;
  std::vector<uint16_t> t_mcp;
  std::vector<uint16_t> t_pip;

  // Index segments (4+2+2 = 8 taxels)
  std::vector<uint16_t> i_dip;
  std::vector<uint16_t> i_mcp;
  std::vector<uint16_t> i_pip;

  // Middle segments (4+2+2 = 8 taxels)
  std::vector<uint16_t> m_dip;
  std::vector<uint16_t> m_mcp;
  std::vector<uint16_t> m_pip;

  // Ring segments (4+2+2 = 8 taxels)
  std::vector<uint16_t> r_dip;
  std::vector<uint16_t> r_mcp;
  std::vector<uint16_t> r_pip;

  // Pinky segments (4+2+2 = 8 taxels)
  std::vector<uint16_t> p_dip;
  std::vector<uint16_t> p_mcp;
  std::vector<uint16_t> p_pip;

  // Palm segments (16+16+16 = 48 taxels)
  std::vector<uint16_t> upper_palm;
  std::vector<uint16_t> middle_palm;
  std::vector<uint16_t> lower_palm;
};

/**
 * IMU status data wrapper - fused orientation quaternion
 */
struct ImuStatus {
  bool isValid;
  unsigned int timestamp;
  float qw;
  float qx;
  float qy;
  float qz;
};

/**
 * ProGlove Client - RAII wrapper for ProGloveClientHandle
 */
class ProGloveClient {
private:
  ProGloveClientHandle *handle_;
  std::string statusEndpoint_;

public:
  /**
   * Create a new ProGlove client
   *
   * @param statusEndpoint ZMQ status endpoint (e.g.,
   * "ipc:///tmp/proglove-left-status.ipc")
   * @throws SdkException if connection fails
   */
  ProGloveClient(const std::string &statusEndpoint)
      : handle_(nullptr), statusEndpoint_(statusEndpoint) {
    handle_ = proglove_client_create(statusEndpoint.c_str());
    if (!handle_) {
      throw SdkException("Failed to create ProGlove client for endpoint: " +
                         statusEndpoint);
    }
  }

  // Disable copy
  ProGloveClient(const ProGloveClient &) = delete;
  ProGloveClient &operator=(const ProGloveClient &) = delete;

  // Enable move
  ProGloveClient(ProGloveClient &&other) noexcept
      : handle_(other.handle_),
        statusEndpoint_(std::move(other.statusEndpoint_)) {
    other.handle_ = nullptr;
  }

  ProGloveClient &operator=(ProGloveClient &&other) noexcept {
    if (this != &other) {
      if (handle_) {
        proglove_client_destroy(handle_);
      }
      handle_ = other.handle_;
      statusEndpoint_ = std::move(other.statusEndpoint_);
      other.handle_ = nullptr;
    }
    return *this;
  }

  /**
   * Destructor - cleanup resources
   */
  ~ProGloveClient() {
    if (handle_) {
      proglove_client_destroy(handle_);
      handle_ = nullptr;
    }
  }

  /**
   * Check if connected to device
   */
  bool isConnected() const {
    if (!handle_)
      return false;
    return proglove_client_is_connected(handle_) != 0;
  }

  /**
   * Send a ping command
   *
   * Since ProGlove uses PUB/SUB (not REQ/REP), this waits for
   * tactile data to confirm the connection is working.
   */
  void sendPing() {
    checkHandle();
    auto result = proglove_send_ping(handle_);
    // 0 means success (PROGLOVE_SUCCESS), negative means error
    if (result < 0) {
      checkResult(result, "sendPing");
    }
  }

  /**
   * Full OTA update: sends the image + key/sig, then answers every firmware
   * page request automatically, invoking `onProgress(pagesSent,
   * totalPages)` after each page (if given). Blocks until the transfer
   * succeeds, fails, or stalls for timeoutMs with no reply (the timeout
   * resets on every reply, so it's a stall detector, not a cap on total
   * transfer time).
   *
   * @param image Firmware image bytes
   * @param key 32-byte ed25519 public key (currently unenforced firmware-side)
   * @param sig 64-byte ed25519 signature (currently unenforced firmware-side)
   * @param onProgress Optional callback invoked after each page is sent
   * @param timeoutMs Milliseconds to wait for each firmware reply before giving
   * up (default: 15000)
   * @return true on success, false on firmware-reported error or timeout
   */
  bool performOta(
      const std::vector<uint8_t> &image, const std::vector<uint8_t> &key,
      const std::vector<uint8_t> &sig,
      std::function<void(unsigned int, unsigned int)> onProgress = nullptr,
      unsigned int timeoutMs = 15000) {
    checkHandle();
    if (key.size() != 32) {
      throw std::invalid_argument("key must be 32 bytes");
    }
    if (sig.size() != 64) {
      throw std::invalid_argument("sig must be 64 bytes");
    }

    // The trampoline + this pointer only need to stay alive for the
    // duration of this blocking call, so a stack-local std::function and
    // its address as user_data is safe here.
    int result = onProgress
                     ? proglove_perform_ota(handle_, image.data(), image.size(),
                                            key.data(), sig.data(), timeoutMs,
                                            &progressTrampoline, &onProgress)
                     : proglove_perform_ota(handle_, image.data(), image.size(),
                                            key.data(), sig.data(), timeoutMs,
                                            nullptr, nullptr);
    if (result < 0) {
      checkResult(result, "performOta");
    }
    return result == 1;
  }

  /**
   * Full calibration cycle: clear the existing baseline, then start a fresh
   * snapshot, blocking until BaselineCommitted arrives or timeoutMs elapses.
   *
   * @param timeoutMs Milliseconds to wait for BaselineCommitted (default: 5000)
   * @return true if calibration completed within the timeout, false if it
   * timed out (baseline may still complete later).
   */
  bool calibrate(unsigned int timeoutMs = 5000) {
    checkHandle();
    int result = proglove_calibrate_and_wait(handle_, timeoutMs);
    if (result < 0) {
      checkResult(result, "calibrate");
    }
    return result == 1;
  }

  /**
   * Toggle stuck-pixel masking.
   */
  void setDenoiseEnabled(bool enabled) {
    checkHandle();
    checkResult(proglove_set_denoise_enabled(handle_, enabled ? 1 : 0),
                "setDenoiseEnabled");
  }

  /**
   * Default filter configuration - a sensible starting point to tweak
   * before calling setFilterConfig().
   */
  static ProGloveFilterConfig defaultFilterConfig() {
    ProGloveFilterConfig cfg{};
    checkResult(proglove_get_default_filter_config(&cfg),
                "getDefaultFilterConfig");
    return cfg;
  }

  /**
   * Replace the entire tactile filter configuration - deadzone on/off,
   * stuck-pixel spatial-isolation threshold, and stuck-detection timing.
   * This replaces the whole config, not a per-field patch — start from
   * defaultFilterConfig() and override only what you need.
   */
  void setFilterConfig(const ProGloveFilterConfig &config) {
    checkHandle();
    checkResult(proglove_set_filter_config(handle_, &config),
                "setFilterConfig");
  }

  /**
   * Try to receive tactile status (non-blocking)
   *
   * @return TactileStatus if available, nullopt otherwise
   */
  std::optional<TactileStatus> tryRecvStatus() {
    checkHandle();

    ProGloveTactileStatus cStatus = {};
    int result = proglove_try_recv_status(handle_, &cStatus);

    if (result > 0) {
      return convertTactile(cStatus);
    } else if (result == 0) {
      return std::nullopt;
    } else {
      checkResult(result, "tryRecvStatus");
      return std::nullopt; // Unreachable
    }
  }

  /**
   * Try to receive a pre-filter RAW tactile frame (non-blocking).
   *
   * Pure hardware ADC from the driver's secondary raw node (no host
   * filter/baseline). Poll alongside tryRecvStatus() to capture raw +
   * processed together.
   *
   * @return TactileStatus if a raw frame is available, nullopt otherwise
   */
  std::optional<TactileStatus> tryRecvRawTactile() {
    checkHandle();

    ProGloveTactileStatus cStatus = {};
    int result = proglove_try_recv_raw_tactile(handle_, &cStatus);

    if (result > 0) {
      return convertTactile(cStatus);
    } else if (result == 0) {
      return std::nullopt;
    } else {
      checkResult(result, "tryRecvRawTactile");
      return std::nullopt; // Unreachable
    }
  }

  /**
   * Whether this client derived a raw tactile endpoint (a local -status.ipc
   * path). true doesn't guarantee the driver is publishing raw.
   */
  bool hasRawTactile() {
    checkHandle();
    return proglove_has_raw_tactile(handle_) > 0;
  }

  /** Convert a C tactile struct into the C++ `TactileStatus`. */
  static TactileStatus convertTactile(const ProGloveTactileStatus &cStatus) {
    TactileStatus status;
    status.isValid = cStatus.is_valid != 0;
    status.timestamp = cStatus.timestamp;
    status.uid = cStatus.uid;

    // Thumb segments
    status.t_dip.assign(cStatus.t_dip, cStatus.t_dip + PROGLOVE_TAXELS_T_DIP);
    status.t_mcp.assign(cStatus.t_mcp, cStatus.t_mcp + PROGLOVE_TAXELS_T_MCP);
    status.t_pip.assign(cStatus.t_pip, cStatus.t_pip + PROGLOVE_TAXELS_T_PIP);

    // Index segments
    status.i_dip.assign(cStatus.i_dip, cStatus.i_dip + PROGLOVE_TAXELS_I_DIP);
    status.i_mcp.assign(cStatus.i_mcp, cStatus.i_mcp + PROGLOVE_TAXELS_I_MCP);
    status.i_pip.assign(cStatus.i_pip, cStatus.i_pip + PROGLOVE_TAXELS_I_PIP);

    // Middle segments
    status.m_dip.assign(cStatus.m_dip, cStatus.m_dip + PROGLOVE_TAXELS_M_DIP);
    status.m_mcp.assign(cStatus.m_mcp, cStatus.m_mcp + PROGLOVE_TAXELS_M_MCP);
    status.m_pip.assign(cStatus.m_pip, cStatus.m_pip + PROGLOVE_TAXELS_M_PIP);

    // Ring segments
    status.r_dip.assign(cStatus.r_dip, cStatus.r_dip + PROGLOVE_TAXELS_R_DIP);
    status.r_mcp.assign(cStatus.r_mcp, cStatus.r_mcp + PROGLOVE_TAXELS_R_MCP);
    status.r_pip.assign(cStatus.r_pip, cStatus.r_pip + PROGLOVE_TAXELS_R_PIP);

    // Pinky segments
    status.p_dip.assign(cStatus.p_dip, cStatus.p_dip + PROGLOVE_TAXELS_P_DIP);
    status.p_mcp.assign(cStatus.p_mcp, cStatus.p_mcp + PROGLOVE_TAXELS_P_MCP);
    status.p_pip.assign(cStatus.p_pip, cStatus.p_pip + PROGLOVE_TAXELS_P_PIP);

    // Palm segments
    status.upper_palm.assign(cStatus.upper_palm,
                             cStatus.upper_palm + PROGLOVE_TAXELS_UPPER_PALM);
    status.middle_palm.assign(
        cStatus.middle_palm, cStatus.middle_palm + PROGLOVE_TAXELS_MIDDLE_PALM);
    status.lower_palm.assign(cStatus.lower_palm,
                             cStatus.lower_palm + PROGLOVE_TAXELS_LOWER_PALM);

    return status;
  }

  /**
   * Try to receive IMU status (non-blocking)
   *
   * @return ImuStatus if the next message was IMU data, nullopt otherwise
   * (including when the next message was a different type — call this
   * alongside tryRecvStatus() and check for nullopt on each).
   */
  std::optional<ImuStatus> tryRecvImuStatus() {
    checkHandle();

    ProGloveImuStatus cStatus = {};
    int result = proglove_try_recv_imu_status(handle_, &cStatus);

    if (result > 0) {
      ImuStatus status;
      status.isValid = cStatus.is_valid != 0;
      status.timestamp = cStatus.timestamp;
      status.qw = cStatus.qw;
      status.qx = cStatus.qx;
      status.qy = cStatus.qy;
      status.qz = cStatus.qz;
      return status;
    } else if (result == 0) {
      return std::nullopt;
    } else {
      checkResult(result, "tryRecvImuStatus");
      return std::nullopt; // Unreachable
    }
  }

  /**
   * Discover USB devices (static method)
   */
  static std::vector<UsbDevice> discoverUsbDevices() {
    ProGloveUsbDeviceInfo devices[10];
    int count = proglove_discover_usb_devices(devices, 10);

    if (count < 0) {
      throw SdkException("USB discovery failed");
    }

    std::vector<UsbDevice> result;
    for (int i = 0; i < count; ++i) {
      UsbDevice dev;
      if (devices[i].port_name) {
        dev.portName = devices[i].port_name;
        proglove_free_string(const_cast<char *>(devices[i].port_name));
      }
      if (devices[i].display_name) {
        dev.displayName = devices[i].display_name;
        proglove_free_string(const_cast<char *>(devices[i].display_name));
      }
      result.push_back(std::move(dev));
    }

    return result;
  }

  /**
   * Get SDK version
   */
  static std::string getVersion() {
    const char *ver = proglove_get_version();
    return ver ? std::string(ver) : "unknown";
  }

private:
  static void progressTrampoline(unsigned int pagesSent,
                                 unsigned int totalPages, void *userData) {
    auto *fn = static_cast<std::function<void(unsigned int, unsigned int)> *>(
        userData);
    (*fn)(pagesSent, totalPages);
  }

  void checkHandle() const {
    if (!handle_) {
      throw SdkException("Client handle is null");
    }
  }

  static void checkResult(int result, const std::string &operation) {
    if (result == PROGLOVE_SUCCESS) {
      return;
    }

    std::string error = operation + " failed: ";
    switch (result) {
    case PROGLOVE_ERROR_NULL:
      error += "Null pointer error";
      break;
    case PROGLOVE_ERROR_CONNECTION:
      error += "Connection error";
      break;
    case PROGLOVE_ERROR_INVALID_ARGUMENT:
      error += "Invalid argument";
      break;
    case PROGLOVE_ERROR_NOT_CONNECTED:
      error += "Not connected";
      break;
    case PROGLOVE_ERROR_UNSUPPORTED:
      error += "Unsupported operation";
      break;
    default:
      error += "Unknown error (" + std::to_string(result) + ")";
      break;
    }
    throw SdkException(error);
  }
};

} // namespace proglove_sdk
