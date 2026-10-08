/**
 * Utility functions for ProGlove FFI demos
 */

#pragma once

#include <iostream>
#include <sstream>
#include <string>

namespace proglove_demo {
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

inline void clearScreen() { std::cout << "\033[2J\033[H" << std::flush; }

template <typename T>
inline std::string formatArray(const T *data, size_t size) {
  std::ostringstream oss;
  oss << "[";
  for (size_t i = 0; i < size; ++i) {
    if (i > 0)
      oss << ", ";
    oss << static_cast<int>(data[i]);
  }
  oss << "]";
  return oss.str();
}

} // namespace utils
} // namespace proglove_demo
