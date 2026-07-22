#include <sys/file.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

#include <cerrno>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fcntl.h>

#include "control_protocol.hpp"

namespace geoveil {
namespace {

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

uint64_t monotonic_ns() {
    timespec now{};
    if (clock_gettime(CLOCK_MONOTONIC, &now) != 0) return 1;
    const uint64_t value = static_cast<uint64_t>(now.tv_sec) * 1000000000ULL
            + static_cast<uint64_t>(now.tv_nsec);
    return value == 0 ? 1 : value;
}

bool parse_u64(const char* text, uint64_t* output) {
    if (text == nullptr || output == nullptr || *text == '\0' || *text == '-') return false;
    errno = 0;
    char* end = nullptr;
    const unsigned long long value = std::strtoull(text, &end, 10);
    if (errno != 0 || end == text || *end != '\0') return false;
    *output = static_cast<uint64_t>(value);
    return true;
}

bool parse_u32(const char* text, uint32_t* output) {
    uint64_t value = 0;
    if (!parse_u64(text, &value) || value > UINT32_MAX) return false;
    *output = static_cast<uint32_t>(value);
    return true;
}

bool parse_double(const char* text, double* output) {
    if (text == nullptr || output == nullptr || *text == '\0') return false;
    errno = 0;
    char* end = nullptr;
    const double value = std::strtod(text, &end);
    if (errno != 0 || end == text || *end != '\0' || !std::isfinite(value)) return false;
    *output = value;
    return true;
}

bool parse_float(const char* text, float* output) {
    double value = 0.0;
    if (!parse_double(text, &value) || value < -3.402823466e38 || value > 3.402823466e38) {
        return false;
    }
    *output = static_cast<float>(value);
    return std::isfinite(*output);
}

bool build_request(int argc, char** argv, ControlRequest* request) {
    if (request == nullptr || argc < 2) return false;
    request->nonce = monotonic_ns() ^ static_cast<uint64_t>(getpid());
    if (argc == 2 && std::strcmp(argv[1], "probe") == 0) {
        request->operation = static_cast<uint16_t>(Operation::kProbe);
        return true;
    }
    if (argc == 2 && std::strcmp(argv[1], "clear-emergency") == 0) {
        request->operation = static_cast<uint16_t>(Operation::kClearEmergency);
        return true;
    }
    if (argc == 2 && std::strcmp(argv[1], "disable-module") == 0) {
        request->operation = static_cast<uint16_t>(Operation::kDisableModule);
        return true;
    }
    if (argc != 11 || std::strcmp(argv[1], "publish") != 0) return false;
    request->operation = static_cast<uint16_t>(Operation::kPublish);
    return parse_u64(argv[2], &request->generation)
            && parse_u32(argv[3], &request->publish.flags)
            && parse_u32(argv[4], &request->publish.movement_mode)
            && parse_double(argv[5], &request->publish.latitude)
            && parse_double(argv[6], &request->publish.longitude)
            && parse_double(argv[7], &request->publish.altitude)
            && parse_float(argv[8], &request->publish.speed)
            && parse_float(argv[9], &request->publish.bearing)
            && parse_float(argv[10], &request->publish.accuracy);
}

bool send_request(const ControlRequest& request) {
    const int fd = open(kControlRequestTemp,
            O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0600);
    if (fd < 0) return false;
    const bool written = write_full(fd, &request, sizeof(request)) && fsync(fd) == 0;
    close(fd);
    return written && rename(kControlRequestTemp, kControlRequest) == 0;
}

bool wait_response(uint64_t nonce, ControlResponse* output) {
    for (int attempt = 0; attempt < 250; ++attempt) {
        const int fd = open(kControlResponse, O_RDONLY | O_CLOEXEC);
        if (fd >= 0) {
            ControlResponse response;
            const bool valid = read_full(fd, &response, sizeof(response))
                    && response.magic == kControlMagic
                    && response.version == kControlVersion
                    && response.nonce == nonce;
            close(fd);
            unlink(kControlResponse);
            if (valid) {
                *output = response;
                return true;
            }
        }
        usleep(20000);
    }
    return false;
}

void print_response(const ControlRequest& request, const ControlResponse& response) {
    const int status = response.response.status;
    const uint32_t movement = request.operation == static_cast<uint16_t>(Operation::kPublish)
            ? request.publish.movement_mode : 0;
    if (status == 0) {
        std::printf("OK %llu %u %u\n",
                static_cast<unsigned long long>(response.response.accepted_generation),
                response.response.flags, movement);
    } else {
        std::printf("ERR %d %llu %u %u\n", status,
                static_cast<unsigned long long>(response.response.accepted_generation),
                response.response.flags, movement);
    }
}

}  // namespace
}  // namespace geoveil

int main(int argc, char** argv) {
    if (getuid() != 0) {
        std::fprintf(stderr, "GeoVeil control requires root\n");
        return 13;
    }
    geoveil::ControlRequest request;
    if (!geoveil::build_request(argc, argv, &request)) {
        std::fprintf(stderr, "GeoVeil control command is invalid\n");
        return 2;
    }
    const int lock_fd = open(geoveil::kControlLock, O_RDWR | O_CREAT | O_CLOEXEC, 0600);
    if (lock_fd < 0 || flock(lock_fd, LOCK_EX) != 0) {
        if (lock_fd >= 0) close(lock_fd);
        std::fprintf(stderr, "GeoVeil control channel is unavailable\n");
        return 6;
    }
    unlink(geoveil::kControlResponse);
    geoveil::ControlResponse response;
    const bool completed = geoveil::send_request(request)
            && geoveil::wait_response(request.nonce, &response);
    (void)flock(lock_fd, LOCK_UN);
    close(lock_fd);
    if (!completed) {
        std::fprintf(stderr, "GeoVeil companion did not answer\n");
        return 6;
    }
    geoveil::print_response(request, response);
    return response.response.status == 0 ? 0 : 1;
}
