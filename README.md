# GeoVeil

GeoVeil is an experimental Magisk + Zygisk module for centrally virtualizing Android's framework-visible location state.

> **Status:** the RC2 development source now contains the central `system_server` delivery engine, root companion, lock-free shared state, one-crash fuse, parasitic Shell manager, Easy Location Switch, and foreground joystick. CI builds and packages the implementation successfully. It is still unvalidated on the target device and is not a proven safe release.

## Current implementation

- `system_server` connects to the Zygisk root companion before specialization and performs heavy initialization only after specialization.
- The engine probes the exact Android 16 delivery transport classes and commits all three LSPlant hooks only when every required class, method, DEX helper, and `Location` API is available.
- Framework-delivered `LocationResult` objects are copied, rewritten coherently, and rebuilt through Android 16's `LocationResult.wrap(List)` factory.
- Disabled, invalid, incompatible, stale, or emergency state returns the original genuine-location object unchanged.
- A memfd-backed seqlock snapshot keeps location callbacks free of file reads, socket waits, and process-shared locks.
- The root companion validates every state generation and handles static coordinates, walking/jogging movement, joystick deltas, recovery, and module-disable requests.
- An unfinished hook-install marker causes a replacement `system_server` to enter emergency pass-through rather than installing the hooks again.
- The Magisk late-start monitor observes the guarded `system_server` PID without killing or restarting any process.
- The parasitic manager is hosted through `com.android.shell`, launched from the module Action, and is never installed as a launcher-visible package.
- The manager includes filled coordinate fields, dynamic system colors, validation, remembered drafts, altitude/speed/bearing/accuracy controls, Easy Location Switch, recovery controls, and a movement panel.
- A movable 360-degree joystick is injected into the foreground top application without requesting Android's system-overlay permission; walking and jogging are mutually exclusive.
- The module packages raw `classes.dex` for `system_server` separately from the APK/ZIP archive used by the Shell manager.

## Safety boundary

- Virtualization and Easy Location Switch start disabled.
- No Android test provider, Developer Options mock app, `Settings.Secure` mock path, or mock-flag override is used.
- No Watchdog or Rescue Party modification.
- No telephony, IMEI, EFS, modem, RIL, IMS, SIM, call, SMS, mobile-data, vendor-radio, or block-device access.
- No framework partition replacement, custom kernel component, Shell force-stop, or framework restart.
- Hook or compatibility failure is fail-open and restores genuine-location delivery.

## Validation status

The API 36 manager DEX, arm64 Zygisk library, companion export, source guard, ZIP layout, and checksums build successfully in GitHub Actions. That does **not** prove device behavior. RC2 remains blocked on cold/warm boot tests, deliberate `system_server` failure recovery, manager and joystick cycles, framework/fused-location verification, Google Maps behavior, disable restoration, and calls/SMS/data/SIM/IMEI/connectivity regression testing.

The optional Wi-Fi and Bluetooth metadata sanitizers described in the roadmap are not included in this location-engine branch; they require separate compatibility probes and may not be added to the release until they can remain completely fail-open and connectivity-neutral.

See [`docs/ROADMAP.md`](docs/ROADMAP.md) and [`docs/MANAGER.md`](docs/MANAGER.md) for the release gates.

## Target

Initial target: arm64, Android 16 / API 36, Magisk 30.7 with Zygisk enabled. The native library uses Android API 35 as its NDK minimum because NDK r29 exposes native platforms through API 35; Java/framework compatibility is compiled and probed against API 36.

## License

The current manager implementation is original GeoVeil code and does not copy ReLSPosed source. A project license must still be finalized before importing or adapting GPL-covered ReLSPosed code. Pinned LSPlant and Dobby sources retain their upstream license notices and build lock data.
