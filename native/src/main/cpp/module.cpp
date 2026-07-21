#include "zygisk.hpp"

namespace geoveil {

// Safety scaffold only. This module intentionally installs no hooks yet.
// Its purpose is to prove that GeoVeil can enter and leave specialization
// callbacks without doing work in zygote or unrelated app processes.
class GeoVeilModule final : public zygisk::ModuleBase {
public:
    void onLoad(zygisk::Api* api, JNIEnv* env) override {
        api_ = api;
        env_ = env;
    }

    void preAppSpecialize(zygisk::AppSpecializeArgs*) override {
        // No app-process payload exists in this scaffold. Request unloading in
        // every ordinary app child. This option is safe only because no hooks,
        // callbacks, threads, or retained function pointers have been installed.
        if (api_ != nullptr) {
            api_->setOption(zygisk::DLCLOSE_MODULE_LIBRARY);
        }
    }

    void postAppSpecialize(const zygisk::AppSpecializeArgs*) override {
        // Deliberately empty.
    }

    void preServerSpecialize(zygisk::ServerSpecializeArgs*) override {
        // Deliberately empty: no allocation, I/O, ART access, thread creation,
        // state parsing, or compatibility probing is allowed before specialize.
    }

    void postServerSpecialize(const zygisk::ServerSpecializeArgs*) override {
        // Future RC1 implementation point:
        // 1. perform read-only compatibility probes;
        // 2. abort to genuine-location pass-through on any mismatch;
        // 3. commit the complete hook set atomically;
        // 4. never touch telephony, radio, EFS, block devices, or settings.
        //
        // Until that implementation is reviewed and tested, this stays empty.
        (void)env_;
    }

private:
    zygisk::Api* api_ = nullptr;
    JNIEnv* env_ = nullptr;
};

}  // namespace geoveil

REGISTER_ZYGISK_MODULE(geoveil::GeoVeilModule)
