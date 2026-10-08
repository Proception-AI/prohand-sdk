/**
 * ProHand SDK FFI Demo: Test Hand - Test Each Joint
 *
 * Tests each joint of each finger individually with cyclic motion.
 */

#include <chrono>
#include <cmath>
#include <cxxopts.hpp>
#include <iostream>
#include <thread>

#include "prohand_demo/Utils.hpp"
#include <prohand_sdk/ProHandClient.hpp>

using namespace prohand_sdk;
using namespace prohand_demo; // For utils namespace

int main(int argc, char **argv) {
  cxxopts::Options options("test_hand",
                           "Test each joint of each finger individually");

  options.add_options()("command-endpoint", "ZMQ command endpoint",
                        cxxopts::value<std::string>()->default_value(
                            "ipc:///tmp/prohand-commands.ipc"))(
      "status-endpoint", "ZMQ status endpoint",
      cxxopts::value<std::string>()->default_value(
          "ipc:///tmp/prohand-status.ipc"))(
      "hand-streaming-endpoint", "ZMQ hand streaming endpoint",
      cxxopts::value<std::string>()->default_value(
          "ipc:///tmp/prohand-hand-streaming.ipc"))(
      "wrist-streaming-endpoint", "ZMQ wrist streaming endpoint",
      cxxopts::value<std::string>()->default_value(
          "ipc:///tmp/prohand-wrist-streaming.ipc"))(
      "d,delay", "Delay between movements (seconds)",
      cxxopts::value<double>()->default_value("0.2"))(
      "c,cycles", "Number of cycles per joint",
      cxxopts::value<int>()->default_value("5"))("h,help", "Print usage");

  auto result = options.parse(argc, argv);

  if (result.count("help")) {
    std::cout << options.help() << std::endl;
    return 0;
  }

  auto commandEndpoint = result["command-endpoint"].as<std::string>();
  auto statusEndpoint = result["status-endpoint"].as<std::string>();
  auto handStreamingEndpoint =
      result["hand-streaming-endpoint"].as<std::string>();
  auto wristStreamingEndpoint =
      result["wrist-streaming-endpoint"].as<std::string>();
  auto delay = result["delay"].as<double>();
  auto cycles = result["cycles"].as<int>();

  utils::printBanner("ProHand Test Hand - Individual Joint Testing");

  std::cout << "\nTest parameters:\n";
  std::cout << "  Delay between moves: " << delay << "s\n";
  std::cout << "  Cycles per joint: " << cycles << "\n";
  std::cout << "  Command endpoint: " << commandEndpoint << "\n";
  std::cout << "  Status endpoint: " << statusEndpoint << "\n";

  try {
    utils::printSection("Connecting to IPC host with streaming...");
    ProHandClient client(commandEndpoint, statusEndpoint, handStreamingEndpoint,
                         wristStreamingEndpoint);
    utils::printSuccess("Connected with streaming support!");

    // Verify connection with a ping
    utils::printSection("Verifying connection...");
    client.sendPing();
    std::this_thread::sleep_for(std::chrono::milliseconds(200));
    utils::printSuccess("Connection verified!");

    // Enable streaming mode on the driver
    utils::printSection("Enabling streaming mode...");
    utils::printInfo("Telling driver to accept streaming commands...");
    client.setStreamingMode(true);

    // Wait for streaming connection to be established (with verification)
    utils::printInfo("Waiting for streaming connection to be ready...");
    if (!client.waitForStreamingReady(5.0)) {
      utils::printError("Streaming connection failed to establish!");
      utils::printInfo("This may happen if the driver is busy or under load.");
      utils::printInfo("Try running the demo again.");
      client.setStreamingMode(false);
      return 1;
    }

    utils::printSuccess(
        "Streaming mode enabled! Commands will use streaming socket.");

    const std::vector<std::string> fingers = {"thumb", "index", "middle",
                                              "ring", "pinky"};
    const std::vector<std::string> jointNames = {"metacarpal", "proximal",
                                                 "intermediate", "distal"};

    // Zero all fingers initially (use streaming mode)
    utils::printSection("Zeroing all fingers...");
    std::vector<float> zeroPositions(20, 0.0f);     // 5 fingers × 4 joints
    std::vector<float> zeroWristPositions(2, 0.0f); // 2 wrist joints
    client.sendHandStreams(zeroPositions, 0.45f);
    client.sendWristStreams(zeroWristPositions);
    std::this_thread::sleep_for(std::chrono::seconds(1));

    // Test each joint of each finger
    // Joint layout: thumb[0-3], index[4-7], middle[8-11], ring[12-15],
    // pinky[16-19]
    for (size_t fingerIdx = 0; fingerIdx < fingers.size(); ++fingerIdx) {
      for (int j = 0; j < 4; ++j) {
        int jointIdx = fingerIdx * 4 + j;
        utils::printSection(fingers[fingerIdx] + " - " + jointNames[j] +
                            " (joint " + std::to_string(jointIdx) + ")");

        // Determine range based on joint and finger
        float minDeg =
            (j == 0 && fingers[fingerIdx] != "thumb") ? -30.0f : 0.0f;
        float maxDeg =
            (j == 0 && fingers[fingerIdx] != "thumb") ? 30.0f : 90.0f;

        float minRad = minDeg * M_PI / 180.0f;
        float maxRad = maxDeg * M_PI / 180.0f;

        // Run cycles (use streaming for high-frequency commands)
        for (int cycle = 0; cycle < cycles; ++cycle) {
          // Start with all zero (20 positions: 5 fingers × 4 joints)
          std::vector<float> positions(20, 0.0f);

          // For distal joint (j==3), pre-flex intermediate
          if (j == 3 && fingers[fingerIdx] != "thumb") {
            positions[jointIdx - 1] =
                90.0f * M_PI / 180.0f; // intermediate joint
          }

          // Move to max position (use streaming for high-frequency control)
          positions[jointIdx] = maxRad;
          client.sendHandStreams(positions, 0.45f);
          client.sendWristStreams(zeroWristPositions);
          std::this_thread::sleep_for(std::chrono::duration<double>(delay));

          // Move to min position
          positions[jointIdx] = minRad;
          client.sendHandStreams(positions, 0.45f);
          client.sendWristStreams(zeroWristPositions);
          std::this_thread::sleep_for(std::chrono::duration<double>(delay));
        }
      }
    }

    // Return to zero (use streaming mode)
    utils::printSection("Returning to zero position...");
    client.sendHandStreams(zeroPositions, 0.45f);
    client.sendWristStreams(zeroWristPositions);
    std::this_thread::sleep_for(std::chrono::milliseconds(500));

    // Disable streaming mode
    utils::printSection("Disabling streaming mode...");
    client.setStreamingMode(false);
    std::this_thread::sleep_for(std::chrono::milliseconds(200));

    utils::printSuccess("Test hand demo completed!");
    return 0;

  } catch (const SdkException &e) {
    utils::printError(std::string("Demo failed: ") + e.what());
    std::cout << "\nMake sure prohand-headless-ipc-host is running\n";
    return 1;
  } catch (const std::exception &e) {
    utils::printError(std::string("Unexpected error: ") + e.what());
    return 1;
  }
}
