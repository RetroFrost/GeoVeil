#include <sys/mman.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/types.h>
#include <unistd.h>

#include <algorithm>
#include <cerrno>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fcntl.h>
#include <mutex>
#include <time.h>

#include <linux/memfd.h>

#include "ipc.hpp"
#include "state.hpp"
#include "zygisk.hpp"

namespace geoveil {
namespace {

constexpr char kManagerArchive[] = "/data/adb/modules/geoveil/manager.apk";
constexpr char kStateDirectory[] = "/data/adb/geoveil";
constexpr char kGuardDirectory[] = "/data/adb/geoveil/guard";
constexpr char kInstallingMarker[] = "/data/adb/geoveil/guard/installing";
constexpr char kHealthyMarker[] = "/data/adb/geoveil/guard/healthy";
constexpr char kEmergencyMarker[] = "/data/adb/geoveil/guard/emergency_disable";
constexpr char kDisableMarker[] = "/data/adb/modules/geoveil/disable";
constexpr double kEarthRadiusMeters = 6378137.0;
constexpr double kPi = 3.14159265358979323846;

bool read_full(int fd, void* buffer, size_t size) {
    auto* bytes = static_cast<uint8_t*>(buffer);
    size_t offset = 0;
    while (offset < size) {
        const ssize_t count = TEMP_FAILURE_RETRY(read(fd, bytes + offset, size - offset));
        if (count <= 0) return false;
        offset += static_cast<size_t>(count);
    }
    return true;
}

bool write_full(int fd, const void* buffer, size_t size) {
    const auto* bytes = static_cast<const uint8_t*>(buffer);
    size_t offset = 0;
    while (offset < size) {
        const ssize_t count = TEMP_FAILURE_RETRY(write(fd, bytes + offset, size - offset));
        if (count <= 0) return false;
        offset += static_cast<size_t>(count);
    }
    return true;
}

uint64_t monotonic_ns() {
    timespec now{};
    if (clock_gettime(CLOCK_MONOTONIC, &now) != 0) return 0;
    return static_cast<uint64_t>(now.tv_sec) * 1000000000ULL
            + static_cast<uint64_t>(now.tv_nsec);
}

void ensure_directory(const char* path, mode_t mode) {
    if (mkdir(path, mode) != 0 && errno != EEXIST) return;
    (void)chmod(path, mode);
}

bool path_exists(const char* path) {
    return access(path, F_OK) == 0;
}

bool write_marker(const char* path, uint64_t generation, int32_t pid) {
    const int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0600);
    if (fd < 0) return false;
    char buffer[96];
    const int length = snprintf(buffer, sizeof(buffer), "%llu %d\n",
            static_cast<unsigned long long>(generation), pid);
    const bool ok = length > 0 && static_cast<size_t>(length) < sizeof(buffer)
            && write_full(fd, buffer, static_cast<size_t>(length));
    close(fd);
    return ok;
}

bool create_empty_marker(const char* path) {
    const int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0600);
    if (fd < 0) return false;
    close(fd);
    return true;
}

int create_state_fd() {
#if defined(__NR_memfd_create)
    const int fd = static_cast<int>(syscall(__NR_memfd_create, "geoveil-state-v2",
            MFD_CLOEXEC | MFD_ALLOW_SEALING));
#else
    const int fd = -1;
#endif
    if (fd < 0) return -1;
    if (ftruncate(fd, static_cast<off_t>(sizeof(SharedStateV2))) != 0) {
        close(fd);
        return -1;
    }
    return fd;
}

