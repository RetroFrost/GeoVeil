#include <sys/mman.h>
#include <sys/types.h>
#include <unistd.h>

#include <atomic>
#include <cstdint>
#include <cstring>
#include <pthread.h>
#include <time.h>

#include "bridge.hpp"
#include "engine.hpp"
#include "state.hpp"
#include "zygisk.hpp"

namespace geoveil {
namespace {

constexpr jint kFirstApplicationUid = 10000;
constexpr char kManagerPackage[] = "dev.retrofrost.geoveil.manager";
constexpr char kManagerArchive[] = "/data/local/tmp/geoveil/manager.apk";
constexpr char kOverlayEntryClass[] = "dev.retrofrost.geoveil.manager.OverlayEntry";
constexpr useconds_t kBootstrapDelayMicros = 250000;
constexpr int kManagerBootstrapAttempts = 40;
constexpr int kOverlayBootstrapAttempts = 40;
constexpr unsigned int kHealthyObservationSeconds = 30;

uint64_t monotonic_ns() {
    timespec now{};
    if (clock_gettime(CLOCK_MONOTONIC, &now) != 0) return 1;
    const uint64_t value = static_cast<uint64_t>(now.tv_sec) * 1000000000ULL
            + static_cast<uint64_t>(now.tv_nsec);
    return value == 0 ? 1 : value;
}

bool clear_exception(JNIEnv* env) {
    if (env == nullptr || !env->ExceptionCheck()) return false;
    env->ExceptionClear();
    return true;
}

bool jstring_equals(JNIEnv* env, jstring value, const char* expected) {
    if (env == nullptr || value == nullptr || expected == nullptr) return false;
    const char* chars = env->GetStringUTFChars(value, nullptr);
    if (chars == nullptr || clear_exception(env)) return false;
    const bool equal = std::strcmp(chars, expected) == 0;
    env->ReleaseStringUTFChars(value, chars);
    return equal;
}

jobject current_application(JNIEnv* env) {
    jclass activity_thread = env->FindClass("android/app/ActivityThread");
    if (activity_thread == nullptr || clear_exception(env)) return nullptr;
    jmethodID current = env->GetStaticMethodID(activity_thread, "currentApplication",
            "()Landroid/app/Application;");
    if (current == nullptr || clear_exception(env)) return nullptr;
    jobject application = env->CallStaticObjectMethod(activity_thread, current);
    if (clear_exception(env)) return nullptr;
    return application;
}

jobject application_class_loader(JNIEnv* env, jobject application) {
    if (application == nullptr) return nullptr;
    jclass application_class = env->GetObjectClass(application);
    if (application_class == nullptr || clear_exception(env)) return nullptr;
    jmethodID get_loader = env->GetMethodID(application_class, "getClassLoader",
            "()Ljava/lang/ClassLoader;");
    if (get_loader == nullptr || clear_exception(env)) return nullptr;
    jobject loader = env->CallObjectMethod(application, get_loader);
    if (clear_exception(env)) return nullptr;
    return loader;
}

jobject create_path_loader(JNIEnv* env, jobject parent_loader) {
    jclass path_loader_class = env->FindClass("dalvik/system/PathClassLoader");
    if (path_loader_class == nullptr || clear_exception(env)) return nullptr;
    jmethodID constructor = env->GetMethodID(path_loader_class, "<init>",
            "(Ljava/lang/String;Ljava/lang/ClassLoader;)V");
    if (constructor == nullptr || clear_exception(env)) return nullptr;
    jstring archive_path = env->NewStringUTF(kManagerArchive);
    if (archive_path == nullptr || clear_exception(env)) return nullptr;
    jobject loader = env->NewObject(path_loader_class, constructor, archive_path, parent_loader);
    if (clear_exception(env)) return nullptr;
    return loader;
}

jobject load_class(JNIEnv* env, jobject class_loader, const char* class_name) {
    jclass loader_class = env->FindClass("java/lang/ClassLoader");
    if (loader_class == nullptr || clear_exception(env)) return nullptr;
    jmethodID load = env->GetMethodID(loader_class, "loadClass",
            "(Ljava/lang/String;)Ljava/lang/Class;");
    if (load == nullptr || clear_exception(env)) return nullptr;
    jstring name = env->NewStringUTF(class_name);
    if (name == nullptr || clear_exception(env)) return nullptr;
    jobject result = env->CallObjectMethod(class_loader, load, name);
    if (clear_exception(env)) return nullptr;
    return result;
}

}  // namespace

class GeoVeilModule final : public zygisk::ModuleBase {
public:
    void onLoad(zygisk::Api* api, JNIEnv* env) override {
        api_ = api;
        env_ = env;
        if (env != nullptr) (void)env->GetJavaVM(&vm_);
    }

