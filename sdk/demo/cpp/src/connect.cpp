/**
 * ProHand SDK FFI Demo: Basic Connection Test
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
  cxxopts::Options options("connect", "Test connection to ProHand IPC host");

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
          "ipc:///tmp/prohand-wrist-streaming.ipc"))("h,help", "Print usage");

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

  utils::printBanner("ProHand IPC Connection Test");

  std::cout << "Connection parameters:\n";
  std::cout << "  Command endpoint:       " << commandEndpoint << "\n";
  std::cout << "  Status endpoint:         " << statusEndpoint << "\n";
  std::cout << "  Hand streaming endpoint: " << handStreamingEndpoint << "\n";
  std::cout << "  Wrist streaming endpoint: " << wristStreamingEndpoint << "\n";

  try {
    utils::printSection("Connecting to IPC host...");
    ProHandClient client(commandEndpoint, statusEndpoint, handStreamingEndpoint,
                         wristStreamingEndpoint);

    // Wait for connection to establish (asynchronous background connection)
    utils::printInfo("Waiting for connection to establish...");
    const double maxWait = 2.0;      // Maximum wait time in seconds
    const double pollInterval = 0.1; // Poll every 100ms
    auto startTime = std::chrono::steady_clock::now();

    while (!client.isConnected() &&
           std::chrono::duration<double>(std::chrono::steady_clock::now() -
                                         startTime)
                   .count() < maxWait) {
      std::this_thread::sleep_for(std::chrono::duration<double>(pollInterval));
    }

    if (!client.isConnected()) {
      utils::printError("Failed to establish connection within timeout");
      utils::printInfo("Make sure the IPC host is running");
      return 1;
    }

    utils::printSuccess("Successfully connected to IPC host");

    utils::printSection("Testing communication...");
    client.sendPing();
    utils::printSuccess("Ping successful!");

    utils::printSection("SDK Information:");
    std::cout << "  Version: " << ProHandClient::getVersion() << "\n";

    utils::printSuccess("Connection test completed successfully!");
    return 0;

  } catch (const SdkException &e) {
    utils::printError(std::string("Connection failed: ") + e.what());
    std::cout << "\nMake sure the ProHand IPC host is running.\n";
    return 1;
  } catch (const std::exception &e) {
    utils::printError(std::string("Unexpected error: ") + e.what());
    return 1;
  }
}
