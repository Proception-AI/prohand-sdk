/**
 * ProHand SDK FFI Demo: Kapandji Opposition Test
 *
 * Run the Kapandji opposition sequence - thumb touches each fingertip.
 */

#include <chrono>
#include <cmath>
#include <cxxopts.hpp>
#include <fstream>
#include <iostream>
#include <map>
#include <string>
#include <thread>
#include <vector>

#include "prohand_demo/Utils.hpp"
#include <prohand_sdk/ProHandClient.hpp>

#ifdef YAML_CPP_FOUND
#include <yaml-cpp/yaml.h>
#endif

using namespace prohand_sdk;
using namespace prohand_demo; // For utils namespace

#ifdef YAML_CPP_FOUND
// Helper to parse joint list from YAML
std::vector<double> parseJointList(const YAML::Node &node, int n,
                                   double fill = 0.0) {
  std::vector<double> out(n, fill);
  if (node && node.IsSequence()) {
    for (int i = 0; i < n && i < static_cast<int>(node.size()); ++i) {
      out[i] =
          node[i].as<double>() * M_PI / 180.0; // Convert degrees to radians
    }
  }
  return out;
}

// Extract pose from YAML configuration
std::map<std::string, std::vector<double>>
poseFromYaml(const std::string &gesture, const std::string &hand,
             const YAML::Node &cfg) {
  auto hands = cfg["hands"];

  if (!hands) {
    throw std::runtime_error("YAML config missing 'hands' section");
  }

  auto g = hands[gesture];
  if (!g) {
    throw std::runtime_error("YAML gesture '" + gesture + "' not found");
  }

  std::map<std::string, std::vector<double>> pose;
  pose["thumb"] = parseJointList(g["thumb"], 4);
  pose["index"] = parseJointList(g["index"], 4);
  pose["middle"] = parseJointList(g["middle"], 4);
  pose["ring"] = parseJointList(g["ring"], 4);
  pose["pinky"] = parseJointList(g["pinky"], 4);

  auto wrist = parseJointList(g["wrist"], 2);
  if (wrist.size() < 2)
    wrist = {0.0, 0.0};
  pose["wrist"] = wrist;

  return pose;
}

// Convert pose dictionary to flat list of 20 joint positions
std::vector<float>
poseToHandPositions(const std::map<std::string, std::vector<double>> &pose) {
  std::vector<float> positions;
  positions.reserve(20);

  // Order: thumb[0-3], index[4-7], middle[8-11], ring[12-15], pinky[16-19]
  const std::vector<std::string> fingerNames = {"thumb", "index", "middle",
                                                "ring", "pinky"};
  for (const auto &finger : fingerNames) {
    auto it = pose.find(finger);
    if (it != pose.end()) {
      for (double val : it->second) {
        positions.push_back(static_cast<float>(val));
      }
    } else {
      positions.insert(positions.end(), 4, 0.0f);
    }
  }

  return positions;
}

// Stream a pose for the specified duration
void streamPose(ProHandClient &client,
                const std::map<std::string, std::vector<double>> &pose,
                double publishHz, double durationS, float torque = 0.45f) {
  double period = 1.0 / std::max(1e-6, publishHz);
  std::vector<float> positions = poseToHandPositions(pose);
  auto wristIt = pose.find("wrist");
  std::vector<float> wristPositions = {0.0f, 0.0f};
  if (wristIt != pose.end()) {
    for (size_t i = 0; i < wristIt->second.size() && i < 2; ++i) {
      wristPositions[i] = static_cast<float>(wristIt->second[i]);
    }
  }

  auto deadline = std::chrono::steady_clock::now() +
                  std::chrono::duration<double>(durationS);

  while (std::chrono::steady_clock::now() < deadline) {
    client.sendWristStreams(wristPositions);
    client.sendHandStreams(positions, torque);
    std::this_thread::sleep_for(std::chrono::duration<double>(period));
  }
}
#endif