    void preAppSpecialize(zygisk::AppSpecializeArgs* args) override {
        uid_ = args != nullptr ? args->uid : -1;
        is_manager_app_child_ = args != nullptr && uid_ >= kFirstApplicationUid
                && jstring_equals(env_, args->nice_name, kManagerPackage);
        is_top_app_child_ = args != nullptr && uid_ >= kFirstApplicationUid
                && !is_manager_app_child_
                && args->is_top_app != nullptr && *args->is_top_app == JNI_TRUE;
        if (!is_manager_app_child_ && !is_top_app_child_) {
            if (api_ != nullptr) api_->setOption(zygisk::DLCLOSE_MODULE_LIBRARY);
            return;
        }
        connect_companion_pre_specialize();
        if (companion_socket_ < 0 && api_ != nullptr) {
            api_->setOption(zygisk::DLCLOSE_MODULE_LIBRARY);
        }
    }

    void postAppSpecialize(const zygisk::AppSpecializeArgs*) override {
        if ((!is_manager_app_child_ && !is_top_app_child_) || vm_ == nullptr
                || companion_socket_ < 0 || bootstrap_started_.exchange(true)) {
            return;
        }
        process_role_ = is_manager_app_child_
                ? ClientRole::kManagerApp : ClientRole::kTopAppOverlay;
        pthread_t thread{};
        if (pthread_create(&thread, nullptr, &GeoVeilModule::app_bootstrap_thread, this) == 0) {
            pthread_detach(thread);
        } else {
            bootstrap_started_.store(false);
        }
    }

    void preServerSpecialize(zygisk::ServerSpecializeArgs*) override {
        uid_ = 1000;
        process_role_ = ClientRole::kSystemServer;
        connect_companion_pre_specialize();
    }

    void postServerSpecialize(const zygisk::ServerSpecializeArgs*) override {
        if (vm_ == nullptr || companion_socket_ < 0 || bootstrap_started_.exchange(true)) return;
        pthread_t thread{};
        if (pthread_create(&thread, nullptr, &GeoVeilModule::engine_bootstrap_thread, this) == 0) {
            pthread_detach(thread);
        } else {
            bootstrap_started_.store(false);
        }
    }

private:
    void connect_companion_pre_specialize() {
        if (api_ == nullptr || companion_socket_ >= 0) return;
        const int socket_fd = api_->connectCompanion();
        if (socket_fd < 0) return;
        companion_socket_ = socket_fd;
        // Zygisk may close inherited app fds during specialization. Exemption is a
        // fixed-fd operation; no protocol, parsing, or manager work occurs here.
        (void)api_->exemptFd(companion_socket_);
    }

    static void* app_bootstrap_thread(void* opaque) {
        static_cast<GeoVeilModule*>(opaque)->run_app_bootstrap();
        return nullptr;
    }

    static void* engine_bootstrap_thread(void* opaque) {
        static_cast<GeoVeilModule*>(opaque)->run_engine_bootstrap();
        return nullptr;
    }

    static void* healthy_thread(void* opaque) {
        auto* module = static_cast<GeoVeilModule*>(opaque);
        sleep(kHealthyObservationSeconds);
        if (module->engine_installed_.load()) {
            (void)module->companion_.engine_healthy(module->engine_generation_);
        }
        return nullptr;
    }

    void run_app_bootstrap() {
        companion_.adopt_socket(companion_socket_);
        companion_socket_ = -1;
        if (!companion_.handshake(process_role_, getpid(), uid_, nullptr, nullptr)) return;

        JNIEnv* env = nullptr;
        if (vm_->AttachCurrentThread(&env, nullptr) != JNI_OK || env == nullptr) return;
        const int attempts = process_role_ == ClientRole::kManagerApp
                ? kManagerBootstrapAttempts : kOverlayBootstrapAttempts;
        for (int attempt = 0; attempt < attempts; ++attempt) {
            const bool installed = process_role_ == ClientRole::kManagerApp
                    ? install_manager_bridge(env)
                    : access(kManagerArchive, R_OK) == 0
                            && install_app_entry(env, kOverlayEntryClass);
            if (installed) break;
            usleep(kBootstrapDelayMicros);
        }
        vm_->DetachCurrentThread();
    }

