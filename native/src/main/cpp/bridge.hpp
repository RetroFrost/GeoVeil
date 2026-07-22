#pragma once

#include <jni.h>

#include <atomic>
#include <cstdint>
#include <mutex>

#include "ipc.hpp"

namespace geoveil {

class CompanionClient final {
public:
    CompanionClient() = default;
    ~CompanionClient();

    CompanionClient(const CompanionClient&) = delete;
    CompanionClient& operator=(const CompanionClient&) = delete;

    void adopt_socket(int socket_fd);
    bool handshake(ClientRole role, int32_t pid, int32_t uid, int* state_fd, int* archive_fd);
    bool register_manager_natives(JNIEnv* env, jobject class_loader);

    int64_t probe();
    int64_t publish(uint64_t generation, const PublishPayload& payload);
    int64_t move(uint64_t generation, const MovePayload& payload);
    int64_t engine_begin(uint64_t generation);
    int64_t engine_healthy(uint64_t generation);
    int64_t clear_emergency();
    int64_t disable_module();

    int last_flags() const;
    int last_movement_mode() const;
    void set_last_movement_mode(int mode);
    bool connected() const;

    static void set_active(CompanionClient* client);
    static CompanionClient* active();

private:
    int64_t transact(Operation operation, uint64_t generation,
            const void* payload, uint32_t payload_size);
    bool receive_initial(Response* response, int* state_fd, int* archive_fd);

    int socket_fd_ = -1;
    mutable std::mutex io_mutex_;
    std::atomic<int> last_flags_{0};
    std::atomic<int> last_movement_mode_{0};
};

}  // namespace geoveil
