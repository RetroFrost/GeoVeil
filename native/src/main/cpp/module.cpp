#include "zygisk.hpp"

namespace geoveil {
namespace {

// Android's dedicated shell UID. This constant lets the pre-specialization
// callback retain GeoVeil only for the future parasitic-manager host without
// converting Java strings, reading files, parsing configuration, or touching ART.
constexpr jint kAndroidShellUid = 2000;

}  // namespace

// Safety scaffold only. This module intentionally installs no location hooks
// and does not load manager DEX/resources yet. Its purpose is to prove that
// GeoVeil can enter and leave specialization callbacks without doing work in
// zygote or unrelated application processes, while reserving a clean RC2
// bootstrap point for the specialized shell child.
class GeoVeilModule final : public zygisk::ModuleBase {
public:
    void onLoad(zygisk::Api* api, JNIEnv* env) override {
        api_ = api;
        env_ = env;
    }

    void preAppSpecialize(zygisk::AppSpecializeArgs* args) override {
        // Keep this callback tiny and deterministic. UID comparison and a bool
        // assignment are the only routing work performed before specialization.
        // No Java strings, package lookups, allocation, I/O, threads, locks,
        // configuration parsing, or manager loading are allowed here.
        is_shell_child_ = args != nullptr && args->uid == kAndroidShellUid;

        // Every unrelated application child unloads the library. The shell child
        // retains it only so RC2 can bootstrap the parasitic manager after the
        // process has specialized. No hooks or retained callbacks exist yet.
        if (!is_shell_child_ && api_ != nullptr) {
            api_->setOption(zygisk::DLCLOSE_MODULE_LIBRARY);
        }
    }

    void postAppSpecialize(const zygisk::AppSpecializeArgs*) override {
        if (!is_shell_child_) {
            return;
        }

        // Future RC2 parasitic-manager bootstrap point. Manager DEX/resources,
        // compatibility handling, and the companion state bridge must be loaded
        // only here, after com.android.shell has specialized. Until reviewed and
        // device-tested, retaining the no-hook native scaffold is the only action.
        (void)env_;
    }

    void preServerSpecialize(zygisk::ServerSpecializeArgs*) override {
        // Deliberately empty: no allocation, I/O, ART access, thread creation,
        // state parsing, compatibility probing, or companion connection is
        // performed by the current no-hook scaffold before specialization.
    }

    void postServerSpecialize(const zygisk::ServerSpecializeArgs*) override {
        // Future RC2 implementation point:
        // 1. perform read-only Android 16 compatibility probes;
        // 2. abort to genuine-location pass-through on any mismatch;
        // 3. commit the complete hook set atomically;
        // 4. consume only bounded, nonblocking state snapshots;
        // 5. never touch Watchdog, telephony, radio, EFS, block devices, or settings.
        //
        // Until that implementation is reviewed and tested, this stays empty.
        (void)env_;
    }

private:
    zygisk::Api* api_ = nullptr;
    JNIEnv* env_ = nullptr;
    bool is_shell_child_ = false;
};

}  // namespace geoveil

REGISTER_ZYGISK_MODULE(geoveil::GeoVeilModule)
