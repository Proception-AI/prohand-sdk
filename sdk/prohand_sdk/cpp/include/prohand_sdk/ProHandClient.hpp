/**
 * ProHand Client C++ Wrapper
 *
 * RAII wrapper around the C API from prohand_sdk.h
 */

#pragma once

#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <optional>
#include <prohand_sdk/prohand_sdk.h>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

namespace prohand_sdk {

/// Matches MAX_SIGNALS in the SDK's signal_rate tracker — the hard bound on how
/// many rows either getter can return, so a buffer this size never truncates.
constexpr size_t kMaxSignals = 48;

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
 * Rotary/linear positions and targets. Superseded by tryRecvMessage(), which
 * covers every message kind the firmware publishes.
 *
 * Values are raw wire units, NOT radians: rotary counts are FT3950 encoder
 * counts (0-4095, neutral 2048) and linear counts are 0.01 mm. An earlier
 * version of this header converted them with a centidegree-to-radian factor,
 * which is wrong for both — the wire never carried degrees.
 *
 * Only the vector matching statusType holds data on any given read; the others
 * are zero.
 */
struct HandStatus {
  bool isValid;
  // 0=other, 1=rotary status, 2=linear status, 3=rotary target, 4=linear target
  int statusType;
  std::vector<int16_t> rotaryPositions; // [16] encoder counts
  std::vector<int16_t> linearPositions; // [2]  0.01 mm
  std::vector<int16_t> rotaryTargets;   // [16] encoder counts
  std::vector<int16_t> linearTargets;   // [2]  0.01 mm
};

/**
 * Scaling for the joint-space payloads, which are the only wire values carrying
 * a real unit: CompactJointState packs position as 0.01 degrees and velocity or
 * torque as a full-range int16.
 */
namespace joint_scale {
constexpr float kCentidegToRad = 3.14159265358979323846f / 18000.0f;
constexpr float kNormalized = 1.0f / 32767.0f;

/// Joint position in radians from a packed CompactJointState.
inline float toRadians(const CompactJointState &state) {
  return static_cast<float>(state.scaled_position) * kCentidegToRad;
}

/// Normalized velocity or torque (-1.0..1.0) from a packed CompactJointState.
inline float toNormalized(const CompactJointState &state) {
  return static_cast<float>(state.normalized_vel_or_tau) * kNormalized;
}
} // namespace joint_scale

/**
 * ProHand Client - RAII wrapper for ProHandClientHandle
 */
class ProHandClient {
private:
  ProHandClientHandle *handle_;
  std::string commandEndpoint_;
  std::string statusEndpoint_;

  static void checkPositions(const std::vector<float> &positions) {
    if (positions.size() != 20) {
      throw SdkException(
          "positions must have 20 elements (5 fingers × 4 joints)");
    }
  }

  /**
   * Broadcast a whole-hand or per-finger torque vector across the 20 per-joint
   * slots the wire carries. A 20-element vector passes through unchanged.
   */
  static std::array<float, 20>
  expandTorques(const std::vector<float> &torques) {
    std::array<float, 20> perJoint{};
    switch (torques.size()) {
    case 1:
      perJoint.fill(torques[0]);
      break;
    case 5:
      for (size_t i = 0; i < perJoint.size(); ++i) {
        perJoint[i] = torques[i / 4]; // 4 joints per finger
      }
      break;
    case 20:
      std::copy(torques.begin(), torques.end(), perJoint.begin());
      break;
    default:
      throw SdkException(
          "torques must have 1, 5 (per finger) or 20 (per joint) elements");
    }
    return perJoint;
  }

public:
  /**
   * Create a new ProHand client
   *
   * @param commandEndpoint ZMQ command endpoint (e.g., "tcp://127.0.0.1:5562")
   * @param statusEndpoint ZMQ status endpoint (e.g., "tcp://127.0.0.1:5561")
   * @param handStreamingEndpoint ZMQ hand streaming endpoint (e.g.,
   * "tcp://127.0.0.1:5563")
   * @param wristStreamingEndpoint ZMQ wrist streaming endpoint (e.g.,
   * "tcp://127.0.0.1:5564")
   * @throws SdkException if connection fails
   */
  ProHandClient(const std::string &commandEndpoint,
                const std::string &statusEndpoint,
                const std::string &handStreamingEndpoint,
                const std::string &wristStreamingEndpoint)
      : handle_(nullptr), commandEndpoint_(commandEndpoint),
        statusEndpoint_(statusEndpoint) {
    handle_ = prohand_client_create(
        commandEndpoint.c_str(), statusEndpoint.c_str(),
        handStreamingEndpoint.c_str(), wristStreamingEndpoint.c_str());

    if (!handle_) {
      throw SdkException("Failed to create ProHand client");
    }
  }