int main(int argc, char **argv) {
  cxxopts::Options options("kapandji", "Kapandji opposition sequence");
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
      "yaml-config", "Path to YAML configuration file",
      cxxopts::value<std::string>()->default_value("../config/kapandji.yaml"))(
      "hand", "Which hand configuration to use",
      cxxopts::value<std::string>()->default_value("left"))(
      "publish-frequency", "Command publish rate (Hz)",
      cxxopts::value<double>()->default_value("60.0"))("h,help", "Print usage");

  auto result = options.parse(argc, argv);

  if (result.count("help")) {
    std::cout << options.help() << std::endl;
    return 0;
  }

  std::string commandEndpoint = result["command-endpoint"].as<std::string>();
  std::string statusEndpoint = result["status-endpoint"].as<std::string>();
  std::string handStreamingEndpoint =
      result["hand-streaming-endpoint"].as<std::string>();
  std::string wristStreamingEndpoint =
      result["wrist-streaming-endpoint"].as<std::string>();
  std::string yamlConfig = result["yaml-config"].as<std::string>();
  std::string hand = result["hand"].as<std::string>();
  double publishFreq = result["publish-frequency"].as<double>();

  utils::printBanner("ProHand Kapandji Opposition Test");
  std::cout << "\nConfiguration:\n";
  std::cout << "  YAML config:      " << yamlConfig << "\n";
  std::cout << "  Hand:             " << hand << "\n";
  std::cout << "  Publish rate:     " << publishFreq << " Hz\n";

