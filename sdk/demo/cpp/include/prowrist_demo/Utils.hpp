/**
 * Utility helpers for ProWristCam C++ demo applications.
 */

#pragma once

#include <iostream>
#include <string>

namespace prowrist_demo {
namespace utils {

inline void printBanner(const std::string &title, int width = 60) {
  std::string line(width, '=');
  std::cout << line << "\n" << title << "\n" << line << "\n";
}

inline void printSection(const std::string &title) {
  std::cout << "\n>>> " << title << "\n";
}

inline void printSuccess(const std::string &msg) {
  std::cout << "✓ " << msg << "\n";
}

inline void printError(const std::string &msg) {
  std::cerr << "✗ " << msg << "\n";
}

inline void printInfo(const std::string &msg) {
  std::cout << "  " << msg << "\n";
}

inline void printWarning(const std::string &msg) {
  std::cout << "! " << msg << "\n";
}

} // namespace utils
} // namespace prowrist_demo
