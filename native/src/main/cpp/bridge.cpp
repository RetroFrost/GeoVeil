#include "bridge.hpp"

#include <sys/socket.h>
#include <unistd.h>

#include <algorithm>
#include <atomic>
#include <cerrno>
#include <cstdint>
#include <cstring>

namespace geoveil {
namespace {

std::atomic<CompanionClient*> g_active_client{nullptr};

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

int64_t unavailable() {
    return static_cast<int64_t>(Status::kIoError);
}

jlong native_probe(JNIEnv*, jclass) {
    CompanionClient* client = CompanionClient::active();
    return client != nullptr ? client->probe() : unavailable();
}

jlong native_publish(JNIEnv*, jclass, jlong generation, jint flags, jint movement_mode,
        jdouble latitude, jdouble longitude, jdouble altitude, jfloat speed,
        jfloat bearing, jfloat accuracy) {
    CompanionClient* client = CompanionClient::active();
    if (client == nullptr) return unavailable();
    PublishPayload payload;
    payload.flags = static_cast<uint32_t>(flags);
    payload.movement_mode = static_cast<uint32_t>(movement_mode);
    payload.latitude = latitude;
    payload.longitude = longitude;
    payload.altitude = altitude;
    payload.speed = speed;
    payload.bearing = bearing;
    payload.accuracy = accuracy;
    const int64_t result = client->publish(static_cast<uint64_t>(generation), payload);
    if (result >= 0) client->set_last_movement_mode(movement_mode);
    return result;
}

jlong native_move(JNIEnv*, jclass, jlong generation, jfloat normalized_x,
        jfloat normalized_y, jint movement_mode, jboolean active, jlong event_ns) {
    CompanionClient* client = CompanionClient::active();
    if (client == nullptr) return unavailable();
    MovePayload payload;
    payload.normalized_x = normalized_x;
    payload.normalized_y = normalized_y;
    payload.movement_mode = static_cast<uint32_t>(movement_mode);
    payload.active = active == JNI_TRUE ? 1u : 0u;
    payload.event_monotonic_ns = static_cast<uint64_t>(event_ns);
    const int64_t result = client->move(static_cast<uint64_t>(generation), payload);
    if (result >= 0) client->set_last_movement_mode(active == JNI_TRUE ? movement_mode : 0);
    return result;
}

jint native_last_flags(JNIEnv*, jclass) {
    CompanionClient* client = CompanionClient::active();
    return client != nullptr ? client->last_flags() : 0;
}

jint native_last_movement_mode(JNIEnv*, jclass) {
    CompanionClient* client = CompanionClient::active();
    return client != nullptr ? client->last_movement_mode() : 0;
}

jlong native_clear_emergency(JNIEnv*, jclass) {
    CompanionClient* client = CompanionClient::active();
    return client != nullptr ? client->clear_emergency() : unavailable();
}

jlong native_disable_module(JNIEnv*, jclass) {
    CompanionClient* client = CompanionClient::active();
    return client != nullptr ? client->disable_module() : unavailable();
}

jobject load_class(JNIEnv* env, jobject loader, const char* name) {
    if (env == nullptr || loader == nullptr || name == nullptr) return nullptr;
    jclass loader_class = env->FindClass("java/lang/ClassLoader");
    if (loader_class == nullptr) return nullptr;
    jmethodID load = env->GetMethodID(loader_class, "loadClass", "(Ljava/lang/String;)Ljava/lang/Class;");
    if (load == nullptr) return nullptr;
    jstring class_name = env->NewStringUTF(name);
    if (class_name == nullptr) return nullptr;
    return env->CallObjectMethod(loader, load, class_name);
}

}  // namespace

CompanionClient::~CompanionClient() {
    CompanionClient* expected = this;
    g_active_client.compare_exchange_strong(expected, nullptr);
    if (socket_fd_ >= 0) close(socket_fd_);
}

void CompanionClient::adopt_socket(int socket_fd) {
    if (socket_fd_ >= 0) close(socket_fd_);
    socket_fd_ = socket_fd;
    if (socket_fd_ >= 0) {
        timeval timeout{};
        timeout.tv_sec = 0;
        timeout.tv_usec = 750000;
        setsockopt(socket_fd_, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout));
        setsockopt(socket_fd_, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout));
    }
}

bool CompanionClient::handshake(ClientRole role, int32_t pid, int32_t uid,
        int* state_fd, int* archive_fd) {
    if (socket_fd_ < 0) return false;
    ClientHello hello;
    hello.role = static_cast<uint16_t>(role);
    hello.pid = pid;
    hello.uid = uid;
    if (!write_full(socket_fd_, &hello, sizeof(hello))) return false;
    Response response;
    if (!receive_initial(&response, state_fd, archive_fd)) return false;
    if (response.magic != kIpcMagic || response.version != kIpcVersion) return false;
    last_flags_.store(static_cast<int>(response.flags));
    return response.status == static_cast<int32_t>(Status::kOk)
            || response.status == static_cast<int32_t>(Status::kEmergencyDisabled);
}

