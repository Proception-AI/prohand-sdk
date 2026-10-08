/**
 * ProHand SDK FFI Demo: Ping Command
 */

#include <chrono>
#include <cxxopts.hpp>
#include <iostream>
#include <thread>

#include "prohand_demo/Utils.hpp"
#include <prohand_sdk/ProHandClient.hpp>

using namespace prohand_sdk;
using namespace prohand_demo; // For utils namespace

int main(int argc, char **argv) {
  cxxopts::Options options("ping", "Send ping commands to ProHand IPC host");

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
      "c,count", "Number of pings to send",
      cxxopts::value<int>()->default_value("10"))(
      "d,delay", "Delay between pings (seconds)",
      cxxopts::value<double>()->default_value("1.0"))("h,help", "Print usage");

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
  auto count = result["count"].as<int>();
  auto delay = result["delay"].as<double>();

  utils::printBanner("ProHand Ping Demo");

  std::cout << "Configuration:\n";
  std::cout << "  Command endpoint:       " << commandEndpoint << "\n";
  std::cout << "  Status endpoint:         " << statusEndpoint << "\n";
  std::cout << "  Hand streaming endpoint: " << handStreamingEndpoint << "\n";
  std::cout << "  Wrist streaming endpoint: " << wristStreamingEndpoint << "\n";
  std::cout << "  Ping count: " << count << "\n";
  std::cout << "  Delay: " << delay << "s\n";

  try {
    utils::printSection("Connecting to IPC host...");
    ProHandClient client(commandEndpoint, statusEndpoint, handStreamingEndpoint,
                         wristStreamingEndpoint);
    utils::printSuccess("Connected!");

    utils::printSection("Sending ping commands...");

    int successCount = 0;
    for (int i = 0; i < count; ++i) {
      try {
        auto start = std::chrono::steady_clock::now();
        client.sendPing();
        auto end = std::chrono::steady_clock::now();
        auto latency =
            std::chrono::duration_cast<std::chrono::microseconds>(end - start);

        successCount++;
        std::cout << "Ping " << (i + 1) << "/" << count
                  << " - ✓ Success (latency: " << latency.count() << "µs)\n";

        if (i < count - 1) {
          std::this_thread::sleep_for(std::chrono::duration<double>(delay));
        }
      } catch (const SdkException &e) {
        std::cout << "Ping " << (i + 1) << "/" << count
                  << " - ✗ Failed: " << e.what() << "\n";
      }
    }

    std::cout << "\n";
    utils::printSuccess("Ping test completed!");
    std::cout << "  Success rate: " << successCount << "/" << count << " ("
              << (100.0 * successCount / count) << "%)\n";

    return successCount == count ? 0 : 1;
  } catch (const SdkException &e) {
    utils::printError(std::string("Connection failed: ") + e.what());
    std::cout << "\nMake sure the ProHand IPC host is running.\n";
    return 1;
  } catch (const std::exception &e) {
    utils::printError(std::string("Unexpected error: ") + e.what());
    return 1;
  }
}