  /**
   * Configure wrist motion limits (only effective if motion profiler is enabled
   * in the SDK build)
   *
   * @param max_velocity 2 values (rad/s)
   * @param max_acceleration 2 values (rad/s^2)
   * @param max_jerk 2 values (rad/s^3)
   * @throws SdkException on error
   */
  void setWristLimits(const std::vector<float> &max_velocity,
                      const std::vector<float> &max_acceleration,
                      const std::vector<float> &max_jerk) {
    checkHandle();
    if (max_velocity.size() != 2 || max_acceleration.size() != 2 ||
        max_jerk.size() != 2) {
      throw SdkException("wrist limits must have 2 elements each");
    }
    auto result = prohand_set_wrist_limits(
        handle_, max_velocity.data(), max_acceleration.data(), max_jerk.data());
    checkResult(result, "setWristLimits");
  }

  /**
   * Take the next qualified monitoring event, oldest first.
   *
   * Events run *beside* the status stream, not in front of it — nothing is
   * filtered out of tryRecvMessage(). An event says a condition has been
   * established (a thermal warning that persisted, a lockdown), which is what
   * you can act on; a lone alert cannot express that.
   *
   * @return empty when the queue is drained
   * @throws SdkException on error
   */
  std::optional<ProHandSystemEvent> pollEvent() {
    checkHandle();
    ProHandSystemEvent event{};
    auto n = prohand_poll_system_event(handle_, &event);
    if (n < 0) {
      checkResult(static_cast<ProHandResult>(n), "pollEvent");
    }
    if (n == 1) {
      return event;
    }
    return std::nullopt;
  }

  /** Every queued monitoring event, oldest first. */
  std::vector<ProHandSystemEvent> drainEvents() {
    std::vector<ProHandSystemEvent> out;
    while (auto e = pollEvent()) {
      out.push_back(*e);
    }
    return out;
  }

  /**
   * Events discarded because the queue filled — non-zero means this client is
   * not polling often enough. The queue is bounded and drops oldest-first, so
   * falling behind costs fixed memory, not unbounded growth.
   *
   * @throws SdkException on error
   */
  int32_t droppedEvents() {
    checkHandle();
    auto n = prohand_dropped_event_count(handle_);
    if (n < 0) {
      checkResult(static_cast<ProHandResult>(n), "droppedEvents");
    }
    return n;
  }

  /**
   * Aggregate health of the hand: liveness, state, thermal load and alert rates
   * in one passive read.
   *
   * Prefer this over reacting to individual alerts — a lone alert carries no
   * severity, while a rate and a latched lockdown state do.
   *
   * Assembled client-side from the driver's raw status stream. Never consumes a
   * status message or sends a command, so it is safe to poll from a UI at frame
   * rate.
   *
   * @throws SdkException on error
   */
  ProHandSystemStatus systemStatus() {
    checkHandle();
    ProHandSystemStatus status{};
    auto result = prohand_get_system_status(handle_, &status);
    checkResult(result, "systemStatus");
    return status;
  }

