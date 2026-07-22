#pragma once

#include <cstdint>

#include "ipc.hpp"

namespace geoveil {

constexpr uint32_t kControlMagic = 0x47564354;  // GVCT
constexpr uint16_t kControlVersion = 1;
constexpr char kControlDirectory[] = "/data/adb/geoveil/control";
constexpr char kControlLock[] = "/data/adb/geoveil/control/lock";
constexpr char kControlRequest[] = "/data/adb/geoveil/control/request.bin";
constexpr char kControlRequestTemp[] = "/data/adb/geoveil/control/request.tmp";
constexpr char kControlResponse[] = "/data/adb/geoveil/control/response.bin";
constexpr char kControlResponseTemp[] = "/data/adb/geoveil/control/response.tmp";

struct ControlRequest {
    uint32_t magic = kControlMagic;
    uint16_t version = kControlVersion;
    uint16_t operation = 0;
    uint64_t nonce = 0;
    uint64_t generation = 0;
    PublishPayload publish;
};

struct ControlResponse {
    uint32_t magic = kControlMagic;
    uint16_t version = kControlVersion;
    uint16_t reserved = 0;
    uint64_t nonce = 0;
    Response response;
};

}  // namespace geoveil
