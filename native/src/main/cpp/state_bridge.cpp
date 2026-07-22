#include <sys/types.h>

#include "state_bridge.hpp"
#include "zygisk.hpp"

#include <atomic>
#include <cerrno>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <fcntl.h>
#include <pthread.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <sys/un.h>
#include <unistd.h>

namespace geoveil {
namespace {

constexpr std::uint32_t kMagic = 0x47565354U;  // GVST
constexpr std::uint16_t kVersion = 1;
constexpr std::uint16_t kOpStatus = 1;
constexpr std::uint16_t kOpPublish = 2;
constexpr std::uint16_t kPacketState = 0x100;

constexpr std::uint16_t kStatusOk = 0;
constexpr std::uint16_t kStatusInvalid = 1;
constexpr std::uint16_t kStatusStale = 2;
constexpr std::uint16_t kStatusEmergency = 3;
constexpr std::uint16_t kStatusProtocol = 4;

constexpr std::uint32_t kFlagBridgeReady = 1U << 0;
constexpr std::uint32_t kFlagEngineActive = 1U << 1;
constexpr std::uint32_t kFlagEmergency = 1U << 2;
constexpr std::uint32_t kFlagEnabled = 1U << 3;
constexpr std::uint32_t kFlagHasCoordinates = 1U << 4;
constexpr std::uint32_t kFlagAutomaticAltitude = 1U << 5;
constexpr std::uint32_t kFlagEasyLocationSwitch = 1U << 6;

constexpr char kManagerSocketName[] = "geoveil.manager.v1";
constexpr char kEmergencyPath[] = "/data/adb/geoveil/guard/emergency_disable";
constexpr uid_t kRootUid = 0;
constexpr uid_t kShellUid = 2000;

pthread_once_t g_server_once = PTHREAD_ONCE_INIT;
pthread_mutex_t g_state_mutex = PTHREAD_MUTEX_INITIALIZER;
pthread_cond_t g_state_changed = PTHREAD_COND_INITIALIZER;
std::atomic<bool> g_server_ready{false};
std::atomic<bool> g_engine_active{false};
std::atomic<int> g_system_server_fd{-1};
std::uint64_t g_last_request_generation = 0;
StateSnapshot g_companion_state{};

std::atomic<std::uint64_t> g_snapshot_sequence{0};
StateSnapshot g_system_server_snapshot{};

bool read_full(int fd, void* buffer, std::size_t size) {
    auto* cursor = static_cast<std::uint8_t*>(buffer);
    std::size_t remaining = size;
    while (remaining > 0) {
        const ssize_t count = read(fd, cursor, remaining);
        if (count == 0) return false;
        if (count < 0) {
            if (errno == EINTR) continue;
            return false;
        }
        cursor += static_cast<std::size_t>(count);
        remaining -= static_cast<std::size_t>(count);
    }
    return true;
}

bool write_full(int fd, const void* buffer, std::size_t size) {
    const auto* cursor = static_cast<const std::uint8_t*>(buffer);
    std::size_t remaining = size;
    while (remaining > 0) {
        const ssize_t count = write(fd, cursor, remaining);
        if (count < 0) {
            if (errno == EINTR) continue;
            return false;
        }
        cursor += static_cast<std::size_t>(count);
        remaining -= static_cast<std::size_t>(count);
    }
    return true;
}

bool read_u16(int fd, std::uint16_t* value) {
    std::uint8_t bytes[2]{};
    if (!read_full(fd, bytes, sizeof(bytes))) return false;
    *value = static_cast<std::uint16_t>(
            (static_cast<std::uint16_t>(bytes[0]) << 8U) |
            static_cast<std::uint16_t>(bytes[1]));
    return true;
}

bool read_u32(int fd, std::uint32_t* value) {
    std::uint8_t bytes[4]{};
    if (!read_full(fd, bytes, sizeof(bytes))) return false;
    *value = (static_cast<std::uint32_t>(bytes[0]) << 24U) |
             (static_cast<std::uint32_t>(bytes[1]) << 16U) |
             (static_cast<std::uint32_t>(bytes[2]) << 8U) |
             static_cast<std::uint32_t>(bytes[3]);
    return true;
}

bool read_u64(int fd, std::uint64_t* value) {
    std::uint8_t bytes[8]{};
    if (!read_full(fd, bytes, sizeof(bytes))) return false;
    std::uint64_t result = 0;
    for (std::uint8_t byte : bytes) {
        result = (result << 8U) | static_cast<std::uint64_t>(byte);
    }
    *value = result;
    return true;
}

bool write_u16(int fd, std::uint16_t value) {
    const std::uint8_t bytes[] = {
            static_cast<std::uint8_t>((value >> 8U) & 0xffU),
            static_cast<std::uint8_t>(value & 0xffU),
    };
    return write_full(fd, bytes, sizeof(bytes));
}

bool write_u32(int fd, std::uint32_t value) {
    const std::uint8_t bytes[] = {
            static_cast<std::uint8_t>((value >> 24U) & 0xffU),
            static_cast<std::uint8_t>((value >> 16U) & 0xffU),
            static_cast<std::uint8_t>((value >> 8U) & 0xffU),
            static_cast<std::uint8_t>(value & 0xffU),
    };
    return write_full(fd, bytes, sizeof(bytes));
}

bool write_u64(int fd, std::uint64_t value) {
    std::uint8_t bytes[8]{};
    for (int index = 7; index >= 0; --index) {
        bytes[index] = static_cast<std::uint8_t>(value & 0xffU);
        value >>= 8U;
    }
    return write_full(fd, bytes, sizeof(bytes));
}

bool read_double(int fd, double* value) {
    std::uint64_t bits = 0;
    if (!read_u64(fd, &bits)) return false;
    static_assert(sizeof(bits) == sizeof(*value));
    std::memcpy(value, &bits, sizeof(bits));
    return true;
}

bool read_float(int fd, float* value) {
    std::uint32_t bits = 0;
    if (!read_u32(fd, &bits)) return false;
    static_assert(sizeof(bits) == sizeof(*value));
    std::memcpy(value, &bits, sizeof(bits));
    return true;
}

bool write_double(int fd, double value) {
    std::uint64_t bits = 0;
    static_assert(sizeof(bits) == sizeof(value));
    std::memcpy(&bits, &value, sizeof(bits));
    return write_u64(fd, bits);
}

bool write_float(int fd, float value) {
    std::uint32_t bits = 0;
    static_assert(sizeof(bits) == sizeof(value));
    std::memcpy(&bits, &value, sizeof(bits));
    return write_u32(fd, bits);
}

void set_socket_timeout(int fd, long milliseconds) {
    timeval timeout{};
    timeout.tv_sec = milliseconds / 1000;
    timeout.tv_usec = (milliseconds % 1000) * 1000;
    (void)setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout));
    (void)setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout));
}

