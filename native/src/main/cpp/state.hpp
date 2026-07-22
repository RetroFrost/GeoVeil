#pragma once

#include <cmath>
#include <cstdint>
#include <cstring>

namespace geoveil {

constexpr uint32_t kStateMagic = 0x47565332;  // GVS2
constexpr uint16_t kStateVersion = 2;

constexpr uint32_t kFlagEnabled = 1u << 0;
constexpr uint32_t kFlagHasCoordinates = 1u << 1;
constexpr uint32_t kFlagAutomaticAltitude = 1u << 2;
constexpr uint32_t kFlagEasyLocationSwitch = 1u << 3;
constexpr uint32_t kFlagEmergencyDisable = 1u << 4;
constexpr uint32_t kFlagEngineReady = 1u << 5;
constexpr uint32_t kFlagJoystickEnabled = 1u << 6;

constexpr uint32_t kMovementNone = 0;
constexpr uint32_t kMovementWalking = 1;
constexpr uint32_t kMovementJogging = 2;

// This structure lives in one memfd owned by the Zygisk root companion. Writers
// use a seqlock and readers use bounded atomic snapshots. No callback path reads
// a file, waits on a socket, or takes a process-shared mutex.
struct alignas(64) SharedStateV2 {
    uint32_t magic;
    uint16_t version;
    uint16_t byte_size;
    alignas(8) uint64_t sequence;
    uint64_t generation;
    uint64_t updated_monotonic_ns;
    uint32_t flags;
    uint32_t movement_mode;
    uint64_t latitude_bits;
    uint64_t longitude_bits;
    uint64_t altitude_bits;
    uint32_t speed_bits;
    uint32_t bearing_bits;
    uint32_t accuracy_bits;
    uint32_t reserved0;
    uint64_t reserved[6];
};

struct StateSnapshot {
    uint64_t generation = 0;
    uint64_t updated_monotonic_ns = 0;
    uint32_t flags = 0;
    uint32_t movement_mode = kMovementNone;
    double latitude = 0.0;
    double longitude = 0.0;
    double altitude = 0.0;
    float speed = 0.0f;
    float bearing = 0.0f;
    float accuracy = 5.0f;
};

inline uint64_t double_to_bits(double value) {
    uint64_t bits = 0;
    static_assert(sizeof(bits) == sizeof(value));
    std::memcpy(&bits, &value, sizeof(bits));
    return bits;
}

inline double bits_to_double(uint64_t bits) {
    double value = 0.0;
    std::memcpy(&value, &bits, sizeof(value));
    return value;
}

inline uint32_t float_to_bits(float value) {
    uint32_t bits = 0;
    static_assert(sizeof(bits) == sizeof(value));
    std::memcpy(&bits, &value, sizeof(bits));
    return bits;
}

inline float bits_to_float(uint32_t bits) {
    float value = 0.0f;
    std::memcpy(&value, &bits, sizeof(value));
    return value;
}

inline uint64_t atomic_load_u64(const uint64_t* value, int order = __ATOMIC_ACQUIRE) {
    return __atomic_load_n(value, order);
}

inline uint32_t atomic_load_u32(const uint32_t* value, int order = __ATOMIC_ACQUIRE) {
    return __atomic_load_n(value, order);
}

inline void atomic_store_u64(uint64_t* target, uint64_t value, int order = __ATOMIC_RELEASE) {
    __atomic_store_n(target, value, order);
}

inline void atomic_store_u32(uint32_t* target, uint32_t value, int order = __ATOMIC_RELEASE) {
    __atomic_store_n(target, value, order);
}

inline bool validate_snapshot(const StateSnapshot& state) {
    const bool has_coordinates = (state.flags & kFlagHasCoordinates) != 0;
    const bool enabled = (state.flags & kFlagEnabled) != 0;
    if (!has_coordinates) {
        return !enabled;
    }
    if (!std::isfinite(state.latitude) || state.latitude < -90.0 || state.latitude > 90.0) {
        return false;
    }
    if (!std::isfinite(state.longitude) || state.longitude < -180.0 || state.longitude > 180.0) {
        return false;
    }
    // Android 16 LocationResult validation rejects non-mock 0,0 as incomplete.
    if (state.latitude == 0.0 && state.longitude == 0.0) {
        return false;
    }
    if ((state.flags & kFlagAutomaticAltitude) == 0
            && (!std::isfinite(state.altitude) || state.altitude < -500.0 || state.altitude > 9000.0)) {
        return false;
    }
    if (!std::isfinite(state.speed) || state.speed < 0.0f || state.speed > 150.0f) {
        return false;
    }
    if (!std::isfinite(state.bearing) || state.bearing < 0.0f || state.bearing >= 360.0f) {
        return false;
    }
    if (!std::isfinite(state.accuracy) || state.accuracy <= 0.0f || state.accuracy > 1000.0f) {
        return false;
    }
    if (state.movement_mode > kMovementJogging) {
        return false;
    }
    return true;
}

inline bool read_snapshot(const SharedStateV2* shared, StateSnapshot* output) {
    if (shared == nullptr || output == nullptr || shared->magic != kStateMagic
            || shared->version != kStateVersion || shared->byte_size != sizeof(SharedStateV2)) {
        return false;
    }

    for (int attempt = 0; attempt < 4; ++attempt) {
        const uint64_t before = atomic_load_u64(&shared->sequence);
        if ((before & 1u) != 0) {
            continue;
        }

        StateSnapshot snapshot;
        snapshot.generation = atomic_load_u64(&shared->generation, __ATOMIC_RELAXED);
        snapshot.updated_monotonic_ns = atomic_load_u64(&shared->updated_monotonic_ns, __ATOMIC_RELAXED);
        snapshot.flags = atomic_load_u32(&shared->flags, __ATOMIC_RELAXED);
        snapshot.movement_mode = atomic_load_u32(&shared->movement_mode, __ATOMIC_RELAXED);
        snapshot.latitude = bits_to_double(atomic_load_u64(&shared->latitude_bits, __ATOMIC_RELAXED));
        snapshot.longitude = bits_to_double(atomic_load_u64(&shared->longitude_bits, __ATOMIC_RELAXED));
        snapshot.altitude = bits_to_double(atomic_load_u64(&shared->altitude_bits, __ATOMIC_RELAXED));
        snapshot.speed = bits_to_float(atomic_load_u32(&shared->speed_bits, __ATOMIC_RELAXED));
        snapshot.bearing = bits_to_float(atomic_load_u32(&shared->bearing_bits, __ATOMIC_RELAXED));
        snapshot.accuracy = bits_to_float(atomic_load_u32(&shared->accuracy_bits, __ATOMIC_RELAXED));

        const uint64_t after = atomic_load_u64(&shared->sequence);
        if (before == after && (after & 1u) == 0) {
            *output = snapshot;
            return validate_snapshot(snapshot);
        }
    }
    return false;
}

inline void write_snapshot(SharedStateV2* shared, const StateSnapshot& state) {
    uint64_t sequence = atomic_load_u64(&shared->sequence, __ATOMIC_RELAXED);
    if ((sequence & 1u) != 0) {
        ++sequence;
    }
    atomic_store_u64(&shared->sequence, sequence + 1, __ATOMIC_RELEASE);
    atomic_store_u64(&shared->generation, state.generation, __ATOMIC_RELAXED);
    atomic_store_u64(&shared->updated_monotonic_ns, state.updated_monotonic_ns, __ATOMIC_RELAXED);
    atomic_store_u32(&shared->flags, state.flags, __ATOMIC_RELAXED);
    atomic_store_u32(&shared->movement_mode, state.movement_mode, __ATOMIC_RELAXED);
    atomic_store_u64(&shared->latitude_bits, double_to_bits(state.latitude), __ATOMIC_RELAXED);
    atomic_store_u64(&shared->longitude_bits, double_to_bits(state.longitude), __ATOMIC_RELAXED);
    atomic_store_u64(&shared->altitude_bits, double_to_bits(state.altitude), __ATOMIC_RELAXED);
    atomic_store_u32(&shared->speed_bits, float_to_bits(state.speed), __ATOMIC_RELAXED);
    atomic_store_u32(&shared->bearing_bits, float_to_bits(state.bearing), __ATOMIC_RELAXED);
    atomic_store_u32(&shared->accuracy_bits, float_to_bits(state.accuracy), __ATOMIC_RELAXED);
    atomic_store_u64(&shared->sequence, sequence + 2, __ATOMIC_RELEASE);
}

}  // namespace geoveil
