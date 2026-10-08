/**
 * ProGlove SDK Demo: Basic Connection Test
 */

#include <chrono>
#include <cxxopts.hpp>
#include <iostream>
#include <thread>

#include "proglove_demo/Utils.hpp"
#include <proglove_sdk/ProGloveClient.hpp>

using namespace proglove_sdk;
using namespace proglove_demo; // For utils namespace

int main(int argc, char **argv) {
  cxxopts::Options options(
      "connect_glove",
      "Test connection to ProGlove IPC host\n\n"
      "Examples:\n"
      "  connect_glove --status-endpoint ipc:///tmp/proglove-left-status.ipc\n"
      "  connect_glove --status-endpoint tcp://192.168.1.82:5565");

  options.add_options()(
      "s,status-endpoint",
      "ZeroMQ status endpoint (e.g., tcp://192.168.1.82:5565)",
      cxxopts::value<std::string>())("h,help", "Print usage");

  auto result = options.parse(argc, argv);

  if (result.count("help")) {
    std::cout << options.help() << std::endl;
    return 0;
  }

  // Check for required --status-endpoint argument
  if (result.count("status-endpoint") == 0) {
    std::cerr << "ERROR: --status-endpoint is required\n\n";
    std::cout << options.help() << std::endl;
    return 1;
  }

  // Use the endpoint directly
  std::string endpoint = result["status-endpoint"].as<std::string>();
  std::string connectionType = endpoint;

  utils::printBanner("ProGlove IPC Connection Test");

  std::cout << "Connection parameters:\n";
  std::cout << "  Mode:     " << connectionType << "\n";
  std::cout << "  Status endpoint: " << endpoint << "\n";

  try {
    utils::printSection("Connecting to IPC host...");
    ProGloveClient client(endpoint);

    // Wait for connection to establish
    utils::printInfo("Waiting for connection to establish...");
    client.sendPing();
    utils::printSuccess("Successfully connected to IPC host");

    utils::printSection("Testing communication...");
    utils::printSuccess("Ping successful!");

    utils::printSection("SDK Information:");
    std::cout << "  Version: " << ProGloveClient::getVersion() << "\n";

    utils::printSuccess("Connection test completed successfully!");
    return 0;

  } catch (const SdkException &e) {
    utils::printError(std::string("Connection failed: ") + e.what());
    std::cout << "\nMake sure the ProGlove IPC host is running.\n";
    return 1;
  } catch (const std::exception &e) {
    utils::printError(std::string("Unexpected error: ") + e.what());
    return 1;
  }
}
