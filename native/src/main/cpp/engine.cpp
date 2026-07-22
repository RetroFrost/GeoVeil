#include "engine.hpp"

#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

#include <algorithm>
#include <atomic>
#include <cstdint>
#include <cstring>
#include <string>
#include <string_view>
#include <vector>

#include "bridge.hpp"
#include "dobby.h"
#include "lsplant.hpp"
#include "state.hpp"

namespace geoveil {
namespace {

constexpr const char* kTransportClasses[] = {
    "com/android/server/location/provider/LocationProviderManager$LocationListenerTransport",
    "com/android/server/location/provider/LocationProviderManager$LocationPendingIntentTransport",
    "com/android/server/location/provider/LocationProviderManager$GetCurrentLocationTransport",
};
constexpr char kDeliveryMethodName[] = "deliverOnLocationChanged";
constexpr char kLocationResultName[] = "android.location.LocationResult";
constexpr char kDeliveryHookClass[] = "dev.retrofrost.geoveil.engine.DeliveryHook";

std::atomic<const SharedStateV2*> g_shared_state{nullptr};
std::atomic<bool> g_hooks_committed{false};
void* g_dex_mapping = nullptr;
size_t g_dex_mapping_size = 0;
jobject g_dex_loader = nullptr;
std::vector<jobject> g_target_methods;
std::vector<jobject> g_hooker_objects;
std::vector<jobject> g_backup_methods;

struct LocationCache {
    jclass location_result_class = nullptr;
    jclass location_class = nullptr;
    jclass array_list_class = nullptr;
    jmethodID result_size = nullptr;
    jmethodID result_get = nullptr;
    jmethodID result_create = nullptr;
    jmethodID location_copy = nullptr;
    jmethodID set_latitude = nullptr;
    jmethodID set_longitude = nullptr;
    jmethodID set_altitude = nullptr;
    jmethodID set_speed = nullptr;
    jmethodID set_bearing = nullptr;
    jmethodID set_accuracy = nullptr;
    jmethodID array_list_constructor = nullptr;
    jmethodID array_list_add = nullptr;
};

LocationCache g_location;

bool clear_exception(JNIEnv* env) {
    if (env == nullptr || !env->ExceptionCheck()) return false;
    env->ExceptionClear();
    return true;
}

void* inline_hook(void* target, void* replacement) {
    void* backup = nullptr;
    return DobbyHook(target, replacement, &backup) == 0 ? backup : nullptr;
}

bool inline_unhook(void* target) {
    return DobbyDestroy(target) == 0;
}

void* resolve_art_symbol(std::string_view name) {
    std::string symbol(name);
    void* result = DobbySymbolResolver("libart.so", symbol.c_str());
    if (result == nullptr) result = DobbySymbolResolver(nullptr, symbol.c_str());
    return result;
}

bool initialize_lsplant(JNIEnv* env) {
    static std::atomic<int> state{0};
    int expected = 0;
    if (state.compare_exchange_strong(expected, 1)) {
        lsplant::InitInfo info;
        info.inline_hooker = inline_hook;
        info.inline_unhooker = inline_unhook;
        info.art_symbol_resolver = resolve_art_symbol;
        info.generated_class_name = "LGeoVeilHook_";
        info.generated_source_name = "GeoVeil";
        info.generated_field_name = "context";
        info.generated_method_name = "deliver";
        state.store(lsplant::Init(env, info) ? 2 : -1);
    } else {
        while (state.load() == 1) sched_yield();
    }
    return state.load() == 2;
}

jobject system_class_loader(JNIEnv* env) {
    jclass class_loader = env->FindClass("java/lang/ClassLoader");
    if (class_loader == nullptr || clear_exception(env)) return nullptr;
    jmethodID get_system = env->GetStaticMethodID(class_loader, "getSystemClassLoader",
            "()Ljava/lang/ClassLoader;");
    if (get_system == nullptr || clear_exception(env)) return nullptr;
    jobject loader = env->CallStaticObjectMethod(class_loader, get_system);
    if (clear_exception(env)) return nullptr;
    return loader;
}

jobject create_in_memory_loader(JNIEnv* env, int archive_fd) {
    struct stat archive_stat{};
    if (fstat(archive_fd, &archive_stat) != 0 || archive_stat.st_size <= 0) return nullptr;
    void* mapping = mmap(nullptr, static_cast<size_t>(archive_stat.st_size), PROT_READ,
            MAP_PRIVATE, archive_fd, 0);
    if (mapping == MAP_FAILED) return nullptr;
    jobject buffer = env->NewDirectByteBuffer(mapping, archive_stat.st_size);
    if (buffer == nullptr || clear_exception(env)) {
        munmap(mapping, static_cast<size_t>(archive_stat.st_size));
        return nullptr;
    }
    jobject parent = system_class_loader(env);
    if (parent == nullptr) {
        munmap(mapping, static_cast<size_t>(archive_stat.st_size));
        return nullptr;
    }
    jclass loader_class = env->FindClass("dalvik/system/InMemoryDexClassLoader");
    if (loader_class == nullptr || clear_exception(env)) {
        munmap(mapping, static_cast<size_t>(archive_stat.st_size));
        return nullptr;
    }
    jmethodID constructor = env->GetMethodID(loader_class, "<init>",
            "(Ljava/nio/ByteBuffer;Ljava/lang/ClassLoader;)V");
    if (constructor == nullptr || clear_exception(env)) {
        munmap(mapping, static_cast<size_t>(archive_stat.st_size));
        return nullptr;
    }
    jobject loader = env->NewObject(loader_class, constructor, buffer, parent);
    if (loader == nullptr || clear_exception(env)) {
        munmap(mapping, static_cast<size_t>(archive_stat.st_size));
        return nullptr;
    }
    g_dex_mapping = mapping;
    g_dex_mapping_size = static_cast<size_t>(archive_stat.st_size);
    g_dex_loader = env->NewGlobalRef(loader);
    return loader;
}

jobject load_class(JNIEnv* env, jobject loader, const char* class_name) {
    jclass loader_class = env->FindClass("java/lang/ClassLoader");
    if (loader_class == nullptr || clear_exception(env)) return nullptr;
    jmethodID load = env->GetMethodID(loader_class, "loadClass",
            "(Ljava/lang/String;)Ljava/lang/Class;");
    if (load == nullptr || clear_exception(env)) return nullptr;
    jstring name = env->NewStringUTF(class_name);
    if (name == nullptr || clear_exception(env)) return nullptr;
    jobject result = env->CallObjectMethod(loader, load, name);
    if (clear_exception(env)) return nullptr;
    return result;
}

bool string_equals(JNIEnv* env, jstring value, const char* expected) {
    if (value == nullptr || expected == nullptr) return false;
    const char* text = env->GetStringUTFChars(value, nullptr);
    if (text == nullptr) {
        clear_exception(env);
        return false;
    }
    const bool equal = std::strcmp(text, expected) == 0;
    env->ReleaseStringUTFChars(value, text);
    return equal;
}

jobject find_delivery_method(JNIEnv* env, const char* class_name) {
    jclass target_class = env->FindClass(class_name);
    if (target_class == nullptr || clear_exception(env)) return nullptr;
    jclass class_class = env->FindClass("java/lang/Class");
    jclass method_class = env->FindClass("java/lang/reflect/Method");
    if (class_class == nullptr || method_class == nullptr || clear_exception(env)) return nullptr;
    jmethodID get_methods = env->GetMethodID(class_class, "getDeclaredMethods",
            "()[Ljava/lang/reflect/Method;");
    jmethodID method_name = env->GetMethodID(method_class, "getName", "()Ljava/lang/String;");
    jmethodID parameter_types = env->GetMethodID(method_class, "getParameterTypes",
            "()[Ljava/lang/Class;");
    jmethodID class_name_id = env->GetMethodID(class_class, "getName", "()Ljava/lang/String;");
    jmethodID set_accessible = env->GetMethodID(method_class, "setAccessible", "(Z)V");
    if (get_methods == nullptr || method_name == nullptr || parameter_types == nullptr
            || class_name_id == nullptr || set_accessible == nullptr || clear_exception(env)) {
        return nullptr;
    }
    auto methods = static_cast<jobjectArray>(env->CallObjectMethod(target_class, get_methods));
    if (methods == nullptr || clear_exception(env)) return nullptr;
    const jsize count = env->GetArrayLength(methods);
    for (jsize index = 0; index < count; ++index) {
        jobject method = env->GetObjectArrayElement(methods, index);
        auto name = static_cast<jstring>(env->CallObjectMethod(method, method_name));
        if (clear_exception(env) || !string_equals(env, name, kDeliveryMethodName)) {
            env->DeleteLocalRef(method);
            continue;
        }
        auto parameters = static_cast<jobjectArray>(env->CallObjectMethod(method, parameter_types));
        if (parameters == nullptr || clear_exception(env) || env->GetArrayLength(parameters) != 2) {
            env->DeleteLocalRef(method);
            continue;
        }
        jobject first = env->GetObjectArrayElement(parameters, 0);
        auto first_name = static_cast<jstring>(env->CallObjectMethod(first, class_name_id));
        const bool matches = !clear_exception(env) && string_equals(env, first_name, kLocationResultName);
        if (!matches) {
            env->DeleteLocalRef(method);
            continue;
        }
        env->CallVoidMethod(method, set_accessible, JNI_TRUE);
        if (clear_exception(env)) {
            env->DeleteLocalRef(method);
            return nullptr;
        }
        return method;
    }
    return nullptr;
}

bool cache_location_api(JNIEnv* env) {
    jclass result = env->FindClass("android/location/LocationResult");
    jclass location = env->FindClass("android/location/Location");
    jclass array_list = env->FindClass("java/util/ArrayList");
    if (result == nullptr || location == nullptr || array_list == nullptr || clear_exception(env)) {
        return false;
    }
    g_location.location_result_class = static_cast<jclass>(env->NewGlobalRef(result));
    g_location.location_class = static_cast<jclass>(env->NewGlobalRef(location));
    g_location.array_list_class = static_cast<jclass>(env->NewGlobalRef(array_list));
    g_location.result_size = env->GetMethodID(result, "size", "()I");
    g_location.result_get = env->GetMethodID(result, "get", "(I)Landroid/location/Location;");
    g_location.result_create = env->GetStaticMethodID(result, "create",
            "(Ljava/util/List;)Landroid/location/LocationResult;");
    g_location.location_copy = env->GetMethodID(location, "<init>",
            "(Landroid/location/Location;)V");
    g_location.set_latitude = env->GetMethodID(location, "setLatitude", "(D)V");
    g_location.set_longitude = env->GetMethodID(location, "setLongitude", "(D)V");
    g_location.set_altitude = env->GetMethodID(location, "setAltitude", "(D)V");
    g_location.set_speed = env->GetMethodID(location, "setSpeed", "(F)V");
    g_location.set_bearing = env->GetMethodID(location, "setBearing", "(F)V");
    g_location.set_accuracy = env->GetMethodID(location, "setAccuracy", "(F)V");
    g_location.array_list_constructor = env->GetMethodID(array_list, "<init>", "(I)V");
    g_location.array_list_add = env->GetMethodID(array_list, "add", "(Ljava/lang/Object;)Z");
    return !clear_exception(env) && g_location.result_size != nullptr
            && g_location.result_get != nullptr && g_location.result_create != nullptr
            && g_location.location_copy != nullptr && g_location.set_latitude != nullptr
            && g_location.set_longitude != nullptr && g_location.set_altitude != nullptr
            && g_location.set_speed != nullptr && g_location.set_bearing != nullptr
            && g_location.set_accuracy != nullptr && g_location.array_list_constructor != nullptr
            && g_location.array_list_add != nullptr;
}

jobject rewrite_location_result(JNIEnv* env, jclass, jobject input) {
    if (input == nullptr || !g_hooks_committed.load(std::memory_order_acquire)) return input;
    const SharedStateV2* shared = g_shared_state.load(std::memory_order_acquire);
    StateSnapshot state;
    if (!read_snapshot(shared, &state)) return input;
    const uint32_t required = kFlagEnabled | kFlagHasCoordinates | kFlagEngineReady;
    if ((state.flags & required) != required || (state.flags & kFlagEmergencyDisable) != 0) {
        return input;
    }

    if (env->PushLocalFrame(32) != JNI_OK) return input;
    jobject output = nullptr;
    do {
        const jint count = env->CallIntMethod(input, g_location.result_size);
        if (clear_exception(env) || count <= 0 || count > 10000) break;
        jobject list = env->NewObject(g_location.array_list_class,
                g_location.array_list_constructor, count);
        if (list == nullptr || clear_exception(env)) break;
        bool failed = false;
        for (jint index = 0; index < count; ++index) {
            jobject original = env->CallObjectMethod(input, g_location.result_get, index);
            if (original == nullptr || clear_exception(env)) {
                failed = true;
                break;
            }
            jobject copy = env->NewObject(g_location.location_class,
                    g_location.location_copy, original);
            if (copy == nullptr || clear_exception(env)) {
                failed = true;
                break;
            }
            env->CallVoidMethod(copy, g_location.set_latitude, state.latitude);
            env->CallVoidMethod(copy, g_location.set_longitude, state.longitude);
            if ((state.flags & kFlagAutomaticAltitude) == 0) {
                env->CallVoidMethod(copy, g_location.set_altitude, state.altitude);
            }
            env->CallVoidMethod(copy, g_location.set_speed, state.speed);
            env->CallVoidMethod(copy, g_location.set_bearing, state.bearing);
            env->CallVoidMethod(copy, g_location.set_accuracy, state.accuracy);
            if (clear_exception(env)) {
                failed = true;
                break;
            }
            env->CallBooleanMethod(list, g_location.array_list_add, copy);
            if (clear_exception(env)) {
                failed = true;
                break;
            }
        }
        if (failed) break;
        output = env->CallStaticObjectMethod(g_location.location_result_class,
                g_location.result_create, list);
        if (clear_exception(env)) output = nullptr;
    } while (false);
    return env->PopLocalFrame(output != nullptr ? output : input);
}

void rollback_hooks(JNIEnv* env, const std::vector<jobject>& targets) {
    for (auto iterator = targets.rbegin(); iterator != targets.rend(); ++iterator) {
        (void)lsplant::UnHook(env, *iterator);
    }
}

}  // namespace

bool install_location_engine(JNIEnv* env, JavaVM*, int archive_fd,
        const SharedStateV2* shared_state, CompanionClient*, uint64_t) {
    if (env == nullptr || archive_fd < 0 || shared_state == nullptr) return false;
    if (env->PushLocalFrame(96) != JNI_OK) return false;
    bool installed = false;
    std::vector<jobject> local_targets;
    std::vector<jobject> local_hookers;
    std::vector<jobject> local_backups;
    do {
        jobject loader = create_in_memory_loader(env, archive_fd);
        if (loader == nullptr) break;
        jobject hook_class_object = load_class(env, loader, kDeliveryHookClass);
        if (hook_class_object == nullptr) break;
        auto hook_class = static_cast<jclass>(hook_class_object);
        JNINativeMethod rewrite_method[] = {
            {const_cast<char*>("rewriteLocationResult"),
                    const_cast<char*>("(Ljava/lang/Object;)Ljava/lang/Object;"),
                    reinterpret_cast<void*>(rewrite_location_result)},
        };
        if (env->RegisterNatives(hook_class, rewrite_method, 1) != JNI_OK || clear_exception(env)) break;
        if (!cache_location_api(env)) break;

        for (const char* target_class : kTransportClasses) {
            jobject target = find_delivery_method(env, target_class);
            if (target == nullptr) {
                local_targets.clear();
                break;
            }
            local_targets.push_back(target);
        }
        if (local_targets.size() != std::size(kTransportClasses)) break;

        jmethodID hook_constructor = env->GetMethodID(hook_class, "<init>", "()V");
        jmethodID callback_id = env->GetMethodID(hook_class, "callback",
                "([Ljava/lang/Object;)Ljava/lang/Object;");
        jmethodID set_backup = env->GetMethodID(hook_class, "setBackup",
                "(Ljava/lang/reflect/Method;)V");
        if (hook_constructor == nullptr || callback_id == nullptr || set_backup == nullptr
                || clear_exception(env)) break;
        jobject callback = env->ToReflectedMethod(hook_class, callback_id, JNI_FALSE);
        if (callback == nullptr || clear_exception(env)) break;
        if (!initialize_lsplant(env)) break;

        bool hook_failure = false;
        for (jobject target : local_targets) {
            jobject hooker = env->NewObject(hook_class, hook_constructor);
            if (hooker == nullptr || clear_exception(env)) {
                hook_failure = true;
                break;
            }
            jobject backup = lsplant::Hook(env, target, hooker, callback);
            if (backup == nullptr || clear_exception(env)) {
                hook_failure = true;
                break;
            }
            env->CallVoidMethod(hooker, set_backup, backup);
            if (clear_exception(env)) {
                hook_failure = true;
                break;
            }
            local_hookers.push_back(hooker);
            local_backups.push_back(backup);
        }
        if (hook_failure || local_backups.size() != local_targets.size()) {
            rollback_hooks(env, local_targets);
            break;
        }

        for (jobject target : local_targets) g_target_methods.push_back(env->NewGlobalRef(target));
        for (jobject hooker : local_hookers) g_hooker_objects.push_back(env->NewGlobalRef(hooker));
        for (jobject backup : local_backups) g_backup_methods.push_back(env->NewGlobalRef(backup));
        g_shared_state.store(shared_state, std::memory_order_release);
        g_hooks_committed.store(true, std::memory_order_release);
        installed = true;
    } while (false);
    env->PopLocalFrame(nullptr);
    return installed;
}

}  // namespace geoveil