    bool install_manager_bridge(JNIEnv* env) {
        if (env->PushLocalFrame(24) != JNI_OK) return false;
        bool installed = false;
        do {
            jobject application = current_application(env);
            if (application == nullptr) break;
            jobject loader = application_class_loader(env, application);
            if (loader == nullptr) break;
            installed = companion_.register_manager_natives(env, loader);
        } while (false);
        env->PopLocalFrame(nullptr);
        return installed;
    }

    bool install_app_entry(JNIEnv* env, const char* entry_name) {
        if (env->PushLocalFrame(40) != JNI_OK) return false;
        bool installed = false;
        do {
            jobject application = current_application(env);
            if (application == nullptr) break;
            jobject parent_loader = application_class_loader(env, application);
            if (parent_loader == nullptr) break;
            jobject loader = create_path_loader(env, parent_loader);
            if (loader == nullptr) break;
            if (!companion_.register_manager_natives(env, loader)) break;
            jobject entry_object = load_class(env, loader, entry_name);
            if (entry_object == nullptr) break;
            auto entry_class = static_cast<jclass>(entry_object);
            jmethodID install = env->GetStaticMethodID(entry_class, "install",
                    "(Landroid/app/Application;)V");
            if (install == nullptr || clear_exception(env)) break;
            env->CallStaticVoidMethod(entry_class, install, application);
            if (clear_exception(env)) break;
            installed = true;
        } while (false);
        env->PopLocalFrame(nullptr);
        return installed;
    }

    void run_engine_bootstrap() {
        companion_.adopt_socket(companion_socket_);
        companion_socket_ = -1;
        int state_fd = -1;
        int archive_fd = -1;
        if (!companion_.handshake(ClientRole::kSystemServer, getpid(), uid_,
                &state_fd, &archive_fd)) {
            if (state_fd >= 0) close(state_fd);
            if (archive_fd >= 0) close(archive_fd);
            return;
        }
        if ((companion_.last_flags() & kFlagEmergencyDisable) != 0
                || state_fd < 0 || archive_fd < 0) {
            if (state_fd >= 0) close(state_fd);
            if (archive_fd >= 0) close(archive_fd);
            return;
        }

        shared_state_ = static_cast<const SharedStateV2*>(mmap(nullptr, sizeof(SharedStateV2),
                PROT_READ, MAP_SHARED, state_fd, 0));
        close(state_fd);
        if (shared_state_ == MAP_FAILED) {
            shared_state_ = nullptr;
            close(archive_fd);
            return;
        }

        engine_generation_ = monotonic_ns();
        if (companion_.engine_begin(engine_generation_) < 0) {
            close(archive_fd);
            return;
        }

        JNIEnv* env = nullptr;
        bool installed = false;
        if (vm_->AttachCurrentThread(&env, nullptr) == JNI_OK && env != nullptr) {
            installed = install_location_engine(env, vm_, archive_fd, shared_state_,
                    &companion_, engine_generation_);
            vm_->DetachCurrentThread();
        }
        close(archive_fd);
        if (!installed) {
            (void)companion_.engine_abort(engine_generation_);
            return;
        }

        engine_installed_.store(true);
        pthread_t thread{};
        if (pthread_create(&thread, nullptr, &GeoVeilModule::healthy_thread, this) == 0) {
            pthread_detach(thread);
        } else {
            // Keep the installing marker. A replacement system_server will observe
            // it and enter emergency pass-through instead of retrying the hooks.
            engine_installed_.store(false);
        }
    }

    zygisk::Api* api_ = nullptr;
    JNIEnv* env_ = nullptr;
    JavaVM* vm_ = nullptr;
    CompanionClient companion_;
    ClientRole process_role_ = ClientRole::kUnknown;
    jint uid_ = -1;
    int companion_socket_ = -1;
    bool is_manager_app_child_ = false;
    bool is_top_app_child_ = false;
    const SharedStateV2* shared_state_ = nullptr;
    uint64_t engine_generation_ = 0;
    std::atomic<bool> bootstrap_started_{false};
    std::atomic<bool> engine_installed_{false};
};

}  // namespace geoveil

REGISTER_ZYGISK_MODULE(geoveil::GeoVeilModule)
