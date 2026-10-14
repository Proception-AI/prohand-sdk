// The wire contract against the fixtures the other sides wrote.
//
// status_frames.bin: every public status variant as the driver's own encoder
// (prohand-capnp, internal edition) writes it; this client must decode each,
// header and host time included.
//
// command_frames.bin: every command the Python reference client builds, in
// the order its tests define. This client's encoders must produce the same
// bytes for the same inputs, and decode each record to the expected variant.
//
// Both files are a sequence of (u32 little-endian length, bytes) records.
//
//   decode_fixtures <fixtures dir>

#include <cstdint>
#include <cstring>
#include <fstream>
#include <iostream>
#include <iterator>
#include <string>
#include <vector>

#include <capnp/serialize-packed.h>
#include <kj/array.h>

#include "prohand_client/prohand_client.hpp"

namespace {

using prohand_client::Bytes;

int failures = 0;

void check(bool ok, const std::string &what) {
  if (!ok) {
    ++failures;
    std::cerr << "FAIL: " << what << "\n";
  }
}

std::vector<Bytes> readRecords(const std::string &path) {
  std::ifstream file(path, std::ios::binary);
  if (!file) {
    std::cerr << "cannot open " << path << "\n";
    std::exit(2);
  }
  Bytes data((std::istreambuf_iterator<char>(file)),
             std::istreambuf_iterator<char>());
  std::vector<Bytes> records;
  size_t pos = 0;
  while (pos + 4 <= data.size()) {
    uint32_t length = 0;
    std::memcpy(&length, data.data() + pos, 4);
    pos += 4;
    records.emplace_back(data.begin() + pos, data.begin() + pos + length);
    pos += length;
  }
  return records;
}

const ::ProHandStatus::Which kStatusVariants[] = {
    ::ProHandStatus::PONG,
    ::ProHandStatus::HAND_REQUEST_ECHO,
    ::ProHandStatus::ROTARY_STATE,
    ::ProHandStatus::LINEAR_STATE,
    ::ProHandStatus::HAND_STATE,
    ::ProHandStatus::ROTARY_GRP_STATUS,
    ::ProHandStatus::LINEAR_GRP_STATUS,
    ::ProHandStatus::ROTARY_GRP_TARGET,
    ::ProHandStatus::LINEAR_GRP_TARGET,
    ::ProHandStatus::HANDEDNESS,
    ::ProHandStatus::IMU_STATUS,
    ::ProHandStatus::IMU_STATE,
    ::ProHandStatus::TIME_SYNC_ACK,
    ::ProHandStatus::ALERT,
    ::ProHandStatus::CURRENT_SENSE_STATUS,
    ::ProHandStatus::CURRENT_SENSE_STATE,
    ::ProHandStatus::HAND_JOINT_TARGET,
    ::ProHandStatus::WRIST_JOINT_TARGET,
    ::ProHandStatus::HAND_JOINT_STATUS,
    ::ProHandStatus::WRIST_JOINT_STATUS,
    ::ProHandStatus::HAND_OBSERVED_STATE,
    ::ProHandStatus::HAND_HEALTH,
    ::ProHandStatus::SYNC_STATUS,
};

void checkStatusFixture(const std::string &dir) {
  const auto frames = readRecords(dir + "/status_frames.bin");
  check(frames.size() == std::size(kStatusVariants),
        "status fixture holds every public variant");
  for (size_t i = 0; i < frames.size() && i < std::size(kStatusVariants); ++i) {
    const auto status = prohand_client::parseStatusMessage(frames[i]);
    const std::string tag = "status #" + std::to_string(i);
    check(status.which() == kStatusVariants[i],
          tag + " decodes as its variant");
    check(status.header.seq == i, tag + " seq");
    check(status.header.tDeviceUs == 1000 + i, tag + " device time");
    check(status.header.tick.has_value() && *status.header.tick == 7,
          tag + " tick");
    check(status.header.boot == 3 && status.header.dropped == 1 &&
              status.header.sync == 2,
          tag + " boot/dropped/sync");
    check(status.tHostUs.has_value() && *status.tHostUs == 2000 + i,
          tag + " host time");
  }
}

// Mirrors tests/test_contract.py::command_frames, inputs and order.
std::vector<Bytes> ownCommandFrames() {
  using namespace prohand_client;
  std::vector<int> positions(16);
  for (int i = 0; i < 16; ++i) {
    positions[i] = i * 10;
  }
  FingerPose pose;
  for (const char *finger : kFingers) {
    pose[finger] = {0.1, 0.2, 0.3, 0.4};
  }
  return {
      encodePing(),
      encodeStreamingMode(false),
      encodeStreamingMode(true),
      encodeStreamingModeContinuous(::SpaceFilter::JOINT_SPACE),
      encodeZeroCalibration(),
      encodeZeroCalibration(3),
      encodeHoming(true),
      encodeRotaryCommand(positions, std::vector<int>(16, 100)),
      encodeLinearCommand({1, 2}, {3, 4}),
      encodeHandCommand(pose, false, 0.5, 0.5, uint16_t{7}, uint16_t{9}),
      encodeWristCommand({0.1, -0.1}, {0.5, 1.0}, false, uint16_t{8},
                         uint16_t{10}),
      encodeHandCommand(
          {{"thumb", {0.3, 0.5, 3.2, -3.2}}, {"index", {1.0, -1.0, 0.0, 0.3}}},
          false, 0.3, 0.3, uint16_t{11}, uint16_t{12}),
      encodeWristCommand({3.2, -3.2}, {0.5, 0.3}, false, uint16_t{13},
                         uint16_t{14}),
  };
}

const ::ProHandCommand::Which kCommandVariants[] = {
    ::ProHandCommand::PING,
    ::ProHandCommand::HAND_REQUEST,
    ::ProHandCommand::HAND_REQUEST,
    ::ProHandCommand::HAND_REQUEST,
    ::ProHandCommand::HAND_REQUEST,
    ::ProHandCommand::HAND_REQUEST,
    ::ProHandCommand::HAND_REQUEST,
    ::ProHandCommand::ROTARY_GRP_COMMAND,
    ::ProHandCommand::LINEAR_GRP_COMMAND,
    ::ProHandCommand::HAND_STATE_COMMAND,
    ::ProHandCommand::WRIST_STATE_COMMAND,
    ::ProHandCommand::HAND_STATE_COMMAND,
    ::ProHandCommand::WRIST_STATE_COMMAND,
};

void checkCommandFixture(const std::string &dir) {
  const auto frames = readRecords(dir + "/command_frames.bin");
  const auto own = ownCommandFrames();
  check(frames.size() == own.size(),
        "command fixture holds every command this client builds");
  for (size_t i = 0; i < frames.size() && i < own.size(); ++i) {
    const std::string tag = "command #" + std::to_string(i);
    check(frames[i] == own[i],
          tag + " encodes to the same bytes as the Python client");
    kj::ArrayInputStream input(
        kj::arrayPtr(reinterpret_cast<const kj::byte *>(frames[i].data()),
                     frames[i].size()));
    capnp::PackedMessageReader reader(input);
    auto command = reader.getRoot<::ProHandCommand>();
    check(command.which() == kCommandVariants[i],
          tag + " decodes as its variant");
  }
}

} // namespace

int main(int argc, char **argv) {
  if (argc != 2) {
    std::cerr << "usage: decode_fixtures <fixtures dir>\n";
    return 2;
  }
  checkStatusFixture(argv[1]);
  checkCommandFixture(argv[1]);
  if (failures == 0) {
    std::cout << "prohand C++ reference client: wire contract OK\n";
  }
  return failures == 0 ? 0 : 1;
}
