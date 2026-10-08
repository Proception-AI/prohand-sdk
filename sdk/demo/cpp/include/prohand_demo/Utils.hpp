/**
 * Utility functions for ProHand FFI demos
 */

#pragma once

#include <iostream>
#include <string>

namespace prohand_demo {
namespace utils {

inline void printBanner(const std::string &title, int width = 60) {
  std::cout << std::string(width, '=') << "\n";
  std::cout << title << "\n";
  std::cout << std::string(width, '=') << "\n";
}

inline void printSection(const std::string &title) {
  std::cout << "\n>>> " << title << "\n";
}

inline void printError(const std::string &message) {
  std::cout << "❌ " << message << "\n";
}

inline void printSuccess(const std::string &message) {
  std::cout << "✅ " << message << "\n";
}

inline void printInfo(const std::string &message) {
  std::cout << "ℹ️  " << message << "\n";
}

} // namespace utils
} // namespace prohand_demo
