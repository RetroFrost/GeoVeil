#pragma once

#include <jni.h>

#include <cstdint>

namespace geoveil {

struct SharedStateV2;
class CompanionClient;

// Installs every required Android 16 delivery hook or installs none. The archive
// fd contains the DEX helper classes built from manager/src/main/java.
bool install_location_engine(JNIEnv* env, JavaVM* vm, int archive_fd,
        const SharedStateV2* shared_state, CompanionClient* companion,
        uint64_t generation);

}  // namespace geoveil
