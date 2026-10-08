/**
 * ProWristCam SDK Demo: Wrist Camera Monitor
 *
 * Continuously polls JPEG frames and prints per-frame statistics
 * (frame rate, UID, timestamp, JPEG size).  Optionally saves frames to disk.
 */

#include <atomic>
#include <chrono>
#include <csignal>
#include <cstdio>
#include <cxxopts.hpp>
#include <fstream>
#include <iostream>
#include <string>
#include <thread>

#include "prowrist_demo/Utils.hpp"
#include <prowrist_sdk/WristCamClient.hpp>

using namespace prowrist_sdk;
using namespace prowrist_demo;

static std::atomic<bool> g_running{true};

static void signalHandler(int) { g_running = false; }

static void printStatus(double fps, uint32_t total_frames, uint32_t uid,
                        uint64_t timestamp, size_t jpeg_size,
                        const std::string &saved_path) {
  std::cout << "\r\033[2K";
  printf("frames: %6u | fps: %5.1f | uid: %5u | ts: %llu ms | size: %6zu B",
         total_frames, fps, uid, (unsigned long long)timestamp, jpeg_size);
  if (!saved_path.empty()) {
    std::cout << " | saved: " << saved_path;
  }
  std::cout.flush();
}

int main(int argc, char **argv) {
  cxxopts::Options options(
      "test_wristcam",
      "Monitor JPEG frames from a wrist camera\n\n"
      "Examples:\n"
      "  test_wristcam --endpoint ipc:///tmp/prowristcam-left-stream.ipc\n"
      "  test_wristcam --endpoint tcp://127.0.0.1:5565 --save-dir /tmp/frames\n"
      "  test_wristcam --endpoint tcp://127.0.0.1:5575 --duration 10");

  options.add_options()("e,endpoint", "ZeroMQ stream endpoint",
                        cxxopts::value<std::string>()->default_value(
                            "ipc:///tmp/prowristcam-left-stream.ipc"))(
      "d,duration", "Duration in seconds (0 = infinite)",
      cxxopts::value<double>()->default_value("0"))(
      "s,save-dir",
      "Directory to save received JPEG frames (default: disabled)",
      cxxopts::value<std::string>()->default_value(""))("h,help",
                                                        "Print usage");

  auto result = options.parse(argc, argv);

  if (result.count("help")) {
    std::cout << options.help() << std::endl;
    return 0;
  }

  std::string endpoint = result["endpoint"].as<std::string>();
  double duration = result["duration"].as<double>();
  std::string save_dir = result["save-dir"].as<std::string>();

  signal(SIGINT, signalHandler);
  signal(SIGTERM, signalHandler);

  utils::printBanner("ProWristCam SDK - Frame Monitor");
  std::cout << "\nConnection parameters:\n";
  std::cout << "  Endpoint:  " << endpoint << "\n";
  std::cout << "  SDK:       " << WristCamClient::getVersion() << "\n";
  std::cout << "\nDisplay parameters:\n";
  std::cout << "  Duration:  "
            << (duration > 0 ? std::to_string(duration) + " s" : "infinite")
            << "\n";
  if (!save_dir.empty()) {
    std::cout << "  Save dir:  " << save_dir << "\n";
  }

  try {
    utils::printSection("Creating client...");
    WristCamClient client(endpoint);
    utils::printSuccess("Client created!");

    utils::printSection("Waiting for first frame (up to 10 s)...");
    auto init_deadline =
        std::chrono::steady_clock::now() + std::chrono::seconds(10);
    bool got_first = false;
    while (!got_first && std::chrono::steady_clock::now() < init_deadline &&
           g_running) {
      if (client.tryRecvFrame()) {
        got_first = true;
      }
      std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }

    if (got_first) {
      utils::printSuccess("Stream is live!");
    } else {
      utils::printWarning("No frames in 10 s — continuing anyway");
    }

    utils::printSection("Monitoring wrist camera stream (Ctrl+C to stop)...\n");

    auto start_time = std::chrono::steady_clock::now();
    auto fps_window_start = start_time;
    uint32_t total_frames = 0;
    uint32_t fps_count = 0;
    double current_fps = 0.0;
    uint32_t last_uid = 0;
    uint64_t last_ts = 0;
    size_t last_size = 0;
    std::string last_saved;

    while (g_running) {
      auto now = std::chrono::steady_clock::now();
      double elapsed = std::chrono::duration<double>(now - start_time).count();
      if (duration > 0 && elapsed >= duration)
        break;

      auto frame = client.tryRecvFrame();
      if (frame) {
        ++total_frames;
        ++fps_count;
        last_uid = frame->uid;
        last_ts = frame->timestamp;
        last_size = frame->jpeg.size();

        if (!save_dir.empty() && !frame->jpeg.empty()) {
          char fname[256];
          std::snprintf(fname, sizeof(fname), "%s/frame_%05u.jpg",
                        save_dir.c_str(), frame->uid);
          std::ofstream ofs(fname, std::ios::binary);
          ofs.write(reinterpret_cast<const char *>(frame->jpeg.data()),
                    static_cast<std::streamsize>(frame->jpeg.size()));
          last_saved = fname;
        }
      }

      // Update FPS counter every second
      double fps_elapsed =
          std::chrono::duration<double>(now - fps_window_start).count();
      if (fps_elapsed >= 1.0) {
        current_fps = fps_count / fps_elapsed;
        fps_count = 0;
        fps_window_start = now;
      }

      printStatus(current_fps, total_frames, last_uid, last_ts, last_size,
                  last_saved);
      if (!last_saved.empty())
        last_saved.clear();

      std::this_thread::sleep_for(std::chrono::microseconds(100));
    }

    std::cout << "\n";
    utils::printSuccess("Monitoring complete — " +
                        std::to_string(total_frames) + " frames received");
    return 0;

  } catch (const SdkException &e) {
    std::cout << "\n";
    utils::printError(std::string("SDK error: ") + e.what());
    std::cout << "\nMake sure prowristcam-headless-ipc-host is running.\n";
    return 1;
  } catch (const std::exception &e) {
    std::cout << "\n";
    utils::printError(std::string("Unexpected error: ") + e.what());
    return 1;
  }
}
