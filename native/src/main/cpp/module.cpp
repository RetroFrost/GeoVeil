#include <sys/types.h>

#include "zygisk.hpp"

#include <atomic>
#include <pthread.h>
#include <unistd.h>

namespace geoveil {
namespace {

constexpr jint kAndroidShellUid = 2000;
constexpr char kManagerArchive[] = "/data/local/tmp/geoveil/manager.apk";
constexpr char kManagerEntryClass[] = "dev.retrofrost.geoveil.manager.GeoVeilEntry";
constexpr int kBootstrapAttempts = 600;
constexpr useconds_t kBootstrapDelayMicros = 1000000;

bool clear_exception(JNIEnv* env) {
    if (env == nullptr || !env->ExceptionCheck()) {
        return false;
    }
    env->ExceptionClear();
    return true;
}

}  // namespace

class GeoVeilModule final : public zygisk::ModuleBase {
public:
    void onLoad(zygisk::Api* api, JNIEnv* env) override {
        api_ = api;
        if (env != nullptr) {
            (void)env->GetJavaVM(&vm_);
        }
    }

    void preAppSpecialize(zygisk::AppSpecializeArgs* args) override {
        // Keep pre-specialization routing intentionally tiny: compare the already
        // supplied UID and choose whether the library may remain mapped.
        is_shell_child_ = args != nullptr && args->uid == kAndroidShellUid;
        if (!is_shell_child_ && api_ != nullptr) {
            api_->setOption(zygisk::DLCLOSE_MODULE_LIBRARY);
        }
    }

    void postAppSpecialize(const zygisk::AppSpecializeArgs*) override {
        if (!is_shell_child_ || vm_ == nullptr || bootstrap_started_.exchange(true)) {
            return;
        }

        pthread_t thread{};
        if (pthread_create(&thread, nullptr, &GeoVeilModule::bootstrap_thread, this) == 0) {
            pthread_detach(thread);
        } else {
            bootstrap_started_.store(false);
        }
    }

    void preServerSpecialize(zygisk::ServerSpecializeArgs*) override {
        // The current system_server payload remains inert. No I/O, allocation,
        // state parsing, companion connection, or hook work occurs here.
    }

    void postServerSpecialize(const zygisk::ServerSpecializeArgs*) override {
        // The RC2 location engine is still a release blocker. Until its exact-build
        // probe, one-crash fuse, and all-or-nothing hook commit are implemented and
        // tested, system_server remains genuine-location pass-through.
    }

private:
    static void* bootstrap_thread(void* opaque) {
        auto* module = static_cast<GeoVeilModule*>(opaque);
        module->run_manager_bootstrap();
        return nullptr;
    }

    void run_manager_bootstrap() {
        JNIEnv* env = nullptr;
        if (vm_->AttachCurrentThread(&env, nullptr) != JNI_OK || env == nullptr) {
            return;
        }

        for (int attempt = 0; attempt < kBootstrapAttempts; ++attempt) {
            if (access(kManagerArchive, R_OK) == 0 && install_manager(env)) {
                break;
            }
            usleep(kBootstrapDelayMicros);
        }

        vm_->DetachCurrentThread();
    }

    bool install_manager(JNIEnv* env) {
        if (env->PushLocalFrame(32) != JNI_OK) {
            return false;
        }

        bool installed = false;
        do {
            jclass activity_thread = env->FindClass("android/app/ActivityThread");
            if (activity_thread == nullptr || clear_exception(env)) break;

            jmethodID current_application = env->GetStaticMethodID(
                    activity_thread,
                    "currentApplication",
                    "()Landroid/app/Application;");
            if (current_application == nullptr || clear_exception(env)) break;

            jobject application = env->CallStaticObjectMethod(activity_thread, current_application);
            if (application == nullptr || clear_exception(env)) break;

            jclass application_class = env->GetObjectClass(application);
            if (application_class == nullptr || clear_exception(env)) break;

            jmethodID get_class_loader = env->GetMethodID(
                    application_class,
                    "getClassLoader",
                    "()Ljava/lang/ClassLoader;");
            if (get_class_loader == nullptr || clear_exception(env)) break;

            jobject parent_loader = env->CallObjectMethod(application, get_class_loader);
            if (parent_loader == nullptr || clear_exception(env)) break;

            jclass path_loader_class = env->FindClass("dalvik/system/PathClassLoader");
            if (path_loader_class == nullptr || clear_exception(env)) break;

            jmethodID path_loader_constructor = env->GetMethodID(
                    path_loader_class,
                    "<init>",
                    "(Ljava/lang/String;Ljava/lang/ClassLoader;)V");
            if (path_loader_constructor == nullptr || clear_exception(env)) break;

            jstring archive_path = env->NewStringUTF(kManagerArchive);
            if (archive_path == nullptr || clear_exception(env)) break;

            jobject manager_loader = env->NewObject(
                    path_loader_class,
                    path_loader_constructor,
                    archive_path,
                    parent_loader);
            if (manager_loader == nullptr || clear_exception(env)) break;

            jclass class_loader_class = env->FindClass("java/lang/ClassLoader");
            if (class_loader_class == nullptr || clear_exception(env)) break;

            jmethodID load_class = env->GetMethodID(
                    class_loader_class,
                    "loadClass",
                    "(Ljava/lang/String;)Ljava/lang/Class;");
            if (load_class == nullptr || clear_exception(env)) break;

            jstring entry_name = env->NewStringUTF(kManagerEntryClass);
            if (entry_name == nullptr || clear_exception(env)) break;

            jobject entry_object = env->CallObjectMethod(manager_loader, load_class, entry_name);
            if (entry_object == nullptr || clear_exception(env)) break;

            auto entry_class = static_cast<jclass>(entry_object);
            jmethodID install = env->GetStaticMethodID(
                    entry_class,
                    "install",
                    "(Landroid/app/Application;)V");
            if (install == nullptr || clear_exception(env)) break;

            env->CallStaticVoidMethod(entry_class, install, application);
            if (clear_exception(env)) break;
            installed = true;
        } while (false);

        env->PopLocalFrame(nullptr);
        return installed;
    }

    zygisk::Api* api_ = nullptr;
    JavaVM* vm_ = nullptr;
    bool is_shell_child_ = false;
    std::atomic<bool> bootstrap_started_{false};
};

}  // namespace geoveil

REGISTER_ZYGISK_MODULE(geoveil::GeoVeilModule)
