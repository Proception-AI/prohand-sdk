#include "prohand_client/prohand_client.hpp"

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstring>
#include <stdexcept>

#include <capnp/serialize-packed.h>
#include <kj/array.h>

namespace prohand_client {

namespace {

constexpr double kPi = 3.14159265358979323846;

Bytes packed(capnp::MallocMessageBuilder &message) {
  kj::VectorOutputStream out;
  capnp::writePackedMessage(out, message);
  auto bytes = out.getArray();
  return Bytes(bytes.begin(), bytes.end());
}

int16_t clampI16(double value) {
  return static_cast<int16_t>(
      std::max(-32768.0, std::min(32767.0, std::round(value))));
}

// Joint angle in centi-degrees, the CompactJointState.scaledPosition unit,
// clamped to the i16 range and never wrapped.
int16_t scaledPosition(double radians) {
  return clampI16(radians * 180.0 / kPi * 100.0);
}

// [-1, 1] onto the full i16 range, the normalizedVelOrTau unit.
int16_t normalized(double value) {
  return clampI16(std::max(-1.0, std::min(1.0, value)) * 32767.0);
}

uint16_t nextUid() {
  static std::atomic<uint16_t> uid{0};
  return ++uid;
}

uint16_t timestampMsNow() {
  using namespace std::chrono;
  return static_cast<uint16_t>(
      duration_cast<milliseconds>(steady_clock::now().time_since_epoch())
          .count() &
      0xFFFF);
}

int64_t nowMs() {
  using namespace std::chrono;
  return duration_cast<milliseconds>(steady_clock::now().time_since_epoch())
      .count();
}

zmq::message_t toMessage(const Bytes &payload) {
  zmq::message_t msg(payload.size());
  std::memcpy(msg.data(), payload.data(), payload.size());
  return msg;
}

} // namespace

// ── Encoding ──────────────────────────────────────────────────────────────

Bytes encodePing() {
  capnp::MallocMessageBuilder message;
  message.initRoot<::ProHandCommand>().setPing();
  return packed(message);
}

Bytes encodeStreamingMode(bool enabled) {
  capnp::MallocMessageBuilder message;
  auto mode = message.initRoot<::ProHandCommand>()
                  .initHandRequest()
                  .initStreamingMode();
  if (enabled) {
    mode.setOnDemand();
  } else {
    mode.setOff();
  }
  return packed(message);
}

Bytes encodeStreamingModeContinuous(::SpaceFilter spaceFilter) {
  capnp::MallocMessageBuilder message;
  message.initRoot<::ProHandCommand>()
      .initHandRequest()
      .initStreamingMode()
      .setContinuous(spaceFilter);
  return packed(message);
}

Bytes encodeZeroCalibration(std::optional<int> motorId) {
  capnp::MallocMessageBuilder message;
  auto calib =
      message.initRoot<::ProHandCommand>().initHandRequest().initZeroCalib(16);
  for (int i = 0; i < 16; ++i) {
    calib.set(i, !motorId.has_value() || *motorId == i);
  }
  return packed(message);
}

Bytes encodeHoming(bool start) {
  capnp::MallocMessageBuilder message;
  message.initRoot<::ProHandCommand>().initHandRequest().setHoming(start);
  return packed(message);
}

Bytes encodeRotaryCommand(const std::vector<int> &positions,
                          const std::vector<int> &torques,
                          const std::vector<int> &velocities) {
  if (positions.size() != 16 || torques.size() != 16) {
    throw std::invalid_argument("exactly 16 positions and 16 torques");
  }
  if (!velocities.empty() && velocities.size() != 16) {
    throw std::invalid_argument("exactly 16 velocities");
  }
  capnp::MallocMessageBuilder message;
  auto servos = message.initRoot<::ProHandCommand>().initRotaryGrpCommand(16);
  for (int i = 0; i < 16; ++i) {
    auto servo = servos[i];
    servo.setPosition(static_cast<int16_t>(positions[i]));
    servo.setTorque(static_cast<uint16_t>(torques[i]));
    servo.setVelocity(static_cast<uint8_t>(
        velocities.empty() ? kDefaultRotaryVelocity : velocities[i]));
  }
  return packed(message);
}

Bytes encodeLinearCommand(const std::vector<int> &positions,
                          const std::vector<int> &speeds) {
  if (positions.size() != 2 || speeds.size() != 2) {
    throw std::invalid_argument("exactly 2 positions and 2 speeds");
  }
  capnp::MallocMessageBuilder message;
  auto actuators = message.initRoot<::ProHandCommand>().initLinearGrpCommand(2);
  for (int i = 0; i < 2; ++i) {
    auto actuator = actuators[i];
    actuator.setPosition(static_cast<int16_t>(positions[i]));
    actuator.setSpeed(static_cast<uint16_t>(speeds[i]));
  }
  return packed(message);
}

Bytes encodeHandCommand(const FingerPose &pose, bool degrees, double torque,
                        double velocitySaturation, std::optional<uint16_t> uid,
                        std::optional<uint16_t> timestampMs) {
  capnp::MallocMessageBuilder message;
  auto hand = message.initRoot<::ProHandCommand>().initHandStateCommand();
  hand.setTimestamp(timestampMs.value_or(timestampMsNow()));
  hand.setUid(uid.value_or(nextUid()));
  const double saturation = std::max(0.0, std::min(1.0, velocitySaturation));
  hand.setVelocitySaturation(
      static_cast<uint8_t>(std::round(saturation * 255.0)));
  const int16_t level = normalized(torque);
  auto fill = [&](auto joints, const char *finger) {
    const auto found = pose.find(finger);
    const std::vector<double> none;
    const auto &angles = found == pose.end() ? none : found->second;
    for (size_t i = 0; i < 4; ++i) {
      double angle = i < angles.size() ? angles[i] : 0.0;
      if (degrees) {
        angle = angle * kPi / 180.0;
      }
      auto joint = joints[static_cast<unsigned>(i)];
      joint.setScaledPosition(scaledPosition(angle));
      joint.setNormalizedVelOrTau(level);
    }
  };
  fill(hand.initThumb(4), kFingers[0]);
  fill(hand.initIndex(4), kFingers[1]);
  fill(hand.initMiddle(4), kFingers[2]);
  fill(hand.initRing(4), kFingers[3]);
  fill(hand.initPinky(4), kFingers[4]);
  return packed(message);
}

Bytes encodeWristCommand(const std::vector<double> &positions,
                         const std::vector<double> &velocityNorm, bool degrees,
                         std::optional<uint16_t> uid,
                         std::optional<uint16_t> timestampMs) {
  if (positions.size() != 2 || velocityNorm.size() != 2) {
    throw std::invalid_argument("exactly 2 positions and 2 velocities");
  }
  capnp::MallocMessageBuilder message;
  auto wrist = message.initRoot<::ProHandCommand>().initWristStateCommand();
  wrist.setTimestamp(timestampMs.value_or(timestampMsNow()));
  wrist.setUid(uid.value_or(nextUid()));
  auto joints = wrist.initWrist(2);
  for (size_t i = 0; i < 2; ++i) {
    double angle = positions[i];
    if (degrees) {
      angle = angle * kPi / 180.0;
    }
    auto joint = joints[static_cast<unsigned>(i)];
    joint.setScaledPosition(scaledPosition(angle));
    joint.setNormalizedVelOrTau(normalized(velocityNorm[i]));
  }
  return packed(message);
}

// ── Decoding ──────────────────────────────────────────────────────────────

::ProHandStatus::Reader Status::body() const {
  return message_->getRoot<::ProHandStatus>().asReader();
}

Status parseStatusMessage(const uint8_t *data, size_t size) {
  kj::ArrayInputStream input(
      kj::arrayPtr(reinterpret_cast<const kj::byte *>(data), size));
  capnp::PackedMessageReader reader(input);
  Status status;
  status.message_ = std::make_unique<capnp::MallocMessageBuilder>();
  status.message_->setRoot(reader.getRoot<::ProHandStatus>());
  auto root = status.body();
  if (root.hasHeader()) {
    auto header = root.getHeader();
    auto stamp = header.getStamp();
    status.header.tDeviceUs = stamp.getTDeviceUs();
    if (stamp.getFrame().isTick()) {
      status.header.tick = stamp.getFrame().getTick();
    }
    status.header.seq = header.getSeq();
    status.header.boot = header.getBoot();
    status.header.dropped = header.getDropped();
    status.header.sync = header.getSync();
  }
  if (root.getTHostUs() != 0) {
    status.tHostUs = root.getTHostUs();
  }
  return status;
}

// ── ServiceClient ─────────────────────────────────────────────────────────

ServiceClient::ServiceClient(std::string commandEndpoint)
    : context_(1), endpoint_(std::move(commandEndpoint)) {}

ServiceClient::~ServiceClient() { disconnect(); }

void ServiceClient::connect() { open(); }

void ServiceClient::open() {
  sock_ = std::make_unique<zmq::socket_t>(context_, zmq::socket_type::req);
  sock_->set(zmq::sockopt::linger, 0);
  sock_->connect(endpoint_);
}

void ServiceClient::disconnect() { sock_.reset(); }

std::optional<Bytes> ServiceClient::request(const Bytes &payload,
                                            int timeoutMs) {
  if (!sock_) {
    open();
  }
  sock_->send(toMessage(payload), zmq::send_flags::none);
  sock_->set(zmq::sockopt::rcvtimeo, timeoutMs);
  zmq::message_t reply;
  if (!sock_->recv(reply, zmq::recv_flags::none).has_value()) {
    open();
    return std::nullopt;
  }
  const auto *bytes = static_cast<const uint8_t *>(reply.data());
  return Bytes(bytes, bytes + reply.size());
}

bool ServiceClient::ping(int timeoutMs) {
  return request(encodePing(), timeoutMs).has_value();
}

bool ServiceClient::setStreamingMode(bool enabled, int timeoutMs) {
  return request(encodeStreamingMode(enabled), timeoutMs).has_value();
}

bool ServiceClient::setStreamingModeContinuous(::SpaceFilter spaceFilter,
                                               int timeoutMs) {
  return request(encodeStreamingModeContinuous(spaceFilter), timeoutMs)
      .has_value();
}

bool ServiceClient::zeroCalibration(std::optional<int> motorId, int timeoutMs) {
  return request(encodeZeroCalibration(motorId), timeoutMs).has_value();
}

bool ServiceClient::homing(bool start, int timeoutMs) {
  return request(encodeHoming(start), timeoutMs).has_value();
}

// ── Publisher ─────────────────────────────────────────────────────────────

Publisher::Publisher(std::string handStreamingEndpoint,
                     std::string wristStreamingEndpoint)
    : context_(1), handEndpoint_(std::move(handStreamingEndpoint)),
      wristEndpoint_(std::move(wristStreamingEndpoint)) {}

Publisher::~Publisher() { disconnect(); }

void Publisher::connect() {
  hand_ = open(handEndpoint_);
  wrist_ = open(wristEndpoint_);
}

std::unique_ptr<zmq::socket_t> Publisher::open(const std::string &endpoint) {
  auto sock = std::make_unique<zmq::socket_t>(context_, zmq::socket_type::pub);
  sock->set(zmq::sockopt::linger, 0);
  sock->set(zmq::sockopt::conflate, 1);
  sock->connect(endpoint);
  return sock;
}

void Publisher::disconnect() {
  hand_.reset();
  wrist_.reset();
}

void Publisher::send(zmq::socket_t *sock, const Bytes &payload) {
  if (!sock) {
    throw std::runtime_error("publisher not connected");
  }
  sock->send(toMessage(payload), zmq::send_flags::dontwait);
}

void Publisher::sendRotaryCommand(const std::vector<int> &positions,
                                  const std::vector<int> &torques,
                                  const std::vector<int> &velocities) {
  send(hand_.get(), encodeRotaryCommand(positions, torques, velocities));
}

void Publisher::sendLinearCommand(const std::vector<int> &positions,
                                  const std::vector<int> &speeds) {
  send(wrist_.get(), encodeLinearCommand(positions, speeds));
}

void Publisher::sendHandCommand(const FingerPose &pose, bool degrees,
                                double torque, double velocitySaturation) {
  send(hand_.get(),
       encodeHandCommand(pose, degrees, torque, velocitySaturation));
}

void Publisher::sendWristCommand(const std::vector<double> &positions,
                                 const std::vector<double> &velocityNorm,
                                 bool degrees) {
  send(wrist_.get(), encodeWristCommand(positions, velocityNorm, degrees));
}

// ── Subscriber ────────────────────────────────────────────────────────────

Subscriber::Subscriber(std::string statusEndpoint, int receiveHwm,
                       int reconnectAfterMs)
    : context_(1), endpoint_(std::move(statusEndpoint)),
      receiveHwm_(receiveHwm), reconnectAfterMs_(reconnectAfterMs) {}

Subscriber::~Subscriber() { disconnect(); }

void Subscriber::connect() { open(); }

void Subscriber::open() {
  sock_ = std::make_unique<zmq::socket_t>(context_, zmq::socket_type::sub);
  sock_->set(zmq::sockopt::rcvhwm, receiveHwm_);
  sock_->connect(endpoint_);
  sock_->set(zmq::sockopt::subscribe, "");
  lastFrameAtMs_ = nowMs();
}

void Subscriber::disconnect() { sock_.reset(); }

std::optional<Status> Subscriber::receive(int timeoutMs) {
  if (!sock_) {
    open();
  }
  sock_->set(zmq::sockopt::rcvtimeo, timeoutMs);
  zmq::message_t msg;
  if (!sock_->recv(msg, zmq::recv_flags::none).has_value()) {
    if (nowMs() - lastFrameAtMs_ > reconnectAfterMs_) {
      open();
    }
    return std::nullopt;
  }
  lastFrameAtMs_ = nowMs();
  return parseStatusMessage(static_cast<const uint8_t *>(msg.data()),
                            msg.size());
}

} // namespace prohand_client
