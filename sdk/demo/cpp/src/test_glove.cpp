/**
 * @file test_glove.cpp
 * @brief ProGlove SDK Demo: Test Glove - Tactile Sensor Monitor
 *
 * Reads all taxel data from the glove and displays it in the terminal.
 * Taxel data is organized by joint segment (DIP/MCP/PIP per finger).
 */

#include <atomic>
#include <chrono>
#include <csignal>
#include <cxxopts.hpp>
#include <iomanip>
#include <iostream>
#include <thread>

#include "proglove_demo/Utils.hpp"
#include <proglove_sdk/ProGloveClient.hpp>

using namespace proglove_sdk;
using namespace proglove_demo;

// Global flag for signal handling (graceful Ctrl+C exit)
static std::atomic<bool> g_running{true};

/**
 * @brief Signal handler for graceful shutdown on Ctrl+C
 */
void signalHandler(int signum) {
  (void)signum;
  g_running = false;
}

/**
 * @brief Display tactile status in formatted output
 * @param status Tactile status data
 * @param rate Current sample rate in Hz
 */
void displayStatus(const TactileStatus &status, double rate) {
  utils::clearScreen();
  utils::printBanner("ProGlove Test Glove - Tactile Sensor Monitor");

  std::cout << "\n";
  std::cout << "Timestamp: " << std::setw(5) << status.timestamp
            << " | UID: " << status.uid << " | Rate: " << std::fixed
            << std::setprecision(1) << rate << " Hz\n";
  std::cout << "\n";

  // Thumb (largest finger: DIP=6, MCP=10, PIP=4)
  std::cout << "THUMB:  DIP[" << std::setw(2) << status.t_dip.size() << "]: "
            << utils::formatArray(status.t_dip.data(), status.t_dip.size())
            << "\n";
  std::cout << "        PIP[" << std::setw(2) << status.t_pip.size() << "]: "
            << utils::formatArray(status.t_pip.data(), status.t_pip.size())
            << "\n";
  std::cout << "        MCP[" << std::setw(2) << status.t_mcp.size() << "]: "
            << utils::formatArray(status.t_mcp.data(), status.t_mcp.size())
            << "\n";

  // Index (DIP=4, MCP=2, PIP=2)
  std::cout << "INDEX:  DIP[" << std::setw(2) << status.i_dip.size() << "]: "
            << utils::formatArray(status.i_dip.data(), status.i_dip.size())
            << "\n";
  std::cout << "        PIP[" << std::setw(2) << status.i_pip.size() << "]: "
            << utils::formatArray(status.i_pip.data(), status.i_pip.size())
            << "\n";
  std::cout << "        MCP[" << std::setw(2) << status.i_mcp.size() << "]: "
            << utils::formatArray(status.i_mcp.data(), status.i_mcp.size())
            << "\n";

  // Middle (DIP=4, MCP=2, PIP=2)
  std::cout << "MIDDLE: DIP[" << std::setw(2) << status.m_dip.size() << "]: "
            << utils::formatArray(status.m_dip.data(), status.m_dip.size())
            << "\n";
  std::cout << "        PIP[" << std::setw(2) << status.m_pip.size() << "]: "
            << utils::formatArray(status.m_pip.data(), status.m_pip.size())
            << "\n";
  std::cout << "        MCP[" << std::setw(2) << status.m_mcp.size() << "]: "
            << utils::formatArray(status.m_mcp.data(), status.m_mcp.size())
            << "\n";

  // Ring (DIP=4, MCP=2, PIP=2)
  std::cout << "RING:   DIP[" << std::setw(2) << status.r_dip.size() << "]: "
            << utils::formatArray(status.r_dip.data(), status.r_dip.size())
            << "\n";
  std::cout << "        PIP[" << std::setw(2) << status.r_pip.size() << "]: "
            << utils::formatArray(status.r_pip.data(), status.r_pip.size())
            << "\n";
  std::cout << "        MCP[" << std::setw(2) << status.r_mcp.size() << "]: "
            << utils::formatArray(status.r_mcp.data(), status.r_mcp.size())
            << "\n";

  // Pinky (DIP=4, MCP=2, PIP=2)
  std::cout << "PINKY:  DIP[" << std::setw(2) << status.p_dip.size() << "]: "
            << utils::formatArray(status.p_dip.data(), status.p_dip.size())
            << "\n";
  std::cout << "        PIP[" << std::setw(2) << status.p_pip.size() << "]: "
            << utils::formatArray(status.p_pip.data(), status.p_pip.size())
            << "\n";
  std::cout << "        MCP[" << std::setw(2) << status.p_mcp.size() << "]: "
            << utils::formatArray(status.p_mcp.data(), status.p_mcp.size())
            << "\n";

  // Palm segments (16 taxels each)
  std::cout << "\n";
  std::cout << "PALM:   Upper [" << std::setw(2) << status.upper_palm.size()
            << "]: "
            << utils::formatArray(status.upper_palm.data(),
                                  status.upper_palm.size())
            << "\n";
  std::cout << "        Middle[" << std::setw(2) << status.middle_palm.size()
            << "]: "
            << utils::formatArray(status.middle_palm.data(),
                                  status.middle_palm.size())
            << "\n";
  std::cout << "        Lower [" << std::setw(2) << status.lower_palm.size()
            << "]: "
            << utils::formatArray(status.lower_palm.data(),
                                  status.lower_palm.size())
            << "\n";

  std::cout << "\nPress Ctrl+C to stop\n";
}

