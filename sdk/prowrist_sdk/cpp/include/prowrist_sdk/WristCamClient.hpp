/**
 * WristCam Client C++ Wrapper
 *
 * RAII wrapper around the C API from prowrist_sdk.h
 */

#pragma once

#include <cstdint>
#include <optional>
#include <prowrist_sdk/prowrist_sdk.h>
#include <stdexcept>
#include <string>
#include <vector>

namespace prowrist_sdk {

/**
 * Exception thrown by SDK operations.
 */
class SdkException : public std::runtime_error {
public:
  explicit SdkException(const std::string &message)
      : std::runtime_error(message) {}
};

/**
 * A decoded JPEG frame from the wrist camera.
 */
struct WristCamFrame {
  uint16_t uid;              /**< Rolling frame counter */
  uint16_t timestamp;        /**< Low-16 ms since epoch */
  std::vector<uint8_t> jpeg; /**< Raw JPEG bytes */
};

/**
 * WristCam Client — RAII wrapper for WristCamClientHandle.
 *
 * Example:
 * @code
 *   using namespace prowrist_sdk;
 *
 *   WristCamClient client("ipc:///tmp/prowristcam-left-stream.ipc");
 *
 *   while (true) {
 *       if (auto frame = client.tryRecvFrame()) {
 *           printf("Frame uid=%u size=%zu\n",
 *                  frame->uid, frame->jpeg.size());
 *       }
 *       std::this_thread::sleep_for(std::chrono::milliseconds(1));
 *   }
 * @endcode
 */
class WristCamClient {
private:
  WristCamClientHandle *handle_;
  std::string streamEndpoint_;

public:
  /**
   * Create a new WristCam client.
   *
   * @param streamEndpoint  ZMQ endpoint to subscribe to
   *                        (e.g. "ipc:///tmp/prowristcam-left-stream.ipc")
   * @throws SdkException if creation fails.
   */
  explicit WristCamClient(const std::string &streamEndpoint)
      : handle_(nullptr), streamEndpoint_(streamEndpoint) {
    handle_ = prowristcam_client_create(streamEndpoint.c_str());
    if (!handle_) {
      throw SdkException("Failed to create WristCam client for endpoint: " +
                         streamEndpoint);
    }
  }

  // Non-copyable
  WristCamClient(const WristCamClient &) = delete;
  WristCamClient &operator=(const WristCamClient &) = delete;

  // Movable
  WristCamClient(WristCamClient &&other) noexcept
      : handle_(other.handle_),
        streamEndpoint_(std::move(other.streamEndpoint_)) {
    other.handle_ = nullptr;
  }

  WristCamClient &operator=(WristCamClient &&other) noexcept {
    if (this != &other) {
      if (handle_) {
        prowristcam_client_destroy(handle_);
      }
      handle_ = other.handle_;
      streamEndpoint_ = std::move(other.streamEndpoint_);
      other.handle_ = nullptr;
    }
    return *this;
  }

  ~WristCamClient() {
    if (handle_) {
      prowristcam_client_destroy(handle_);
      handle_ = nullptr;
    }
  }

  /**
   * Check if connected to the stream publisher.
   */
  bool isConnected() const {
    if (!handle_)
      return false;
    return prowristcam_client_is_connected(handle_) != 0;
  }

  /**
   * Try to receive the next JPEG frame (non-blocking).
   *
   * Returns std::nullopt immediately if no frame is queued.
   *
   * @return  WristCamFrame if available, std::nullopt otherwise.
   * @throws  SdkException on error.
   */
  std::optional<WristCamFrame> tryRecvFrame() {
    checkHandle();

    WristCamFrameInfo cFrame = {};
    int result = prowristcam_try_recv_frame(handle_, &cFrame);

    if (result > 0) {
      WristCamFrame frame;
      frame.uid = cFrame.uid;
      frame.timestamp = cFrame.timestamp;
      if (cFrame.jpeg_data && cFrame.jpeg_len > 0) {
        frame.jpeg.assign(cFrame.jpeg_data, cFrame.jpeg_data + cFrame.jpeg_len);
      }
      prowristcam_free_frame(&cFrame);
      return frame;
    }

    if (result == 0) {
      return std::nullopt;
    }

    checkResult(result, "tryRecvFrame");
    return std::nullopt; // unreachable
  }

  /**
   * Get SDK version string.
   */
  static std::string getVersion() {
    const char *ver = prowristcam_get_version();
    return ver ? std::string(ver) : "unknown";
  }

private:
  void checkHandle() const {
    if (!handle_) {
      throw SdkException("Client handle is null");
    }
  }

  void checkResult(int result, const std::string &operation) const {
    if (result == PROWRISTCAM_SUCCESS)
      return;

    std::string error = operation + " failed: ";
    switch (result) {
    case PROWRISTCAM_ERROR_NULL:
      error += "Null pointer error";
      break;
    case PROWRISTCAM_ERROR_CONNECTION:
      error += "Connection error";
      break;
    case PROWRISTCAM_ERROR_INVALID_ARGUMENT:
      error += "Invalid argument";
      break;
    default:
      error += "Unknown error (" + std::to_string(result) + ")";
      break;
    }
    throw SdkException(error);
  }
};

} // namespace prowrist_sdk