  /**
   * Thermal load per subsystem, as a percentage of the maximum rate at which
   * firmware can publish thermal alerts. Quiet subsystems are omitted.
   *
   * Firmware caps thermal alerts at one per subsystem per 5 s, so that ceiling
   * is the denominator: a lone temperature excursion reads single digits, a
   * genuinely hot actuator saturates the channel and reads 100. Prefer this
   * over reacting to individual warnings — one warning carries no severity, a
   * percentage does.
   *
   * Measured by the driver on its raw alert stream and republished on the
   * filtered status channel this client subscribes to, so the debouncing
   * applied to that channel does not distort these numbers — and the counts
   * span the driver's uptime, not just this connection.
   *
   * @throws SdkException on error
   */
  std::vector<ThermalLoad> thermalLoad() {
    checkHandle();
    std::vector<ThermalLoad> loads(kMaxSignals);
    auto n = prohand_get_thermal_load(handle_, loads.data(),
                                      static_cast<uint32_t>(loads.size()));
    if (n < 0) {
      checkResult(static_cast<ProHandResult>(n), "thermalLoad");
    }
    loads.resize(static_cast<size_t>(n));
    return loads;
  }

  /**
   * Every alerting signal active inside the window, thermal or not.
   *
   * One row per unique (source, severity, actuator, code). thermalLoad() is the
   * thermal-only view of the same data, reassembled per subsystem.
   *
   * @throws SdkException on error
   */
  std::vector<SignalRate> signalRates() {
    checkHandle();
    std::vector<SignalRate> rates(kMaxSignals);
    auto n = prohand_get_signal_rates(handle_, rates.data(),
                                      static_cast<uint32_t>(rates.size()));
    if (n < 0) {
      checkResult(static_cast<ProHandResult>(n), "signalRates");
    }
    rates.resize(static_cast<size_t>(n));
    return rates;
  }

  /**
   * The most loaded subsystem, lockdown ranked above warning.
   *
   * @return empty when nothing has alerted inside the window
   * @throws SdkException on error
   */
  std::optional<ThermalLoad> worstThermalLoad() {
    checkHandle();
    ThermalLoad load{};
    auto n = prohand_get_worst_thermal_load(handle_, &load);
    if (n < 0) {
      checkResult(static_cast<ProHandResult>(n), "worstThermalLoad");
    }
    if (n == 1) {
      return load;
    }
    return std::nullopt;
  }

  // Disable copy
  ProHandClient(const ProHandClient &) = delete;
  ProHandClient &operator=(const ProHandClient &) = delete;

  // Enable move
  ProHandClient(ProHandClient &&other) noexcept
      : handle_(other.handle_),
        commandEndpoint_(std::move(other.commandEndpoint_)),
        statusEndpoint_(std::move(other.statusEndpoint_)) {
    other.handle_ = nullptr;
  }

  ProHandClient &operator=(ProHandClient &&other) noexcept {
    if (this != &other) {
      if (handle_) {
        prohand_client_destroy(handle_);
      }
      handle_ = other.handle_;
      commandEndpoint_ = std::move(other.commandEndpoint_);
      statusEndpoint_ = std::move(other.statusEndpoint_);
      other.handle_ = nullptr;
    }
    return *this;
  }

  /**
   * Destructor - cleanup resources
   */
  ~ProHandClient() {
    if (handle_) {
      prohand_client_destroy(handle_);
      handle_ = nullptr;
    }
  }

  /**
   * Check if connected to device
   */
  bool isConnected() const {
    if (!handle_)
      return false;
    return prohand_client_is_connected(handle_) != 0;
  }

  /**
   * Milliseconds elapsed since the last status message arrived
   *
   * Finer-grained liveness than isConnected(), which stays true for up to 10
   * seconds after the driver goes silent. The counter is seeded at
   * construction, so treat the value as meaningful only after the first
   * tryRecvStatus().
   */
  uint64_t msSinceLastHeartbeat() const {
    checkHandle();
    uint64_t ms = 0;
    auto result = prohand_ms_since_last_heartbeat(handle_, &ms);
    checkResult(result, "msSinceLastHeartbeat");
    return ms;
  }

  /**
   * Send a ping command
   */
  void sendPing() {
    checkHandle();
    auto result = prohand_send_ping(handle_);
    checkResult(result, "sendPing");
  }

  /**
   * Enable or disable streaming mode
   */
  void setStreamingMode(bool enabled) {
    checkHandle();
    auto result = prohand_set_streaming_mode(handle_, enabled ? 1 : 0);
    checkResult(result, "setStreamingMode");
  }

