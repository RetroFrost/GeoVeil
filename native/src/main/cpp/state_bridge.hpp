#pragma once

#include <cstdint>

namespace zygisk {
struct Api;
}

namespace geoveil {

struct StateSnapshot {
    std::uint64_t generation = 0;
    bool bridge_connected = false;
    bool engine_active = false;
    bool emergency = false;
    bool enabled = false;
    bool has_coordinates = false;
    bool automatic_altitude = true;
    bool easy_location_switch = false;
    double latitude = 0.0;
    double longitude = 0.0;
    double altitude = 0.0;
    float speed = 0.0f;
    float bearing = 0.0f;
    float accuracy = 5.0f;
};

enum class CompanionRole : std::uint8_t {
    kShellBootstrap = 1,
    kSystemServerState = 2,
};

// Opens a Zygisk companion request while the caller is still in a
// pre-specialization callback. Shell bootstrap requests only ensure the root
// manager socket exists and are closed immediately. System-server requests
// return a retained state-stream descriptor, or -1 on failure.
int open_companion_channel(zygisk::Api* api, CompanionRole role);

// Starts the post-specialization system_server reader. All blocking socket work
// stays on its detached background thread; future hook paths only call
// read_state_snapshot().
void start_system_server_state_reader(int fd);

// Bounded lock-free snapshot read for the future location delivery hook.
bool read_state_snapshot(StateSnapshot* out);

// Root companion entry registered with Zygisk.
void root_companion_handler(int client);

}  // namespace geoveil
