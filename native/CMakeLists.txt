cmake_minimum_required(VERSION 3.28)
project(geoveil LANGUAGES C CXX ASM)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

set(DOBBY_DEBUG OFF CACHE BOOL "" FORCE)
set(DOBBY_BUILD_EXAMPLE OFF CACHE BOOL "" FORCE)
set(DOBBY_BUILD_TEST OFF CACHE BOOL "" FORCE)
set(Plugin.SymbolResolver ON CACHE BOOL "" FORCE)
set(Plugin.ImportTableReplace OFF CACHE BOOL "" FORCE)
set(Plugin.Android.BionicLinkerUtil OFF CACHE BOOL "" FORCE)
set(LSPLANT_BUILD_SHARED OFF CACHE BOOL "" FORCE)

add_subdirectory(third_party/dobby third_party_build/dobby EXCLUDE_FROM_ALL)
add_subdirectory(third_party/lsplant/lsplant/src/main/jni
    third_party_build/lsplant EXCLUDE_FROM_ALL)

add_library(geoveil SHARED
    src/main/cpp/module.cpp
    src/main/cpp/bridge.cpp
    src/main/cpp/companion.cpp
    src/main/cpp/engine.cpp
)

add_executable(geoveilctl
    src/main/cpp/control.cpp
)

target_include_directories(geoveil PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/src/main/cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/third_party/zygisk
)

target_compile_features(geoveil PRIVATE cxx_std_23)
target_compile_features(geoveilctl PRIVATE cxx_std_23)
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

target_compile_options(geoveilctl PRIVATE
    -Wall
    -Wextra
    -Werror
    -fno-exceptions
    -fno-rtti
    -ffunction-sections
    -fdata-sections
)

target_link_libraries(geoveil PRIVATE
    lsplant_static
    dobby_static
    log
    dl
)

target_link_options(geoveil PRIVATE
    -Wl,--gc-sections
    -Wl,--exclude-libs,ALL
)

target_link_options(geoveilctl PRIVATE
    -Wl,--gc-sections
)

set_target_properties(geoveil PROPERTIES
    OUTPUT_NAME geoveil
)