int main(int argc, char **argv) {
  // Setup command line argument parsing
  cxxopts::Options options(
      "test_glove",
      "Monitor tactile sensor data from ProGlove\n\n"
      "Examples:\n"
      "  # Connect via IPC (local)\n"
      "  test_glove --status-endpoint ipc:///tmp/proglove-left-status.ipc\n"
      "  test_glove --status-endpoint ipc:///tmp/proglove-right-status.ipc\n\n"
      "  # Connect via TCP (remote)\n"
      "  test_glove --status-endpoint tcp://192.168.1.82:5565\n"
      "  test_glove --status-endpoint tcp://127.0.0.1:5565\n\n"
      "Default endpoints:\n"
      "  Left hand (IPC):  ipc:///tmp/proglove-left-status.ipc\n"
      "  Right hand (IPC): ipc:///tmp/proglove-right-status.ipc\n"
      "  Left hand (TCP):  tcp://127.0.0.1:5565\n"
      "  Right hand (TCP): tcp://127.0.0.1:5575");

  options.add_options()(
      "s,status-endpoint",
      "ZeroMQ status endpoint (e.g., tcp://192.168.1.82:5565)",
      cxxopts::value<std::string>())(
      "d,duration", "Duration to run in seconds (0 = infinite)",
      cxxopts::value<double>()->default_value("0"))(
      "r,refresh-rate", "Terminal refresh rate in Hz",
      cxxopts::value<double>()->default_value("10.0"))("h,help", "Print usage");

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

  auto duration = result["duration"].as<double>();
  auto refreshRate = result["refresh-rate"].as<double>();

  // Setup signal handler for Ctrl+C
  std::signal(SIGINT, signalHandler);

  utils::printBanner("ProGlove Test Glove - Tactile Sensor Monitor");

  std::cout << "\nConnection parameters:\n";
  std::cout << "  Mode:     " << connectionType << "\n";
  std::cout << "  Status endpoint: " << endpoint << "\n";

  std::cout << "\nDisplay parameters:\n";
  std::cout << "  Duration:     " << duration << "s (0 = infinite)\n";
  std::cout << "  Refresh rate: " << refreshRate << " Hz\n";

  try {
    // Create client using C++ wrapper
    utils::printSection("Connecting to " + endpoint + "...");
    ProGloveClient client(endpoint);
    utils::printSuccess("Client created!");

    // Verify connection with a ping
    utils::printSection("Verifying connection...");
    client.sendPing();
    utils::printSuccess("Connection verified!");

    // Monitoring loop
    utils::printSection("Starting tactile sensor monitoring...");
    std::this_thread::sleep_for(std::chrono::milliseconds(500));

    auto startTime = std::chrono::steady_clock::now();
    auto lastDisplayTime = startTime;
    auto rateStartTime = startTime;
    double displayInterval = 1.0 / refreshRate;

    int rateSamples = 0;
    double currentRate = 0.0;

    while (g_running) {
      auto now = std::chrono::steady_clock::now();
      double elapsed = std::chrono::duration<double>(now - startTime).count();

      // Check duration limit
      if (duration > 0 && elapsed >= duration) {
        break;
      }

      // Poll for status (non-blocking)
      auto status = client.tryRecvStatus();

      if (status && status->isValid) {
        rateSamples++;

        // Update rate calculation every second
        double rateElapsed =
            std::chrono::duration<double>(now - rateStartTime).count();
        if (rateElapsed >= 1.0) {
          currentRate = rateSamples / rateElapsed;
          rateSamples = 0;
          rateStartTime = now;
        }

        // Display at refresh rate
        double displayElapsed =
            std::chrono::duration<double>(now - lastDisplayTime).count();
        if (displayElapsed >= displayInterval) {
          displayStatus(*status, currentRate);
          lastDisplayTime = now;
        }
      }

      // Small sleep to avoid busy-waiting (100 microseconds)
      std::this_thread::sleep_for(std::chrono::microseconds(100));
    }

    return 0;

  } catch (const SdkException &e) {
    utils::printError(std::string("Demo failed: ") + e.what());
    std::cout << "\nMake sure proglove-headless-ipc-host is running\n";
    return 1;
  } catch (const std::exception &e) {
    utils::printError(std::string("Unexpected error: ") + e.what());
    return 1;
  }
}
