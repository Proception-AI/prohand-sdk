// ProHand protocol reference client.
//
// The wire contract, and nothing else: packed Cap'n Proto messages from the
// public schema over ZeroMQ. Three classes, one per role (ServiceClient for
// request/reply commands, Publisher for streamed setpoints, Subscriber for
// the status stream), and a plain encode* function per message so a program
// can bring its own transport.
#pragma once

#include <cstdint>
#include <map>
#include <memory>
#include <optional>
#include <string>
#include <vector>

#include <capnp/message.h>
#include <zmq.hpp>

#include "prohand_sdk.capnp.h"

namespace prohand_client {

// The servo Running Speed register reads 0 as stop, so an unset velocity
// holds the hand still. 50 is the fleet default every other producer uses.
inline constexpr int kDefaultRotaryVelocity = 50;

// A SUB socket never learns that its publisher went away; after this much
// silence the subscriber reopens its socket.
inline constexpr int kDefaultReconnectAfterMs = 5000;

inline constexpr const char *kFingers[5] = {"thumb", "index", "middle", "ring",
                                            "pinky"};

// Finger name to four joint angles. A missing finger or joint reads as zero.
using FingerPose = std::map<std::string, std::vector<double>>;

using Bytes = std::vector<uint8_t>;

// ── Encoding ──────────────────────────────────────────────────────────────

Bytes encodePing();
// true is on-demand streaming (one echo per accepted command), false is off.
Bytes encodeStreamingMode(bool enabled);
// Continuous streaming: the firmware re-emits the cached joint targets every
// control tick and admits only commands inside `spaceFilter`.
Bytes encodeStreamingModeContinuous(
    ::SpaceFilter spaceFilter = ::SpaceFilter::JOINT_SPACE);
// Zero calibration of one rotary servo, or of all sixteen.
Bytes encodeZeroCalibration(std::optional<int> motorId = std::nullopt);
// Start or abort the firmware's homing sequence. Not zero calibration.
Bytes encodeHoming(bool start = true);
// Sixteen servo setpoints. `velocities` caps each servo's speed and must be
// non-zero to move; empty applies the fleet default to every servo.
Bytes encodeRotaryCommand(const std::vector<int> &positions,
                          const std::vector<int> &torques,
                          const std::vector<int> &velocities = {});
// Two wrist actuator setpoints.
Bytes encodeLinearCommand(const std::vector<int> &positions,
                          const std::vector<int> &speeds);
// Finger joint targets in radians (degrees with `degrees`), one normalised
// torque level for every finger, and the global speed cap in [0, 1]; the
// wire default of zero does not move. Wire integers follow the rule every
// reference client shares: clamp to the field's range, never wrap an angle,
// round half away from zero. `uid` and `timestampMs` come from a
// counter and the monotonic clock when not given.
Bytes encodeHandCommand(const FingerPose &pose, bool degrees = false,
                        double torque = 0.45, double velocitySaturation = 1.0,
                        std::optional<uint16_t> uid = std::nullopt,
                        std::optional<uint16_t> timestampMs = std::nullopt);
// Two wrist joint targets with a normalised velocity each; exactly two of each.
Bytes encodeWristCommand(const std::vector<double> &positions,
                         const std::vector<double> &velocityNorm,
                         bool degrees = false,
                         std::optional<uint16_t> uid = std::nullopt,
                         std::optional<uint16_t> timestampMs = std::nullopt);

// ── Decoding ──────────────────────────────────────────────────────────────

// What every status frame carries beside its body: the device clock, the
// control tick the stamp was taken in (none when unbound), the sequence
// counter, the boot count, frames dropped before this one and the clock-sync
// epoch.
struct Header {
  uint64_t tDeviceUs{0};
  std::optional<uint32_t> tick;
  uint32_t seq{0};
  uint16_t boot{0};
  uint8_t dropped{0};
  uint8_t sync{0};
};

// One status frame. `tHostUs` is the device clock mapped onto the host's,
// filled by the driver once the clocks are synchronised. `body()` is the
// Cap'n Proto reader; pick the variant with `which()`.
class Status {
public:
  Header header;
  std::optional<uint64_t> tHostUs;