bool emergency_active() {
    return access(kEmergencyPath, F_OK) == 0;
}

bool finite_in_range(double value, double minimum, double maximum) {
    return std::isfinite(value) && value >= minimum && value <= maximum;
}

bool finite_in_range(float value, float minimum, float maximum) {
    return std::isfinite(value) && value >= minimum && value <= maximum;
}

bool validate_state(const StateSnapshot& state) {
    if (state.enabled && !state.has_coordinates) return false;
    if (state.has_coordinates) {
        if (!finite_in_range(state.latitude, -90.0, 90.0)) return false;
        if (!finite_in_range(state.longitude, -180.0, 180.0)) return false;
    }
    if (!state.automatic_altitude && !finite_in_range(state.altitude, -500.0, 9000.0)) {
        return false;
    }
    if (!finite_in_range(state.speed, 0.0f, 150.0f)) return false;
    if (!std::isfinite(state.bearing) || state.bearing < 0.0f || state.bearing >= 360.0f) {
        return false;
    }
    return finite_in_range(state.accuracy, 0.0001f, 1000.0f);
}

std::uint32_t flags_for_state(const StateSnapshot& state) {
    std::uint32_t flags = 0;
    if (g_server_ready.load(std::memory_order_acquire)) flags |= kFlagBridgeReady;
    if (state.engine_active) flags |= kFlagEngineActive;
    if (state.emergency) flags |= kFlagEmergency;
    if (state.enabled) flags |= kFlagEnabled;
    if (state.has_coordinates) flags |= kFlagHasCoordinates;
    if (state.automatic_altitude) flags |= kFlagAutomaticAltitude;
    if (state.easy_location_switch) flags |= kFlagEasyLocationSwitch;
    return flags;
}

