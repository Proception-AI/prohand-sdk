// Connect to a running ProHand driver, ping it, turn streaming on, send one
// open-hand command, and print the status frames that come back.
//
//   ./quickstart [tcp://127.0.0.1]
//
// The left hand's default TCP ports: 5562 commands (REQ/REP), 5561 status
// (PUB/SUB), 5563 hand streaming and 5564 wrist streaming (PUB/SUB); the right
// hand's are 5572, 5571, 5573 and 5574.

#include <chrono>
#include <iostream>
#include <string>

#include "prohand_client/prohand_client.hpp"

namespace {

const char *variantName(::ProHandStatus::Which which) {
  switch (which) {
  case ::ProHandStatus::HAND_JOINT_STATUS:
    return "hand joints";
  case ::ProHandStatus::WRIST_JOINT_STATUS:
    return "wrist joints";
  case ::ProHandStatus::HAND_OBSERVED_STATE:
    return "observed state";
  case ::ProHandStatus::ALERT:
    return "alert";
  default:
    return "other";
  }
}

} // namespace

int main(int argc, char **argv) {
  using namespace prohand_client;
  const std::string host = argc > 1 ? argv[1] : "tcp://127.0.0.1";

  ServiceClient service(host + ":5562");
  service.connect();
  if (!service.ping()) {
    std::cerr << "no reply from the driver within 1 s\n";
    return 1;
  }
  std::cout << "driver answered the ping\n";

  Subscriber subscriber(host + ":5561");
  subscriber.connect();
  Publisher publisher(host + ":5563", host + ":5564");
  publisher.connect();

  if (!service.setStreamingMode(true)) {
    std::cerr << "the driver did not acknowledge streaming mode within 1 s\n";
    return 1;
  }
  // The first status frame shows the subscriptions are up; a setpoint sent
  // before that is dropped by the PUB socket. Streaming is a stream: the
  // setpoint goes out on every pass, not once.
  FingerPose open;
  for (const char *finger : kFingers) {
    open[finger] = {0.0, 0.0, 0.0, 0.0};
  }
  const auto until = std::chrono::steady_clock::now() + std::chrono::seconds(3);
  unsigned frames = 0;
  while (std::chrono::steady_clock::now() < until) {
    auto status = subscriber.receive(200);
    if (!status) {
      continue;
    }
    publisher.sendHandCommand(open, false, 0.3);
    ++frames;
    if (frames % 50 == 1) {
      std::cout << "seq " << status->header.seq << " device "
                << status->header.tDeviceUs << " us host "
                << (status->tHostUs ? std::to_string(*status->tHostUs) : "none")
                << " us: " << variantName(status->which()) << "\n";
    }
  }
  std::cout << frames << " status frames in 3 s\n";

  service.setStreamingMode(false);
  return 0;
}