  /**
   * Check if the driver is in Running state (streaming active)
   *
   * Polls the status channel and checks if RotaryState or LinearState
   * is in Running mode, which indicates streaming is truly active.
   *
   * @return true if in running state, false otherwise
   */
  bool isRunningState() {
    checkHandle();
    return prohand_is_running_state(handle_) == 1;
  }

  /**
   * Wait for streaming connection to be established with state verification
   *
   * This method repeatedly sends setStreamingMode(true) and polls for
   * Running state until confirmed or timeout.
   *
   * @param timeout Maximum time to wait in seconds (default: 1.0)
   * @param retryInterval How often to retry setStreamingMode in seconds
   * (default: 0.3)
   * @return true if ready and in Running state, false if timeout
   *
   * Example:
   *   client.setStreamingMode(true);
   *   if (client.waitForStreamingReady()) {
   *       // Driver is confirmed in Running state
   *       client.sendRotaryStreams(positions, torques);
   *   }
   */
  bool waitForStreamingReady(double timeout = 1.0, double retryInterval = 0.3) {
    checkHandle();

    // First, verify command channel is working
    try {
      sendPing();
    } catch (...) {
      return false;
    }

    auto start = std::chrono::steady_clock::now();
    auto lastRetry = start;
    const double pollInterval = 0.05; // Poll every 50ms

    // Initial delay for ZMQ PUB/SUB connection to establish
    std::this_thread::sleep_for(std::chrono::duration<double>(0.2));

    // Keep retrying setStreamingMode until Running state is detected
    while (true) {
      auto now = std::chrono::steady_clock::now();
      auto elapsed = std::chrono::duration<double>(now - start).count();

      if (elapsed >= timeout) {
        break; // Timeout
      }

      // Check if driver reports Running state
      if (isRunningState()) {
        return true;
      }

      // Retry setStreamingMode if enough time has passed
      auto elapsedSinceRetry =
          std::chrono::duration<double>(now - lastRetry).count();
      if (elapsedSinceRetry >= retryInterval) {
        try {
          setStreamingMode(true);
          lastRetry = now;
        } catch (...) {
          // Ignore errors, keep trying
        }
      }

      // Wait before next poll
      double remaining = timeout - elapsed;
      if (remaining > 0) {
        std::this_thread::sleep_for(
            std::chrono::duration<double>(std::min(pollInterval, remaining)));
      } else {
        break;
      }
    }

    // Timeout - check one last time
    return isRunningState();
  }

  /**
   * Send rotary commands (16 finger joints)
   *
   * @param positions 16 position values in radians
   * @param torques 16 torque values (normalized 0.0 to 1.0)
   */
  void sendRotaryCommands(const std::vector<float> &positions,
                          const std::vector<float> &torques) {
    checkHandle();

    if (positions.size() != 16 || torques.size() != 16) {
      throw SdkException("positions and torques must have 16 elements");
    }

    auto result =
        prohand_send_rotary_commands(handle_, positions.data(), torques.data());
    checkResult(result, "sendRotaryCommands");
  }

  /**
   * Send linear commands (2 wrist motors)
   *
   * @param positions 2 position values in radians
   * @param speeds 2 speed values (normalized 0.0 to 1.0)
   */
  void sendLinearCommands(const std::vector<float> &positions,
                          const std::vector<float> &speeds) {
    checkHandle();

    if (positions.size() != 2 || speeds.size() != 2) {
      throw SdkException("positions and speeds must have 2 elements");
    }

    auto result =
        prohand_send_linear_commands(handle_, positions.data(), speeds.data());
    checkResult(result, "sendLinearCommands");
  }