bool send_response_with_fds(int socket_fd, const Response& response,
        const int* fds, size_t fd_count) {
    if (fd_count > 2) return false;
    iovec io{};
    io.iov_base = const_cast<Response*>(&response);
    io.iov_len = sizeof(response);
    alignas(cmsghdr) char control[CMSG_SPACE(sizeof(int) * 2)]{};
    msghdr message{};
    message.msg_iov = &io;
    message.msg_iovlen = 1;
    if (fds != nullptr && fd_count > 0) {
        message.msg_control = control;
        message.msg_controllen = CMSG_SPACE(sizeof(int) * fd_count);
        cmsghdr* header = CMSG_FIRSTHDR(&message);
        header->cmsg_level = SOL_SOCKET;
        header->cmsg_type = SCM_RIGHTS;
        header->cmsg_len = CMSG_LEN(sizeof(int) * fd_count);
        std::memcpy(CMSG_DATA(header), fds, sizeof(int) * fd_count);
    }
    return TEMP_FAILURE_RETRY(sendmsg(socket_fd, &message, MSG_NOSIGNAL))
            == static_cast<ssize_t>(sizeof(response));
}

class CompanionState final {
public:
    CompanionState() {
        ensure_directory(kStateDirectory, 0700);
        ensure_directory(kGuardDirectory, 0700);
        state_fd_ = create_state_fd();
        if (state_fd_ < 0) return;
        shared_ = static_cast<SharedStateV2*>(mmap(nullptr, sizeof(SharedStateV2),
                PROT_READ | PROT_WRITE, MAP_SHARED, state_fd_, 0));
        if (shared_ == MAP_FAILED) {
            shared_ = nullptr;
            close(state_fd_);
            state_fd_ = -1;
            return;
        }
        std::memset(shared_, 0, sizeof(*shared_));
        shared_->magic = kStateMagic;
        shared_->version = kStateVersion;
        shared_->byte_size = sizeof(*shared_);
        StateSnapshot initial;
        initial.flags = kFlagAutomaticAltitude;
        initial.accuracy = 5.0f;
        initial.updated_monotonic_ns = monotonic_ns();
        write_snapshot(shared_, initial);
    }

    ~CompanionState() {
        if (shared_ != nullptr) munmap(shared_, sizeof(*shared_));
        if (state_fd_ >= 0) close(state_fd_);
    }

    bool ready() const { return state_fd_ >= 0 && shared_ != nullptr; }
    int state_fd() const { return state_fd_; }
    bool has_unfinished_generation() const {
        return path_exists(kInstallingMarker) && !path_exists(kHealthyMarker);
    }

    void enter_emergency() {
        std::lock_guard<std::mutex> lock(mutex_);
        enter_emergency_locked();
    }

    Response probe() {
        std::lock_guard<std::mutex> lock(mutex_);
        return response_for_current_locked(Status::kOk);
    }

    Response publish(uint64_t generation, const PublishPayload& payload) {
        std::lock_guard<std::mutex> lock(mutex_);
        StateSnapshot current;
        if (!read_snapshot(shared_, &current)) return error(Status::kIoError);
        if ((current.flags & kFlagEmergencyDisable) != 0) {
            return response(current, Status::kEmergencyDisabled);
        }
        if (generation <= current.generation) return response(current, Status::kStaleGeneration);

        StateSnapshot next;
        next.generation = generation;
        next.updated_monotonic_ns = monotonic_ns();
        next.flags = payload.flags & (kFlagEnabled | kFlagHasCoordinates
                | kFlagAutomaticAltitude | kFlagEasyLocationSwitch | kFlagJoystickEnabled);
        next.flags |= current.flags & (kFlagEngineReady | kFlagEmergencyDisable);
        next.movement_mode = payload.movement_mode;
        next.latitude = payload.latitude;
        next.longitude = payload.longitude;
        next.altitude = payload.altitude;
        next.speed = payload.speed;
        next.bearing = payload.bearing;
        next.accuracy = payload.accuracy;
        if (!validate_snapshot(next)) return response(current, Status::kInvalidState);
        write_snapshot(shared_, next);
        return response(next, Status::kOk);
    }