bool write_manager_response(
        int fd,
        std::uint16_t status,
        std::uint64_t generation,
        const StateSnapshot& state) {
    return write_u32(fd, kMagic) &&
           write_u16(fd, kVersion) &&
           write_u16(fd, status) &&
           write_u64(fd, generation) &&
           write_u32(fd, flags_for_state(state));
}

bool read_publish_body(int fd, StateSnapshot* state) {
    std::uint32_t flags = 0;
    if (!read_u32(fd, &flags)) return false;
    state->enabled = (flags & (1U << 0)) != 0;
    state->has_coordinates = (flags & (1U << 1)) != 0;
    state->automatic_altitude = (flags & (1U << 2)) != 0;
    state->easy_location_switch = (flags & (1U << 3)) != 0;
    return read_double(fd, &state->latitude) &&
           read_double(fd, &state->longitude) &&
           read_double(fd, &state->altitude) &&
           read_float(fd, &state->speed) &&
           read_float(fd, &state->bearing) &&
           read_float(fd, &state->accuracy);
}

bool peer_is_allowed(int fd) {
    ucred credentials{};
    socklen_t size = sizeof(credentials);
    if (getsockopt(fd, SOL_SOCKET, SO_PEERCRED, &credentials, &size) != 0) return false;
    return credentials.uid == kRootUid || credentials.uid == kShellUid;
}

void handle_manager_client(int fd) {
    set_socket_timeout(fd, 1000);
    if (!peer_is_allowed(fd)) {
        close(fd);
        return;
    }

    std::uint32_t magic = 0;
    std::uint16_t version = 0;
    std::uint16_t operation = 0;
    std::uint64_t request_generation = 0;
    if (!read_u32(fd, &magic) || !read_u16(fd, &version) || !read_u16(fd, &operation) ||
        !read_u64(fd, &request_generation)) {
        close(fd);
        return;
    }

    pthread_mutex_lock(&g_state_mutex);
    StateSnapshot response_state = g_companion_state;
    response_state.bridge_connected = true;
    response_state.engine_active = g_engine_active.load(std::memory_order_acquire);
    response_state.emergency = emergency_active();
    if (response_state.emergency || !response_state.engine_active) {
        response_state.enabled = false;
    }

    std::uint16_t status = kStatusOk;
    if (magic != kMagic || version != kVersion) {
        status = kStatusProtocol;
    } else if (operation == kOpStatus) {
        // Status requests never modify the accepted generation.
    } else if (operation == kOpPublish) {
        StateSnapshot requested{};
        requested.generation = request_generation;
        requested.bridge_connected = true;
        requested.engine_active = response_state.engine_active;
        requested.emergency = response_state.emergency;
        if (!read_publish_body(fd, &requested) || !validate_state(requested)) {
            status = kStatusInvalid;
        } else if (request_generation <= g_last_request_generation) {
            status = kStatusStale;
        } else if (requested.emergency && requested.enabled) {
            status = kStatusEmergency;
        } else {
            g_last_request_generation = request_generation;
            requested.enabled = requested.enabled && requested.engine_active && !requested.emergency;
            g_companion_state = requested;
            response_state = requested;
            pthread_cond_broadcast(&g_state_changed);
        }
    } else {
        status = kStatusProtocol;
    }

    const std::uint64_t accepted_generation = g_companion_state.generation;
    (void)write_manager_response(fd, status, accepted_generation, response_state);
    pthread_mutex_unlock(&g_state_mutex);
    close(fd);
}

