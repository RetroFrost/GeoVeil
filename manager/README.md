# GeoVeil RC2 standalone manager

This directory contains the standalone GeoVeil manager application and the Java helpers shared with the module runtime.

Implemented in source:

- programmatic Material-3-inspired filled-field interface
- dynamic system-color lookup with light/dark fallbacks
- strict latitude, longitude, altitude, speed, bearing, and accuracy validation
- remembered coordinate drafts while virtualization stays disabled by default
- Easy Location Switch control disabled by default
- bounded background client for the versioned native bridge
- launcher-visible `MainActivity` in `dev.retrofrost.geoveil.manager`
- no network permission, analytics, or telemetry
- reproducible `javac`, D8, AAPT2, zipalign, and apksigner build

The native Zygisk library recognizes the manager process after specialization, registers the JNI bridge against the APK's own class loader, and connects it to the root companion. Magisk's module Action launches `MainActivity` directly. If the module bridge is unavailable, the APK remains open and reports pass-through instead of crashing.

Current limitation: CI proves compilation and packaging, not target-device behavior. Working location virtualization is not claimed until Android 16 device validation passes.

Implementation rules retained:

- no manager loading during zygote or pre-specialization callbacks
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