    Response move(uint64_t generation, const MovePayload& payload) {
        std::lock_guard<std::mutex> lock(mutex_);
        StateSnapshot current;
        if (!read_snapshot(shared_, &current)) return error(Status::kIoError);
        if ((current.flags & kFlagEmergencyDisable) != 0) {
            return response(current, Status::kEmergencyDisabled);
        }
        if ((current.flags & (kFlagEnabled | kFlagHasCoordinates))
                != (kFlagEnabled | kFlagHasCoordinates)) {
            return response(current, Status::kNotReady);
        }
        if (generation <= current.generation) return response(current, Status::kStaleGeneration);

        StateSnapshot next = current;
        next.generation = generation;
        next.updated_monotonic_ns = monotonic_ns();
        if (payload.active == 0 || payload.movement_mode == kMovementNone) {
            next.flags &= ~kFlagJoystickEnabled;
            next.movement_mode = kMovementNone;
            next.speed = 0.0f;
            last_move_ns_ = payload.event_monotonic_ns;
            write_snapshot(shared_, next);
            return response(next, Status::kOk);
        }
        if (payload.movement_mode != kMovementWalking
                && payload.movement_mode != kMovementJogging) {
            return response(current, Status::kInvalidState);
        }

        const double x = std::clamp(static_cast<double>(payload.normalized_x), -1.0, 1.0);
        const double y = std::clamp(static_cast<double>(payload.normalized_y), -1.0, 1.0);
        const double magnitude = std::min(1.0, std::hypot(x, y));
        const double intensity = std::min(1.0, magnitude / 0.5);
        const uint64_t now = payload.event_monotonic_ns != 0
                ? payload.event_monotonic_ns : monotonic_ns();
        double delta_seconds = 0.05;
        if (last_move_ns_ != 0 && now > last_move_ns_) {
            delta_seconds = static_cast<double>(now - last_move_ns_) / 1000000000.0;
        }
        last_move_ns_ = now;
        delta_seconds = std::clamp(delta_seconds, 0.0, 0.25);

        if (magnitude > 0.0001 && delta_seconds > 0.0) {
            const double unit_x = x / magnitude;
            const double unit_y = y / magnitude;
            const double meters_per_second = payload.movement_mode == kMovementJogging ? 3.0 : 1.4;
            const double distance = meters_per_second * intensity * delta_seconds;
            const double north = -unit_y * distance;
            const double east = unit_x * distance;
            const double latitude_radians = current.latitude * kPi / 180.0;
            const double latitude_delta = north / kEarthRadiusMeters;
            const double cosine = std::max(0.000001, std::abs(std::cos(latitude_radians)));
            const double longitude_delta = east / (kEarthRadiusMeters * cosine);
            next.latitude = std::clamp(current.latitude + latitude_delta * 180.0 / kPi,
                    -89.999999, 89.999999);
            next.longitude = current.longitude + longitude_delta * 180.0 / kPi;
            while (next.longitude > 180.0) next.longitude -= 360.0;
            while (next.longitude < -180.0) next.longitude += 360.0;
            double bearing = std::atan2(unit_x, -unit_y) * 180.0 / kPi;
            if (bearing < 0.0) bearing += 360.0;
            next.bearing = static_cast<float>(bearing);
            next.speed = static_cast<float>(meters_per_second * intensity);
        }
        next.flags |= kFlagJoystickEnabled;
        next.movement_mode = payload.movement_mode;
        if (!validate_snapshot(next)) return response(current, Status::kInvalidState);
        write_snapshot(shared_, next);
        return response(next, Status::kOk);
    }

    Response engine_begin(uint64_t generation, int32_t pid) {
        std::lock_guard<std::mutex> lock(mutex_);
        StateSnapshot current;
        if (!read_snapshot(shared_, &current)) return error(Status::kIoError);
        if (path_exists(kEmergencyMarker) || has_unfinished_generation()) {
            enter_emergency_locked();
            return response_for_current_locked(Status::kEmergencyDisabled);
        }
        unlink(kHealthyMarker);
        if (!write_marker(kInstallingMarker, generation, pid)) return error(Status::kIoError);
        current.flags &= ~kFlagEngineReady;
        current.generation = std::max(current.generation, generation);
        current.updated_monotonic_ns = monotonic_ns();
        write_snapshot(shared_, current);
        return response(current, Status::kOk);
    }