bool CompanionClient::receive_initial(Response* response, int* state_fd, int* archive_fd) {
    if (response == nullptr) return false;
    iovec io{};
    io.iov_base = response;
    io.iov_len = sizeof(*response);
    alignas(cmsghdr) char control[CMSG_SPACE(sizeof(int) * 2)]{};
    msghdr message{};
    message.msg_iov = &io;
    message.msg_iovlen = 1;
    message.msg_control = control;
    message.msg_controllen = sizeof(control);
    const ssize_t count = TEMP_FAILURE_RETRY(recvmsg(socket_fd_, &message, MSG_WAITALL));
    if (count != static_cast<ssize_t>(sizeof(*response))) return false;

    int received[2] = {-1, -1};
    size_t received_count = 0;
    for (cmsghdr* header = CMSG_FIRSTHDR(&message); header != nullptr;
            header = CMSG_NXTHDR(&message, header)) {
        if (header->cmsg_level != SOL_SOCKET || header->cmsg_type != SCM_RIGHTS) continue;
        const size_t bytes = header->cmsg_len - CMSG_LEN(0);
        const size_t count_fds = std::min<size_t>(2, bytes / sizeof(int));
        std::memcpy(received, CMSG_DATA(header), count_fds * sizeof(int));
        received_count = count_fds;
        break;
    }
    if (state_fd != nullptr && received_count > 0) {
        *state_fd = received[0];
    } else if (received_count > 0) {
        close(received[0]);
    }
    if (archive_fd != nullptr && received_count > 1) {
        *archive_fd = received[1];
    } else if (received_count > 1) {
        close(received[1]);
    }
    return true;
}

bool CompanionClient::register_manager_natives(JNIEnv* env, jobject class_loader) {
    if (env == nullptr || class_loader == nullptr) return false;
    jobject class_object = load_class(env, class_loader,
            "dev.retrofrost.geoveil.manager.NativeBridge");
    if (class_object == nullptr || env->ExceptionCheck()) {
        env->ExceptionClear();
        return false;
    }
    auto bridge_class = static_cast<jclass>(class_object);
    JNINativeMethod methods[] = {
        {const_cast<char*>("probe"), const_cast<char*>("()J"),
                reinterpret_cast<void*>(native_probe)},
        {const_cast<char*>("publish"), const_cast<char*>("(JIIDDDFFF)J"),
                reinterpret_cast<void*>(native_publish)},
        {const_cast<char*>("move"), const_cast<char*>("(JFFIZJ)J"),
                reinterpret_cast<void*>(native_move)},
        {const_cast<char*>("lastFlags"), const_cast<char*>("()I"),
                reinterpret_cast<void*>(native_last_flags)},
        {const_cast<char*>("lastMovementMode"), const_cast<char*>("()I"),
                reinterpret_cast<void*>(native_last_movement_mode)},
        {const_cast<char*>("clearEmergency"), const_cast<char*>("()J"),
                reinterpret_cast<void*>(native_clear_emergency)},
        {const_cast<char*>("disableModule"), const_cast<char*>("()J"),
                reinterpret_cast<void*>(native_disable_module)},
    };
    if (env->RegisterNatives(bridge_class, methods,
            static_cast<jint>(sizeof(methods) / sizeof(methods[0]))) != JNI_OK) {
        env->ExceptionClear();
        return false;
    }
    set_active(this);
    return true;
}

int64_t CompanionClient::transact(Operation operation, uint64_t generation,
        const void* payload, uint32_t payload_size) {
    std::lock_guard<std::mutex> lock(io_mutex_);
    if (socket_fd_ < 0) return unavailable();
    MessageHeader header;
    header.operation = static_cast<uint16_t>(operation);
    header.payload_size = payload_size;
    header.generation = generation;
    if (!write_full(socket_fd_, &header, sizeof(header))) return unavailable();
    if (payload_size > 0 && (payload == nullptr || !write_full(socket_fd_, payload, payload_size))) {
        return unavailable();
    }
    Response response;
    if (!read_full(socket_fd_, &response, sizeof(response))) return unavailable();
    if (response.magic != kIpcMagic || response.version != kIpcVersion) {
        return static_cast<int64_t>(Status::kBadVersion);
    }
    last_flags_.store(static_cast<int>(response.flags));
    if (response.status != static_cast<int32_t>(Status::kOk)) {
        return static_cast<int64_t>(response.status);
    }
    return static_cast<int64_t>(response.accepted_generation);
}

int64_t CompanionClient::probe() {
    return transact(Operation::kProbe, 0, nullptr, 0);
}

int64_t CompanionClient::publish(uint64_t generation, const PublishPayload& payload) {
    return transact(Operation::kPublish, generation, &payload, sizeof(payload));
}

int64_t CompanionClient::move(uint64_t generation, const MovePayload& payload) {
    return transact(Operation::kMove, generation, &payload, sizeof(payload));
}

int64_t CompanionClient::engine_begin(uint64_t generation) {
    return transact(Operation::kEngineBegin, generation, nullptr, 0);
}

int64_t CompanionClient::engine_healthy(uint64_t generation) {
    return transact(Operation::kEngineHealthy, generation, nullptr, 0);
}

int64_t CompanionClient::clear_emergency() {
    return transact(Operation::kClearEmergency, 0, nullptr, 0);
}

int64_t CompanionClient::disable_module() {
    return transact(Operation::kDisableModule, 0, nullptr, 0);
}

int CompanionClient::last_flags() const {
    return last_flags_.load();
}

int CompanionClient::last_movement_mode() const {
    return last_movement_mode_.load();
}

void CompanionClient::set_last_movement_mode(int mode) {
    last_movement_mode_.store(mode);
}

bool CompanionClient::connected() const {
    return socket_fd_ >= 0;
}

void CompanionClient::set_active(CompanionClient* client) {
    g_active_client.store(client);
}

CompanionClient* CompanionClient::active() {
    return g_active_client.load();
}

}  // namespace geoveil
