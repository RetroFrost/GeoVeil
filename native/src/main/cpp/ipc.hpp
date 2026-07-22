#pragma once

#include <cstdint>

namespace geoveil {

constexpr uint32_t kIpcMagic = 0x47564950;  // GVIP
constexpr uint16_t kIpcVersion = 2;

enum class ClientRole : uint16_t {
    kUnknown = 0,
    kSystemServer = 1,
    kManagerApp = 2,
    kTopAppOverlay = 3,
};

enum class Operation : uint16_t {
    kProbe = 1,
    kPublish = 2,
    kMove = 3,
    kEngineBegin = 4,
    kEngineHealthy = 5,
    kEngineAbort = 6,
    kClearEmergency = 7,
    kDisableModule = 8,
};

enum class Status : int32_t {
    kOk = 0,
    kBadMessage = -1,
    kBadVersion = -2,
    kInvalidState = -3,
    kStaleGeneration = -4,
    kEmergencyDisabled = -5,
    kIoError = -6,
    kNotReady = -7,
};

struct ClientHello {
    uint32_t magic = kIpcMagic;
    uint16_t version = kIpcVersion;
    uint16_t role = static_cast<uint16_t>(ClientRole::kUnknown);
    int32_t pid = 0;
    int32_t uid = 0;
};

struct MessageHeader {
    uint32_t magic = kIpcMagic;
    uint16_t version = kIpcVersion;
    uint16_t operation = 0;
    uint32_t payload_size = 0;
    uint32_t reserved = 0;
    uint64_t generation = 0;
};

struct PublishPayload {
    uint32_t flags = 0;
    uint32_t movement_mode = 0;
    double latitude = 0.0;
    double longitude = 0.0;
    double altitude = 0.0;
    float speed = 0.0f;
    float bearing = 0.0f;
    float accuracy = 5.0f;
    uint32_t reserved = 0;
};

struct MovePayload {
    float normalized_x = 0.0f;
    float normalized_y = 0.0f;
    uint32_t movement_mode = 0;
    uint32_t active = 0;
    uint64_t event_monotonic_ns = 0;
};

struct Response {
    uint32_t magic = kIpcMagic;
    uint16_t version = kIpcVersion;
    uint16_t reserved = 0;
    int32_t status = static_cast<int32_t>(Status::kIoError);
    uint32_t flags = 0;
    uint64_t accepted_generation = 0;
};

static_assert(sizeof(ClientHello) == 16);
static_assert(sizeof(MessageHeader) == 24);
static_assert(sizeof(PublishPayload) == 48);
static_assert(sizeof(MovePayload) == 24);
static_assert(sizeof(Response) == 24);

}  // namespace geoveil
