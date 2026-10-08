/**
 * ProHand SDK FFI Demo: Cyclic Joint Motion
 *
 * Runs sine wave motion patterns across finger joints.
 */

#include <chrono>
#include <cmath>
#include <cxxopts.hpp>
#include <iostream>
#include <map>
#include <string>
#include <thread>
#include <vector>

#include "prohand_demo/Utils.hpp"
#include <prohand_sdk/ProHandClient.hpp>

using namespace prohand_sdk;
using namespace prohand_demo; // For utils namespace

int main(int argc, char **argv) {
  cxxopts::Options options("cyclic_motion", "Run cyclic joint motion patterns");

  // clang-format off
    options.add_options()("command-endpoint", "ZMQ command endpoint",
                        cxxopts::value<std::string>()->default_value("ipc:///tmp/prohand-commands.ipc"))\
                        ("status-endpoint", "ZMQ status endpoint", cxxopts::value<std::string>()->default_value("ipc:///tmp/prohand-status.ipc"))\
                        ("hand-streaming-endpoint", "ZMQ hand streaming endpoint", cxxopts::value<std::string>()->default_value("ipc:///tmp/prohand-hand-streaming.ipc"))\
                        ("wrist-streaming-endpoint", "ZMQ wrist streaming endpoint", cxxopts::value<std::string>()->default_value("ipc:///tmp/prohand-wrist-streaming.ipc"))\
                        ("amp-scale", "Amplitude scale factor", cxxopts::value<double>()->default_value("0.8"))\
                        ("frequency", "Motion frequency (Hz)", cxxopts::value<double>()->default_value("0.5"))\
                        ("duration", "Duration (seconds)", cxxopts::value<double>()->default_value("60.0"))\
                        ("pub-hz", "Command publish rate (Hz)", cxxopts::value<double>()->default_value("100.0"))\
                        ("include-thumb", "Include thumb in motion", cxxopts::value<bool>()->default_value("false"))\
                        ("exclude-wrist", "Exclude wrist from motion", cxxopts::value<bool>()->default_value("false"))\
                        ("h,help", "Print usage");
  // clang-format on
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
  auto amplitudeScale = result["amp-scale"].as<double>();
  auto frequency = result["frequency"].as<double>();
  auto duration = result["duration"].as<double>();
  auto pubHz = result["pub-hz"].as<double>();
  bool includeThumb = result.count("include-thumb") > 0;
  bool excludeWrist = result.count("exclude-wrist") > 0;

  // Abduction is always disabled
  bool includeAbduction = false;

  utils::printBanner("ProHand Cyclic Joint Motion");

  std::cout << "\nMotion parameters:\n";
  std::cout << "  Amplitude scale: " << amplitudeScale << "\n";
  std::cout << "  Frequency: " << frequency << " Hz\n";
  std::cout << "  Duration: " << duration << "s\n";
  std::cout << "  Publish rate: " << pubHz << " Hz\n";
  std::cout << "  Include thumb: " << (includeThumb ? "true" : "false") << "\n";
  std::cout << "  Exclude wrist: " << (excludeWrist ? "true" : "false") << "\n";

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
    if (!client.waitForStreamingReady(10.0)) {
      utils::printError("Streaming connection failed to establish!");
      client.setStreamingMode(false);
      return 1;
    }

    utils::printSuccess(
        "Streaming mode enabled! Commands will use streaming socket.");

    utils::printSection("Running cyclic motion for " +
                        std::to_string(duration) + "s...");

    auto period = std::chrono::duration<double>(1.0 / pubHz);
    auto startTime = std::chrono::steady_clock::now();
    int iteration = 0;

    while (true) {
      // Calculate target time for this iteration (fixed timing, no drift)
      auto targetTime =
          startTime + std::chrono::duration<double>(iteration * (1.0 / pubHz));
      auto now = std::chrono::steady_clock::now();
      double t = std::chrono::duration<double>(now - startTime).count();

      if (t >= duration) {
        break;
      }

      // Phase offsets for each finger (wave motion across fingers)
      const std::vector<std::string> fingers = {"thumb", "index", "middle",
                                                "ring", "pinky"};
      std::map<std::string, double> fingerPhases;
      for (size_t i = 0; i < fingers.size(); ++i) {
        fingerPhases[fingers[i]] =
            (i / static_cast<double>(fingers.size())) * 2.0 * M_PI;
      }

      // Max angles per joint (in degrees)
      const double fingerMaxDeg[4] = {
          90.0, 90.0, 90.0, 90.0}; // metacarpal, proximal, intermediate, distal
      const double wristMaxDeg[2] = {30.0,
                                     65.0}; // wrist joint 1, wrist joint 2

      // Calculate joint angles (20 rotary joints: 5 fingers × 4 joints)
      // Joint layout: thumb(0-3), index(4-7), middle(8-11), ring(12-15),
      // pinky(16-19)
      std::vector<float> positions;

      for (size_t fingerIdx = 0; fingerIdx < fingers.size(); ++fingerIdx) {
        const std::string &fingerName = fingers[fingerIdx];
        double basePhase = fingerPhases[fingerName];

        for (int j = 0; j < 4; ++j) // 4 joints per finger
        {
          // Skip metacarpal (j=0) for non-thumb fingers if abduction not
          // included
          if (!includeAbduction && j == 0 && fingerName != "thumb") {
            positions.push_back(0.0f);
          } else {
            // Per-joint phase offset: j * 0.4 creates wave along finger
            double jointPhase =
                2.0 * M_PI * frequency * t + (j * 0.4) + basePhase;
            // Normalized sine [0, 1]
            double s01 = 0.5 + 0.5 * std::sin(jointPhase);
            // Scale by max angle and amplitude scale
            double jointAngleDeg = s01 * (fingerMaxDeg[j] * amplitudeScale);
            positions.push_back(
                static_cast<float>(jointAngleDeg * M_PI / 180.0));
          }
        }

        // Zero thumb joints if not included
        if (!includeThumb && fingerName == "thumb") {
          positions[fingerIdx * 4 + 1] = 0.0f;
          positions[fingerIdx * 4 + 2] = 0.0f;
          positions[fingerIdx * 4 + 3] = 0.0f;
        }
      }

      // Torque (0.0-1.0 normalized, single value for all joints)
      float torque = 1.0f; // Match original torque_level=1.0

      // Wrist command (wrist joints) - alternates between joints
      if (!excludeWrist) {
        double T = 1.0 / std::max(1e-6, frequency);
        int seg = static_cast<int>((t / T)) % 2;
        double local = 2.0 * M_PI * ((std::fmod(t, T)) / T);
        std::vector<float> wristPositions(2, 0.0f);
        if (seg == 0) {
          wristPositions[0] = static_cast<float>(
              std::sin(local) * (wristMaxDeg[0] * amplitudeScale) * M_PI /
              180.0);
        } else {
          wristPositions[1] = static_cast<float>(
              std::sin(local) * (wristMaxDeg[1] * amplitudeScale) * M_PI /
              180.0);
        }
        client.sendWristStreams(wristPositions);
      } else {
        client.sendWristStreams({0.0f, 0.0f});
      }

      // Send hand command (high-level joint angles, uses inverse kinematics)
      // Uses streaming for high-frequency control
      client.sendHandStreams(positions, torque);

      iteration++;
      if (iteration % static_cast<int>(pubHz) == 0) { // Print every second
        double mainPhase = 2.0 * M_PI * frequency * t;
        double phaseDeg = std::fmod(mainPhase * 180.0 / M_PI, 360.0);
        printf("  [%6.2fs] Running... (phase: %.1f°)\n", t, phaseDeg);
      }

      // Sleep until target time (compensates for command sending time)
      auto nextTarget = startTime + std::chrono::duration<double>(
                                        (iteration + 1) * (1.0 / pubHz));
      auto sleepTime = nextTarget - std::chrono::steady_clock::now();
      if (sleepTime.count() > 0) {
        std::this_thread::sleep_for(sleepTime);
      }
    }

    // Return to zero (use streaming mode)
    utils::printSection("Returning to zero...");
    std::vector<float> zeroPositions(20, 0.0f);
    client.sendHandStreams(zeroPositions, 1.0f);
    if (!excludeWrist) {
      client.sendWristStreams({0.0f, 0.0f});
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(500));

    // Disable streaming mode
    utils::printSection("Disabling streaming mode...");
    client.setStreamingMode(false);
    std::this_thread::sleep_for(std::chrono::milliseconds(200));

    utils::printSuccess("Cyclic motion demo completed!");
    return 0;
  } catch (const SdkException &e) {
    utils::printError(std::string("Motion failed: ") + e.what());
    return 1;
  } catch (const std::exception &e) {
    utils::printError(std::string("Unexpected error: ") + e.what());
    return 1;
  }
}
