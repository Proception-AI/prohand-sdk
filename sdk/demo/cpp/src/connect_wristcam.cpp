/**
 * ProWristCam SDK Demo: Basic Connection Test
 *
 * Connects to a prowristcam-headless-ipc-host endpoint, waits for the first
 * JPEG frame, and prints its metadata.
 */

#include <chrono>
#include <cxxopts.hpp>
#include <iostream>
#include <thread>

#include "prowrist_demo/Utils.hpp"
#include <prowrist_sdk/WristCamClient.hpp>

using namespace prowrist_sdk;
using namespace prowrist_demo;

int main(int argc, char **argv) {
  cxxopts::Options options(
      "connect_wristcam",
      "Test connection to a prowristcam-headless-ipc-host endpoint\n\n"
      "Examples:\n"
      "  connect_wristcam --endpoint ipc:///tmp/prowristcam-left-stream.ipc\n"
      "  connect_wristcam --endpoint tcp://192.168.1.82:5565");

  options.add_options()("e,endpoint", "ZeroMQ stream endpoint",
                        cxxopts::value<std::string>()->default_value(
                            "ipc:///tmp/prowristcam-left-stream.ipc"))(
      "h,help", "Print usage");

  auto result = options.parse(argc, argv);

  if (result.count("help")) {
    std::cout << options.help() << std::endl;
    return 0;
  }

  std::string endpoint = result["endpoint"].as<std::string>();

  utils::printBanner("ProWristCam IPC Connection Test");

  std::cout << "\nConnection parameters:\n";
  std::cout << "  Endpoint: " << endpoint << "\n";
  std::cout << "  SDK version: " << WristCamClient::getVersion() << "\n";

  try {
    utils::printSection("Creating client...");
    WristCamClient client(endpoint);
    utils::printSuccess("Client created!");

    utils::printSection("Waiting for first frame (up to 5 s)...");

    auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(5);
    std::optional<WristCamFrame> frame;

    while (std::chrono::steady_clock::now() < deadline) {
      frame = client.tryRecvFrame();
      if (frame) {
        break;
      }
      std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }

    if (frame) {
      utils::printSuccess("Frame received!");
      std::cout << "\nFrame details:\n";
      std::cout << "  uid:       " << frame->uid << "\n";
      std::cout << "  timestamp: " << frame->timestamp << " ms\n";
      std::cout << "  JPEG size: " << frame->jpeg.size() << " bytes\n";
      std::cout << "  Connected: " << (client.isConnected() ? "yes" : "no")
                << "\n";
    } else {
      utils::printWarning("No frame received within 5 s");
      std::cout << "\nMake sure prowristcam-headless-ipc-host is running.\n";
      return 1;
    }

    utils::printSuccess("Connection test completed successfully!");
    return 0;

  } catch (const SdkException &e) {
    utils::printError(std::string("SDK error: ") + e.what());
    std::cout << "\nMake sure prowristcam-headless-ipc-host is running.\n";
    return 1;
  } catch (const std::exception &e) {
    utils::printError(std::string("Unexpected error: ") + e.what());
    return 1;
  }
}