void* manager_client_thread(void* opaque) {
    const int fd = *static_cast<int*>(opaque);
    std::free(opaque);
    handle_manager_client(fd);
    return nullptr;
}

void* manager_server_thread(void*) {
    const int server = socket(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC, 0);
    if (server < 0) return nullptr;

    sockaddr_un address{};
    address.sun_family = AF_UNIX;
    address.sun_path[0] = '\0';
    constexpr std::size_t name_length = sizeof(kManagerSocketName) - 1;
    static_assert(name_length + 1 < sizeof(address.sun_path));
    std::memcpy(address.sun_path + 1, kManagerSocketName, name_length);
    const socklen_t address_length = static_cast<socklen_t>(
            offsetof(sockaddr_un, sun_path) + 1 + name_length);

    if (bind(server, reinterpret_cast<sockaddr*>(&address), address_length) != 0 ||
        listen(server, 4) != 0) {
        close(server);
        return nullptr;
    }

    g_server_ready.store(true, std::memory_order_release);
    for (;;) {
        const int client = accept(server, nullptr, nullptr);
        if (client < 0) {
            if (errno == EINTR) continue;
            break;
        }
        auto* client_holder = static_cast<int*>(std::malloc(sizeof(int)));
        if (client_holder == nullptr) {
            close(client);
            continue;
        }
        *client_holder = client;
        pthread_t thread{};
        if (pthread_create(&thread, nullptr, manager_client_thread, client_holder) == 0) {
            pthread_detach(thread);
        } else {
            std::free(client_holder);
            close(client);
        }
    }

    g_server_ready.store(false, std::memory_order_release);
    close(server);
    return nullptr;
}

void start_manager_server_once() {
    pthread_t thread{};
    if (pthread_create(&thread, nullptr, manager_server_thread, nullptr) == 0) {
        pthread_detach(thread);
    }
}

void ensure_manager_server() {
    (void)pthread_once(&g_server_once, start_manager_server_once);
}

bool write_state_packet(int fd, const StateSnapshot& state) {
    return write_u32(fd, kMagic) &&
           write_u16(fd, kVersion) &&
           write_u16(fd, kPacketState) &&
           write_u64(fd, state.generation) &&
           write_u32(fd, flags_for_state(state)) &&
           write_double(fd, state.latitude) &&
           write_double(fd, state.longitude) &&
           write_double(fd, state.altitude) &&
           write_float(fd, state.speed) &&
           write_float(fd, state.bearing) &&
           write_float(fd, state.accuracy);
}

void stream_state_to_system_server(int client) {
    const int previous = g_system_server_fd.exchange(client, std::memory_order_acq_rel);
    if (previous >= 0 && previous != client) {
        (void)shutdown(previous, SHUT_RDWR);
    }

    g_engine_active.store(false, std::memory_order_release);
    std::uint64_t sent_generation = UINT64_MAX;
    for (;;) {
        pthread_mutex_lock(&g_state_mutex);
        while (sent_generation == g_companion_state.generation &&
               g_system_server_fd.load(std::memory_order_acquire) == client) {
            pthread_cond_wait(&g_state_changed, &g_state_mutex);
        }
        StateSnapshot state = g_companion_state;
        state.bridge_connected = true;
        state.engine_active = false;
        state.emergency = emergency_active();
        state.enabled = false;
        pthread_mutex_unlock(&g_state_mutex);

        if (g_system_server_fd.load(std::memory_order_acquire) != client ||
            !write_state_packet(client, state)) {
            break;
        }
        sent_generation = state.generation;
    }

    int expected = client;
    (void)g_system_server_fd.compare_exchange_strong(expected, -1, std::memory_order_acq_rel);
    close(client);
}

void publish_local_snapshot(const StateSnapshot& state) {
    g_snapshot_sequence.fetch_add(1, std::memory_order_acq_rel);
    g_system_server_snapshot = state;
    g_snapshot_sequence.fetch_add(1, std::memory_order_release);
}

