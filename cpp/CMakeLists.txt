cmake_minimum_required(VERSION 3.14)
project(ProofChecker VERSION 1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find Z3
find_package(Z3 REQUIRED CONFIG)

# Fetch nlohmann/json
include(FetchContent)
FetchContent_Declare(
    json
    GIT_REPOSITORY https://github.com/nlohmann/json.git
    GIT_TAG v3.11.3
)
FetchContent_MakeAvailable(json)

# Main executable
add_executable(prover prover.cpp)
target_link_libraries(prover PRIVATE z3::libz3 nlohmann_json::nlohmann_json)
target_include_directories(prover PRIVATE ${CMAKE_CURRENT_BINARY_DIR}/_deps/json-src/include)

# Installation
install(TARGETS prover RUNTIME DESTINATION bin)
