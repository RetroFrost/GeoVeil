cmake_minimum_required(VERSION 3.22.1)
project(geoveil LANGUAGES CXX)

add_library(geoveil SHARED
    src/main/cpp/module.cpp
    src/main/cpp/state_bridge.cpp
)

target_include_directories(geoveil PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/third_party/zygisk
    ${CMAKE_CURRENT_SOURCE_DIR}/src/main/cpp
)

target_compile_features(geoveil PRIVATE cxx_std_20)
target_compile_options(geoveil PRIVATE
    -Wall
    -Wextra
    -Werror
    -fvisibility=hidden
    -fvisibility-inlines-hidden
    -fno-exceptions
    -fno-rtti
    -ffunction-sections
    -fdata-sections
)

target_link_options(geoveil PRIVATE
    -Wl,--gc-sections
    -Wl,--exclude-libs,ALL
)

set_target_properties(geoveil PROPERTIES
    OUTPUT_NAME geoveil
)