  ::ProHandStatus::Reader body() const;
  ::ProHandStatus::Which which() const { return body().which(); }

private:
  friend Status parseStatusMessage(const uint8_t *data, size_t size);
  std::unique_ptr<capnp::MallocMessageBuilder> message_;
};

Status parseStatusMessage(const uint8_t *data, size_t size);
inline Status parseStatusMessage(const Bytes &bytes) {
  return parseStatusMessage(bytes.data(), bytes.size());
}

// ── Transport ─────────────────────────────────────────────────────────────

// Request/reply commands. A request the driver does not answer within the
// timeout returns false and reopens the socket, since a REQ socket that is
// waiting for a reply accepts no further request.
class ServiceClient {
public:
  explicit ServiceClient(std::string commandEndpoint);
  ~ServiceClient();

  void connect();
  void disconnect();

  // Send one command and wait for the reply; nullopt on timeout.
  std::optional<Bytes> request(const Bytes &payload, int timeoutMs = 1000);

  bool ping(int timeoutMs = 1000);
  bool setStreamingMode(bool enabled, int timeoutMs = 1000);
  bool setStreamingModeContinuous(
      ::SpaceFilter spaceFilter = ::SpaceFilter::JOINT_SPACE,
      int timeoutMs = 1000);
  bool zeroCalibration(std::optional<int> motorId = std::nullopt,
                       int timeoutMs = 2000);
  bool homing(bool start = true, int timeoutMs = 2000);

private:
  void open();
  zmq::context_t context_;
  std::unique_ptr<zmq::socket_t> sock_;
  std::string endpoint_;
};

// Streamed commands, newest only: each socket keeps one pending frame
// (CONFLATE), so a driver that stalls receives the latest setpoint when it
// resumes, never a backlog of stale ones. A PUB socket never reports what a
// peer received: a setpoint sent before the driver's subscription completed,
// or superseded before the driver read it, is gone without a trace. Send the
// setpoint on every control pass, after the first status frame arrived.
class Publisher {
public:
  Publisher(std::string handStreamingEndpoint,
            std::string wristStreamingEndpoint);
  ~Publisher();

  void connect();
  void disconnect();

  void sendRotaryCommand(const std::vector<int> &positions,
                         const std::vector<int> &torques,
                         const std::vector<int> &velocities = {});
  void sendLinearCommand(const std::vector<int> &positions,
                         const std::vector<int> &speeds);
  void sendHandCommand(const FingerPose &pose, bool degrees = false,
                       double torque = 0.45, double velocitySaturation = 1.0);
  void sendWristCommand(const std::vector<double> &positions,
                        const std::vector<double> &velocityNorm,
                        bool degrees = false);

private:
  std::unique_ptr<zmq::socket_t> open(const std::string &endpoint);
  static void send(zmq::socket_t *sock, const Bytes &payload);
  zmq::context_t context_;
  std::unique_ptr<zmq::socket_t> hand_;
  std::unique_ptr<zmq::socket_t> wrist_;
  std::string handEndpoint_;
  std::string wristEndpoint_;
};

// The status stream. The receive buffer is kept short so a reader that falls
// behind sees recent frames, not a backlog; a socket silent for
// `reconnectAfterMs` is reopened.
class Subscriber {
public:
  explicit Subscriber(std::string statusEndpoint, int receiveHwm = 8,
                      int reconnectAfterMs = kDefaultReconnectAfterMs);
  ~Subscriber();

  void connect();
  void disconnect();

  // The next status frame within `timeoutMs`, else nullopt.
  std::optional<Status> receive(int timeoutMs = 100);
  std::optional<Status> tryReceive() { return receive(0); }

private:
  void open();
  zmq::context_t context_;
  std::unique_ptr<zmq::socket_t> sock_;
  std::string endpoint_;
  int receiveHwm_;
  int reconnectAfterMs_;
  int64_t lastFrameAtMs_{0};
};

} // namespace prohand_client
