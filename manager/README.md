# GeoVeil RC2 parasitic manager

This directory now contains an original Java implementation of the first GeoVeil parasitic-manager surface.

Implemented in source:

- programmatic Material-3-inspired filled-field interface
- dynamic system-color lookup with light/dark fallbacks
- strict latitude, longitude, altitude, speed, bearing, and accuracy validation
- remembered coordinate drafts while virtualization stays disabled by default
- Easy Location Switch control disabled by default
- bounded background local-socket client for the future versioned native bridge
- Shell activity lifecycle attachment through `GeoVeilEntry`
- no separately installed launcher-visible package
- reproducible `javac` + D8 build producing a DEX archive named `manager.apk`

The native Zygisk library loads this archive only in the specialized Android Shell child and invokes `GeoVeilEntry.install(Application)`. Magisk's module Action stages the archive in `/data/local/tmp/geoveil` and opens the Shell bug-report activity with GeoVeil's launch category.

Current limitation: the central `system_server` location engine and root bridge server are still intentionally absent, so the manager reports pass-through when no bridge accepts its bounded state message. The UI is implemented; working location virtualization is not yet claimed.

Implementation rules retained:

- no manager loading during zygote or pre-specialization callbacks
- one targeted `com.android.shell` restart when opening the parasitic manager; no `system_server` or zygote restart
- no synchronous bridge calls on the UI thread
- no direct synchronous calls from the manager into `system_server`
- closing or crashing the manager does not change the engine state
- no network telemetry, test provider, Settings mock path, telephony, EFS, modem, or block-device access

Build with an Android API 36 SDK and Build Tools 36.0.0:

```bash
ANDROID_HOME=/path/to/android-sdk ./manager/build-manager.sh
```

See [`../docs/MANAGER.md`](../docs/MANAGER.md) for the complete RC2 manager contract and target-device release tests.
