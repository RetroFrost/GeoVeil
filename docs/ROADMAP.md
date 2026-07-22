# GeoVeil release roadmap

GeoVeil separates its safety foundation from its first functional implementation. A version label does not mean a feature works until the corresponding code, CI checks, and target-device tests have passed.

## RC1 — safety foundation

RC1 remains the non-functional safety and packaging milestone.

Planned RC1 completion requirements:

- reproducible arm64 Zygisk build and Magisk ZIP packaging
- source guard and native ELF validation
- no-hook pass-through payload for `system_server`
- ordinary app children unload the module
- safe cleanup of withdrawn Alpha 1 and Alpha 3 state
- installer cleanup returns to the installer instead of terminating it
- one-crash fuse for an unfinished hook-install generation
- Magisk disable-marker recovery path
- Android 16 / API 36 and Magisk 30.7 target checks
- no test provider, Android mock-location setting, framework replacement, Watchdog modification, telephony access, EFS access, modem access, or block-device access

RC1 is not the working location-virtualization release.

## RC2 — functional system-wide virtualization

RC2 is the first milestone intended to implement GeoVeil's complete user-facing behavior.

### Central location engine

- actual global framework-visible location virtualization
- Android 16 framework compatibility probing for the exact target build
- atomic all-or-nothing installation of the required location hooks
- copied `Location` objects with coherent coordinate rewriting
- genuine-location pass-through whenever disabled, invalid, incompatible, or unhealthy
- consistent latitude, longitude, altitude, speed, bearing, accuracy, and timestamps

### Runtime state and IPC

- Zygisk companion-backed state bridge
- versioned binary state schema
- lock-free latest-state snapshots in hook paths
- no synchronous file or socket reads in a location callback
- strict latitude and longitude validation, including rejection of empty, malformed, NaN, and infinite values
- clean state-only enable and disable controls without ART unhooking or process restarts

### Manager

- ReLSPosed-style parasitic Material 3 manager
- `com.android.shell` manager bootstrap from Magisk's module Action
- filled Material 3 coordinate fields with inline validation
- remembered coordinates while spoofing remains disabled by default
- altitude, speed, bearing, and accuracy controls
- Easy Location Switch clipboard mode, disabled by default

### Movement controls

- movable joystick overlay
- 360-degree movement
- mutually exclusive walking and jogging modes
- speed saturation at 50 percent of joystick radius
- UI rendering separated from the lower-rate coordinate update stream

### Integration and validation

- framework `LocationManager` verification
- fused-location verification, including Google Maps behavior on the target device
- genuine-location restoration after disabling GeoVeil
- repeated manager launch, enable, disable, movement, and recovery cycles
- cold-boot, warm-reboot, and deliberate `system_server` failure recovery tests

### Network-environment sanitization

- optional app-visible Wi-Fi metadata sanitization while the real Wi-Fi connection remains untouched
- optional app-visible Bluetooth metadata sanitization while the real Bluetooth connection remains untouched
- separate compatibility probes and fail-open behavior for each sanitizer
- no connectivity, radio, telephony, IMS, SIM, modem, or vendor-service modification

## RC2 release blockers

RC2 must not be published as working until all of the following are true:

- the RC1 safety foundation and one-crash fuse are complete
- every required Android 16 compatibility probe succeeds on the target build
- hook installation is all-or-nothing
- hook paths use only bounded, nonblocking state reads
- the manager and joystick work without killing or restarting `com.android.shell`
- Google Maps and fused-location consumers observe the intended coherent location state
- disabling GeoVeil restores genuine location without rebooting
- calls, SMS, mobile data, SIM state, IMEI, Wi-Fi connectivity, and Bluetooth connectivity remain unchanged
- repeated reboot and forced-failure recovery tests pass
- the resulting ZIP, checksum, ELF metadata, source guard, and release notes are reviewed

## Permanent exclusions

GeoVeil will not add:

- Android test-provider or Developer Options mock-location mechanisms
- per-app hooks that hardcode mock-status or Settings results
- Watchdog or Rescue Party modifications
- blocking IPC in `system_server` callback paths
- telephony, IMEI, EFS, modem, RIL, IMS, SIM, call, SMS, or mobile-data hooks
- custom kernel modules or partition replacement trees
- claims of universal undetectability