    Response engine_healthy(uint64_t generation, int32_t pid) {
        std::lock_guard<std::mutex> lock(mutex_);
        StateSnapshot current;
        if (!read_snapshot(shared_, &current)) return error(Status::kIoError);
        if (!write_marker(kHealthyMarker, generation, pid)) return error(Status::kIoError);
        unlink(kInstallingMarker);
        current.flags |= kFlagEngineReady;
        current.flags &= ~kFlagEmergencyDisable;
        current.generation = std::max(current.generation, generation);
        current.updated_monotonic_ns = monotonic_ns();
        write_snapshot(shared_, current);
        return response(current, Status::kOk);
    }

    Response engine_abort(uint64_t generation) {
        std::lock_guard<std::mutex> lock(mutex_);
        StateSnapshot current;
        if (!read_snapshot(shared_, &current)) return error(Status::kIoError);
        unlink(kInstallingMarker);
        unlink(kHealthyMarker);
        current.flags &= ~kFlagEngineReady;
        current.generation = std::max(current.generation, generation);
        current.updated_monotonic_ns = monotonic_ns();
        write_snapshot(shared_, current);
        return response(current, Status::kOk);
    }

    Response clear_emergency() {
        std::lock_guard<std::mutex> lock(mutex_);
        StateSnapshot current;
        if (!read_snapshot(shared_, &current)) return error(Status::kIoError);
        if ((current.flags & kFlagEnabled) != 0 || path_exists(kInstallingMarker)) {
            return response(current, Status::kNotReady);
        }
        unlink(kEmergencyMarker);
        unlink(kDisableMarker);
        current.flags &= ~kFlagEmergencyDisable;
        current.updated_monotonic_ns = monotonic_ns();
        write_snapshot(shared_, current);
        return response(current, Status::kOk);
    }

    Response disable_module() {
        std::lock_guard<std::mutex> lock(mutex_);
        enter_emergency_locked();
        return response_for_current_locked(Status::kOk);
    }

private:
    static Response error(Status status) {
        Response output;
        output.status = static_cast<int32_t>(status);
        return output;
    }

    static Response response(const StateSnapshot& snapshot, Status status) {
        Response output;
        output.status = static_cast<int32_t>(status);
        output.flags = snapshot.flags;
        output.accepted_generation = snapshot.generation;
        return output;
    }

    Response response_for_current_locked(Status status) const {
        StateSnapshot current;
        if (!read_snapshot(shared_, &current)) return error(Status::kIoError);
        return response(current, status);
    }

    void enter_emergency_locked() {
        create_empty_marker(kEmergencyMarker);
        create_empty_marker(kDisableMarker);
        StateSnapshot current;
        if (shared_ != nullptr && read_snapshot(shared_, &current)) {
            current.flags |= kFlagEmergencyDisable;
            current.flags &= ~(kFlagEnabled | kFlagEngineReady | kFlagJoystickEnabled);
            current.movement_mode = kMovementNone;
            current.speed = 0.0f;
            current.updated_monotonic_ns = monotonic_ns();
            write_snapshot(shared_, current);
        }
    }

    int state_fd_ = -1;
    SharedStateV2* shared_ = nullptr;
    uint64_t last_move_ns_ = 0;
    std::mutex mutex_;
};

CompanionState& companion_state() {
    static CompanionState state;
    return state;
}

