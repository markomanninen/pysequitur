// Times jsdw's C++11 Sequitur (github.com/jsdw/cpp-sequitur) on a file, then
// measures the grammar it built and expands it back. fetch.sh builds it:
//   clang++ -std=c++11 -O2 -I vendor/cpp-sequitur bench_jsdw.cpp vendor/cpp-sequitur/sequitur/*.cpp
// This is its main.cpp with a timer, and without the progress and the rules printed.
#include <chrono>
#include <fstream>
#include <iostream>
#include <iterator>
#include <string>
#include "sequitur.hpp"

using namespace jw;

int main(int argc, char* argv[]) {
    std::ifstream input(argv[1], std::ios::binary);
    std::string text((std::istreambuf_iterator<char>(input)), std::istreambuf_iterator<char>());

    auto start = std::chrono::steady_clock::now();
    Sequitur<char> s;
    for (char c : text) s.push_back(c);
    double seconds = std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();

    bool same = s.size() == text.size();
    auto it = s.begin();
    for (size_t i = 0; same && i < text.size(); ++i, ++it) same = *it == text[i];

    // as main.cpp counts them: hops from a rule's head to its tail, less the tail
    auto rules = s.getRules();
    unsigned long symbols = 0;
    for (auto& rule : rules) symbols += rule.second->end().second - 1;
    std::cout << "{\"seconds\": " << seconds << ", \"rules\": " << rules.size() - 1 << ", \"symbols\": " << symbols
              << ", \"roundtrip\": " << (same ? "true" : "false") << "}" << std::endl;
    return 0;
}