  /**
   * Send rotary commands via PUB/SUB streaming channel (16 finger joints)
   *
   * Uses the streaming socket for high-frequency control (100+ Hz).
   * Requires: Client created with streaming endpoint AND driver in streaming
   * mode.
   *
   * @param positions 16 position values in radians
   * @param torques 16 torque values (normalized 0.0 to 1.0)
   * @throws SdkException if streaming not available or driver not in streaming
   * mode
   */
  void sendRotaryStreams(const std::vector<float> &positions,
                         const std::vector<float> &torques) {
    checkHandle();

    if (positions.size() != 16 || torques.size() != 16) {
      throw SdkException("positions and torques must have 16 elements");
    }

    auto result =
        prohand_send_rotary_streams(handle_, positions.data(), torques.data());
    checkResult(result, "sendRotaryStreams");
  }

  /**
   * Send linear commands via PUB/SUB streaming channel (2 wrist motors)
   *
   * Uses the streaming socket for high-frequency control.
   * Requires: Client created with streaming endpoint AND driver in streaming
   * mode.
   *
   * @param positions 2 position values in radians
   * @param speeds 2 speed values (normalized 0.0 to 1.0)
   * @throws SdkException if streaming not available or driver not in streaming
   * mode
   */
  void sendLinearStreams(const std::vector<float> &positions,
                         const std::vector<float> &speeds) {
    checkHandle();

    if (positions.size() != 2 || speeds.size() != 2) {
      throw SdkException("positions and speeds must have 2 elements");
    }

    auto result =
        prohand_send_linear_streams(handle_, positions.data(), speeds.data());
    checkResult(result, "sendLinearStreams");
  }

  /**
   * Send wrist joint command via REQ/REP command channel (high-level wrist
   * joints)
   *
   * Uses the command socket. For high-frequency commands, use
   * sendWristStreams() instead.
   *
   * @param positions 2 wrist joint angles in radians
   * @param use_profiler Whether to enable wrist motion profiling
   * (position-only, implicit max velocity)
   * @throws SdkException on error
   */
  void sendWristCommands(const std::vector<float> &positions,
                         bool use_profiler = false) {
    checkHandle();
    if (positions.size() != 2) {
      throw SdkException("positions must have 2 elements");
    }
    auto result =
        prohand_send_wrist_command(handle_, positions.data(), use_profiler);
    checkResult(result, "sendWristCommands");
  }

  /**
   * Send wrist joint command via PUB/SUB streaming channel (high-level wrist
   * joints)
   *
   * Uses the streaming socket for high-frequency commands.
   * Requires: Client created with streaming endpoint AND driver in streaming
   * mode.
   *
   * @param positions 2 wrist joint angles in radians
   * @param use_profiler Whether to enable wrist motion profiling
   * (position-only, implicit max velocity)
   * @throws SdkException if streaming not available or driver not in streaming
   * mode
   */
  void sendWristStreams(const std::vector<float> &positions,
                        bool use_profiler = false) {
    checkHandle();
    if (positions.size() != 2) {
      throw SdkException("positions must have 2 elements");
    }
    auto result =
        prohand_send_wrist_streams(handle_, positions.data(), use_profiler);
    checkResult(result, "sendWristStreams");
  }

  /**
   * Send hand command via REQ/REP command channel (high-level joint angles,
   * uses inverse kinematics)
   *
   * Uses the command socket. For high-frequency commands, use
   * sendHandStreams() instead.
   *
   * This sends joint angles per finger, which the firmware processes through
   * inverse kinematics to compute actuator positions. This is the high-level
   * API.
   *
   * @param positions 20 position values in radians (5 fingers × 4 joints)
   *                  Order: thumb[0-3], index[4-7], middle[8-11], ring[12-15],
   * pinky[16-19]
   * @param torques Torque, normalized 0.0 to 1.0. Accepts 1 value (whole hand),
   * 5 (per finger, thumb-to-pinky) or 20 (per joint, same order as positions).
   * @param velocitySaturation Global servo velocity cap, normalized 0.0 to 1.0.
   * Pass 0.0 to use the firmware default. The cap is per-hand, not per-finger.
   * @throws SdkException on error
   */
  void sendHandCommands(const std::vector<float> &positions,
                        const std::vector<float> &torques,
                        float velocitySaturation = 0.0f) {
    checkHandle();
    checkPositions(positions);
    auto perJoint = expandTorques(torques);

    auto result = prohand_send_hand_command(
        handle_, positions.data(), perJoint.data(), velocitySaturation);
    checkResult(result, "sendHandCommands");
  }