Response handle_message(CompanionState& state, const ClientHello& hello,
        const MessageHeader& header, const void* payload) {
    if (header.magic != kIpcMagic || header.version != kIpcVersion) {
        Response output;
        output.status = static_cast<int32_t>(Status::kBadVersion);
        return output;
    }
    switch (static_cast<Operation>(header.operation)) {
        case Operation::kProbe:
            if (header.payload_size == 0) return state.probe();
            break;
        case Operation::kPublish:
            if (header.payload_size == sizeof(PublishPayload) && payload != nullptr) {
                return state.publish(header.generation,
                        *static_cast<const PublishPayload*>(payload));
            }
            break;
        case Operation::kMove:
            if (header.payload_size == sizeof(MovePayload) && payload != nullptr) {
                return state.move(header.generation, *static_cast<const MovePayload*>(payload));
            }
            break;
        case Operation::kEngineBegin:
            if (hello.role == static_cast<uint16_t>(ClientRole::kSystemServer)
                    && header.payload_size == 0) {
                return state.engine_begin(header.generation, hello.pid);
            }
            break;
        case Operation::kEngineHealthy:
            if (hello.role == static_cast<uint16_t>(ClientRole::kSystemServer)
                    && header.payload_size == 0) {
                return state.engine_healthy(header.generation, hello.pid);
            }
            break;
        case Operation::kEngineAbort:
            if (hello.role == static_cast<uint16_t>(ClientRole::kSystemServer)
                    && header.payload_size == 0) {
                return state.engine_abort(header.generation);
            }
            break;
        case Operation::kClearEmergency:
            if (hello.role == static_cast<uint16_t>(ClientRole::kShellManager)
                    && header.payload_size == 0) {
                return state.clear_emergency();
            }
            break;
        case Operation::kDisableModule:
            if (hello.role == static_cast<uint16_t>(ClientRole::kShellManager)
                    && header.payload_size == 0) {
                return state.disable_module();
            }
            break;
    }
    Response output;
    output.status = static_cast<int32_t>(Status::kBadMessage);
    return output;
}

}  // namespace

void companion_handler(int client) {
    CompanionState& state = companion_state();
    if (!state.ready()) {
        close(client);
        return;
    }
    ClientHello hello;
    if (!read_full(client, &hello, sizeof(hello)) || hello.magic != kIpcMagic
            || hello.version != kIpcVersion) {
        close(client);
        return;
    }

    Response initial = state.probe();
    int manager_fd = -1;
    int fds[2] = {-1, -1};
    size_t fd_count = 0;
    if (hello.role == static_cast<uint16_t>(ClientRole::kSystemServer)) {
        if (state.has_unfinished_generation() || path_exists(kEmergencyMarker)) {
            state.enter_emergency();
            initial = state.probe();
            initial.status = static_cast<int32_t>(Status::kEmergencyDisabled);
        }
        manager_fd = open(kManagerArchive, O_RDONLY | O_CLOEXEC);
        if (manager_fd < 0) {
            initial.status = static_cast<int32_t>(Status::kIoError);
        } else {
            fds[fd_count++] = state.state_fd();
            fds[fd_count++] = manager_fd;
        }
    }

    if (!send_response_with_fds(client, initial,
            fd_count == 0 ? nullptr : fds, fd_count)) {
        if (manager_fd >= 0) close(manager_fd);
        close(client);
        return;
    }
    if (manager_fd >= 0) close(manager_fd);

    uint8_t payload[sizeof(PublishPayload)]{};
    for (;;) {
        MessageHeader header;
        if (!read_full(client, &header, sizeof(header))) break;
        if (header.payload_size > sizeof(payload)) {
            Response bad;
            bad.status = static_cast<int32_t>(Status::kBadMessage);
            (void)write_full(client, &bad, sizeof(bad));
            break;
        }
        if (header.payload_size > 0 && !read_full(client, payload, header.payload_size)) break;
        Response output = handle_message(state, hello, header,
                header.payload_size > 0 ? payload : nullptr);
        if (!write_full(client, &output, sizeof(output))) break;
    }
    close(client);
}

}  // namespace geoveil

REGISTER_ZYGISK_COMPANION(geoveil::companion_handler)