bool read_state_packet(int fd, StateSnapshot* state) {
    std::uint32_t magic = 0;
    std::uint16_t version = 0;
    std::uint16_t packet = 0;
    std::uint32_t flags = 0;
    if (!read_u32(fd, &magic) || !read_u16(fd, &version) || !read_u16(fd, &packet) ||
        !read_u64(fd, &state->generation) || !read_u32(fd, &flags)) {
        return false;
    }
    if (magic != kMagic || version != kVersion || packet != kPacketState) return false;

    state->bridge_connected = (flags & kFlagBridgeReady) != 0;
    state->engine_active = (flags & kFlagEngineActive) != 0;
    state->emergency = (flags & kFlagEmergency) != 0;
    state->enabled = (flags & kFlagEnabled) != 0;
    state->has_coordinates = (flags & kFlagHasCoordinates) != 0;
    state->automatic_altitude = (flags & kFlagAutomaticAltitude) != 0;
    state->easy_location_switch = (flags & kFlagEasyLocationSwitch) != 0;
    if (!read_double(fd, &state->latitude) || !read_double(fd, &state->longitude) ||
        !read_double(fd, &state->altitude) || !read_float(fd, &state->speed) ||
        !read_float(fd, &state->bearing) || !read_float(fd, &state->accuracy)) {
        return false;
    }
    if (!validate_state(*state)) return false;
    if (state->emergency || !state->engine_active) state->enabled = false;
    return true;
}

void* system_server_reader_thread(void* opaque) {
    const int fd = *static_cast<int*>(opaque);
    std::free(opaque);

    StateSnapshot state{};
    state.bridge_connected = true;
    publish_local_snapshot(state);
    while (read_state_packet(fd, &state)) {
        publish_local_snapshot(state);
    }

    state = StateSnapshot{};
    state.bridge_connected = false;
    state.enabled = false;
    publish_local_snapshot(state);
    close(fd);
    return nullptr;
}

}  // namespace

int open_companion_channel(zygisk::Api* api, CompanionRole role) {
    if (api == nullptr) return -1;
    const int fd = api->connectCompanion();
    if (fd < 0) return -1;

    const std::uint8_t role_byte = static_cast<std::uint8_t>(role);
    if (!write_full(fd, &role_byte, sizeof(role_byte))) {
        close(fd);
        return -1;
    }

    if (role == CompanionRole::kShellBootstrap) {
        close(fd);
        return -1;
    }

    const int flags = fcntl(fd, F_GETFD);
    if (flags >= 0) (void)fcntl(fd, F_SETFD, flags & ~FD_CLOEXEC);
    return fd;
}

void start_system_server_state_reader(int fd) {
    if (fd < 0) return;
    auto* holder = static_cast<int*>(std::malloc(sizeof(int)));
    if (holder == nullptr) {
        close(fd);
        return;
    }
    *holder = fd;
    pthread_t thread{};
    if (pthread_create(&thread, nullptr, system_server_reader_thread, holder) == 0) {
        pthread_detach(thread);
    } else {
        std::free(holder);
        close(fd);
    }
}

bool read_state_snapshot(StateSnapshot* out) {
    if (out == nullptr) return false;
    for (int attempt = 0; attempt < 8; ++attempt) {
        const std::uint64_t before = g_snapshot_sequence.load(std::memory_order_acquire);
        if ((before & 1U) != 0) continue;
        const StateSnapshot candidate = g_system_server_snapshot;
        const std::uint64_t after = g_snapshot_sequence.load(std::memory_order_acquire);
        if (before == after && (after & 1U) == 0) {
            *out = candidate;
            return true;
        }
    }
    return false;
}

void root_companion_handler(int client) {
    ensure_manager_server();
    set_socket_timeout(client, 2000);
    std::uint8_t role = 0;
    if (!read_full(client, &role, sizeof(role))) {
        close(client);
        return;
    }
    if (role == static_cast<std::uint8_t>(CompanionRole::kSystemServerState)) {
        set_socket_timeout(client, 0);
        stream_state_to_system_server(client);
        return;
    }
    close(client);
}

}  // namespace geoveil