  /** Uniform-torque overload of sendHandCommands(). */
  void sendHandCommands(const std::vector<float> &positions, float torque,
                        float velocitySaturation = 0.0f) {
    sendHandCommands(positions, std::vector<float>{torque}, velocitySaturation);
  }

  /**
   * Send hand command via PUB/SUB streaming channel (high-level joint angles,
   * uses inverse kinematics)
   *
   * Uses the streaming socket for high-frequency commands.
   * Requires: Client created with streaming endpoint AND driver in streaming
   * mode.
   *
   * This sends joint angles per finger, which the firmware processes through
   * inverse kinematics to compute actuator positions. This is the high-level
   * API.
   *
   * @param positions 20 position values in radians (5 fingers × 4 joints)
   *                  Order: thumb[0-3], index[4-7], middle[8-11], ring[12-15],
   * pinky[16-19]
   * @param torques Torque, normalized 0.0 to 1.0. Accepts 1 value (whole hand),
   * 5 (per finger, thumb-to-pinky) or 20 (per joint, same order as positions).
   * @param velocitySaturation Global servo velocity cap, normalized 0.0 to 1.0.
   * Pass 0.0 to use the firmware default. The cap is per-hand, not per-finger.
   * @throws SdkException if streaming not available or driver not in streaming
   * mode
   */
  void sendHandStreams(const std::vector<float> &positions,
                       const std::vector<float> &torques,
                       float velocitySaturation = 0.0f) {
    checkHandle();
    checkPositions(positions);
    auto perJoint = expandTorques(torques);

    auto result = prohand_send_hand_streams(
        handle_, positions.data(), perJoint.data(), velocitySaturation);
    checkResult(result, "sendHandStreams");
  }

  /** Uniform-torque overload of sendHandStreams(). */
  void sendHandStreams(const std::vector<float> &positions, float torque,
                       float velocitySaturation = 0.0f) {
    sendHandStreams(positions, std::vector<float>{torque}, velocitySaturation);
  }

  /**
   * Perform zero calibration on selected joints
   *
   * @param mask 16 boolean values indicating which joints to calibrate
   */
  void sendZeroCalibration(const std::vector<bool> &mask) {
    checkHandle();

    if (mask.size() != 16) {
      throw SdkException("mask must have 16 elements");
    }

    std::vector<int> intMask(16);
    for (size_t i = 0; i < 16; ++i) {
      intMask[i] = mask[i] ? 1 : 0;
    }

    auto result = prohand_send_zero_calibration(handle_, intMask.data());
    checkResult(result, "sendZeroCalibration");
  }

  /**
   * Start or abort auto-calibration for the selected fingers
   *
   * Drives each selected finger against its hard stops to discover its range.
   * The hand must be unobstructed. Progress is reported on the status channel.
   *
   * @param fingerMask Bitwise OR of PROHAND_CALIB_* values.
   * PROHAND_CALIB_ABORT (0) aborts a running calibration.
   */
  void sendAutoCalibration(uint8_t fingerMask = PROHAND_CALIB_ALL) {
    checkHandle();
    auto result = prohand_send_auto_calibration(handle_, fingerMask);
    checkResult(result, "sendAutoCalibration");
  }

  /**
   * Start or abort the homing sequence
   *
   * @param enabled true starts homing, false aborts it
   */
  void sendHoming(bool enabled = true) {
    checkHandle();
    auto result = prohand_send_homing(handle_, enabled ? 1 : 0);
    checkResult(result, "sendHoming");
  }