#ifdef YAML_CPP_FOUND
  try {
    // Load YAML configuration
    utils::printSection("Loading YAML configuration...");
    YAML::Node cfg = YAML::LoadFile(yamlConfig);
    utils::printSuccess("YAML configuration loaded!");

    // Resolve torque level from YAML
    float torqueLevel = 0.45f;
    try {
      if (cfg["default_torque_level"]) {
        std::string level = cfg["default_torque_level"].as<std::string>();
        if (cfg["torque_map"] && cfg["torque_map"][level]) {
          torqueLevel =
              static_cast<float>(cfg["torque_map"][level].as<double>());
        }
      }
    } catch (...) {
      torqueLevel = 0.45f; // Keep default on any parse error
    }

    // Connect to IPC host
    utils::printSection("Connecting to IPC host with streaming...");
    ProHandClient client(commandEndpoint, statusEndpoint, handStreamingEndpoint,
                         wristStreamingEndpoint);
    utils::printSuccess("Connected with streaming support!");

    // Verify connection
    utils::printSection("Verifying connection...");
    client.sendPing();
    std::this_thread::sleep_for(std::chrono::milliseconds(200));
    utils::printSuccess("Connection verified!");

    // Enable streaming mode
    utils::printSection("Enabling streaming mode...");
    utils::printInfo("Telling driver to accept streaming commands...");
    client.setStreamingMode(true);

    utils::printInfo("Waiting for streaming connection to be ready...");
    if (!client.waitForStreamingReady(10.0)) {
      utils::printError("Streaming connection failed to establish!");
      std::cout << "\nMake sure:\n";
      std::cout << "  1. prohand-headless-ipc-host is running\n";
      std::cout << "  2. Driver has streaming endpoint enabled\n";
      std::cout << "  3. All ZMQ endpoints match between client and driver\n";
      return 1;
    }
    utils::printSuccess("Streaming mode enabled!");

    // Run Kapandji sequence
    utils::printSection("Running Kapandji opposition sequence...");
    std::vector<std::pair<std::string, double>> sequence = {
        // Slow
        {"finger_down_0", 2.0},
        {"finger_down_1", 1.0},
        {"finger_down_2", 1.0},
        {"finger_down_3", 1.0},
        {"finger_down_4", 1.0},
        {"finger_down_3", 1.0},
        {"finger_down_2", 1.0},
        {"finger_down_1", 1.0},

        // Medium
        {"finger_down_0", 1.25},
        {"finger_down_1", 0.5},
        {"finger_down_2", 0.5},
        {"finger_down_3", 0.5},
        {"finger_down_4", 0.5},
        {"finger_down_3", 0.5},
        {"finger_down_2", 0.5},
        {"finger_down_1", 0.5},

        // Fast
        {"finger_down_0", 0.5},
        {"finger_down_1", 0.25},
        {"finger_down_2", 0.25},
        {"finger_down_3", 0.25},
        {"finger_down_4", 0.25},
        {"finger_down_3", 0.25},
        {"finger_down_2", 0.25},
        {"finger_down_1", 0.25},

        // Fastest
        {"finger_down_0", 0.25},
        {"finger_down_1", 0.1},
        {"finger_down_2", 0.1},
        {"finger_down_3", 0.1},
        {"finger_down_4", 0.1},
        {"finger_down_3", 0.1},
        {"finger_down_2", 0.1},
        {"finger_down_1", 0.1},

        // Fastest (repeat)
        {"finger_down_0", 0.25},
        {"finger_down_1", 0.1},
        {"finger_down_2", 0.1},
        {"finger_down_3", 0.1},
        {"finger_down_4", 0.1},
        {"finger_down_3", 0.1},
        {"finger_down_2", 0.1},
        {"finger_down_1", 0.1},

        // Fastest (repeat)
        {"finger_down_0", 0.25},
        {"finger_down_1", 0.1},
        {"finger_down_2", 0.1},
        {"finger_down_3", 0.1},
        {"finger_down_4", 0.1},
        {"finger_down_3", 0.1},
        {"finger_down_2", 0.1},
        {"finger_down_1", 0.1},
    };

    for (const auto &[gesture, dur] : sequence) {
      auto pose = poseFromYaml(gesture, hand, cfg);
      std::cout << "  Gesture: " << gesture << " for " << dur << "s\n";
      streamPose(client, pose, publishFreq, dur, torqueLevel);
    }

    // Return to zero
    utils::printSection("Returning to zero position...");
    std::vector<float> zeroPositions(20, 0.0f);
    client.sendHandStreams(zeroPositions, torqueLevel);
    std::this_thread::sleep_for(std::chrono::milliseconds(500));

    // Disable streaming mode
    utils::printSection("Disabling streaming mode...");
    client.setStreamingMode(false);
    std::this_thread::sleep_for(std::chrono::milliseconds(200));

    utils::printSuccess("Kapandji sequence completed!");
    return 0;

  } catch (const SdkException &e) {
    utils::printError(std::string("Kapandji test failed: ") + e.what());
    return 1;
  } catch (const std::exception &e) {
    utils::printError(std::string("Unexpected error: ") + e.what());
    return 1;
  }
#else
  utils::printError("YAML support not available (yaml-cpp not found)");
  std::cout << "\n⚠️  NOTE: This demo requires yaml-cpp to be installed.\n";
  std::cout
      << "    Install yaml-cpp and rebuild to enable full functionality.\n";
  std::cout << "    For now, this is a placeholder demo.\n\n";

  try {
    utils::printSection("Connecting to IPC host...");
    ProHandClient client(commandEndpoint, statusEndpoint, handStreamingEndpoint,
                         wristStreamingEndpoint);
    utils::printSuccess("Connected!");

    std::cout << "\nIntended Kapandji sequence:\n";
    std::cout << "  1. Enable streaming mode\n";
    std::cout << "  2. Load positions from " << yamlConfig << "\n";
    std::cout << "  3. Run opposition sequence with varying speeds\n";
    std::cout << "  4. Disable streaming mode\n";

    return 0;
  } catch (const SdkException &e) {
    utils::printError(std::string("Connection failed: ") + e.what());
    return 1;
  }
#endif
}
