# GeoVeil RC2 standalone manager

This directory contains the standalone GeoVeil manager application and the Java helpers shared with the module runtime.

Implemented in source:

- programmatic Material-3-inspired filled-field interface
- dynamic system-color lookup with light/dark fallbacks
- strict latitude, longitude, altitude, speed, bearing, and accuracy validation
- remembered coordinate drafts while virtualization stays disabled by default
- Easy Location Switch control disabled by default
- bounded background `su` client for the module-owned root control helper
- launcher-visible `MainActivity` in `dev.retrofrost.geoveil.manager`
- no network permission, analytics, or telemetry
- reproducible `javac`, D8, AAPT2, zipalign, and apksigner build

The APK requests Magisk root by executing the module-owned `bin/geoveilctl` helper. That helper validates and updates the root-only state mapping consumed by the engine. The manager APK itself is not a Zygisk injection target. Magisk's module Action launches `MainActivity` directly. If root is denied or the helper is absent, the APK remains open and reports the concrete failure instead of pretending to be connected.

Current limitation: CI proves compilation and packaging, not target-device behavior. Working location virtualization is not claimed until Android 16 device validation passes.

Implementation rules retained:

- no manager loading or routing during zygote or app-specialization callbacks
- no Shell, `system_server`, or zygote restart when opening the manager
- no synchronous bridge calls on the UI thread
- no direct synchronous calls from the manager into `system_server`
- closing or crashing the manager does not change the engine state
- no network telemetry, test provider, Settings mock path, telephony, EFS, modem, or block-device access

Build with an Android API 36 SDK and Build Tools 36.0.0:

```bash
ANDROID_HOME=/path/to/android-sdk ./manager/build-manager.sh
```

See [`../docs/MANAGER.md`](../docs/MANAGER.md) for the complete RC2 manager contract and target-device release tests.