  /**
   * Try to receive the next status message (non-blocking)
   *
   * Covers every message kind the firmware publishes. Switch on `kind` and read
   * only the matching payload arm:
   *
   *   if (auto msg = client.tryRecvMessage()) {
   *     switch (msg->kind) {
   *       case PROHAND_MSG_ROTARY_GRP_STATUS:
   *         use(msg->payload.rotary_status.servos);   // encoder counts
   *         break;
   *       case PROHAND_MSG_ROTARY_GRP_TARGET:
   *         use(msg->payload.rotary_target.commands); // commanded counts
   *         break;
   *       case PROHAND_MSG_ALERT:
   *         warn(msg->payload.alert);
   *         break;
   *     }
   *   }
   *
   * @return ProHandMessage if available, nullopt otherwise
   */
  std::optional<ProHandMessage> tryRecvMessage() {
    checkHandle();

    ProHandMessage message;
    int result = prohand_try_recv_message(handle_, &message);

    if (result > 0) {
      return message;
    } else if (result == 0) {
      return std::nullopt;
    } else {
      checkResult(result, "tryRecvMessage");
      return std::nullopt; // Unreachable
    }
  }

  /**
   * Try to receive status (non-blocking) — rotary/linear positions and targets
   * only, in raw wire units. Prefer tryRecvMessage().
   *
   * @return HandStatus if available, nullopt otherwise
   */
  std::optional<HandStatus> tryRecvStatus() {
    checkHandle();

    ProHandStatusInfo statusInfo;
    int result = prohand_try_recv_status(handle_, &statusInfo);

    if (result > 0) {
      HandStatus status;
      status.isValid = statusInfo.is_valid != 0;
      status.statusType = statusInfo.status_type;
      status.rotaryPositions.assign(statusInfo.rotary_positions,
                                    statusInfo.rotary_positions + 16);
      status.linearPositions.assign(statusInfo.linear_positions,
                                    statusInfo.linear_positions + 2);
      status.rotaryTargets.assign(statusInfo.rotary_targets,
                                  statusInfo.rotary_targets + 16);
      status.linearTargets.assign(statusInfo.linear_targets,
                                  statusInfo.linear_targets + 2);
      return status;
    } else if (result == 0) {
      return std::nullopt;
    } else {
      checkResult(result, "tryRecvStatus");
      return std::nullopt; // Unreachable
    }
  }

  /**
   * Discover USB devices (static method)
   */
  static std::vector<UsbDevice> discoverUsbDevices() {
    ProHandUsbDeviceInfo devices[10];
    int count = prohand_discover_usb_devices(devices, 10);

    if (count < 0) {
      throw SdkException("USB discovery failed");
    }

    std::vector<UsbDevice> result;
    for (int i = 0; i < count; ++i) {
      UsbDevice dev;
      if (devices[i].port_name) {
        dev.portName = devices[i].port_name;
        prohand_free_string(const_cast<char *>(devices[i].port_name));
      }
      if (devices[i].display_name) {
        dev.displayName = devices[i].display_name;
        prohand_free_string(const_cast<char *>(devices[i].display_name));
      }
      result.push_back(std::move(dev));
    }

    return result;
  }

  /**
   * Get SDK version
   */
  static std::string getVersion() {
    const char *ver = prohand_get_version();
    return ver ? std::string(ver) : "unknown";
  }

private:
  /// Raw int16 centidegrees (0.01 deg per count) -> radians.
  static std::vector<float> toRadians(const int16_t *raw, size_t count) {
    constexpr float kCentidegToRad = 3.14159265358979323846f / 18000.0f;
    std::vector<float> out(count);
    for (size_t i = 0; i < count; ++i) {
      out[i] = static_cast<float>(raw[i]) * kCentidegToRad;
    }
    return out;
  }

  void checkHandle() const {
    if (!handle_) {
      throw SdkException("Client handle is null");
    }
  }

  void checkResult(int result, const std::string &operation) const {
    if (result == PROHAND_SUCCESS) {
      return;
    }

    std::string error = operation + " failed: ";
    switch (result) {
    case PROHAND_ERROR_NULL:
      error += "Null pointer error";
      break;
    case PROHAND_ERROR_CONNECTION:
      error += "Connection error";
      break;
    case PROHAND_ERROR_INVALID_ARGUMENT:
      error += "Invalid argument";
      break;
    case PROHAND_ERROR_NOT_CONNECTED:
      error += "Not connected";
      break;
    default:
      error += "Unknown error (" + std::to_string(result) + ")";
      break;
    }
    throw SdkException(error);
  }
};

} // namespace prohand_sdk
