# GeoVeil release roadmap

GeoVeil separates its safety foundation from its first functional implementation. A version label does not mean a feature works until the corresponding code, CI checks, and target-device tests have passed.

## RC1 — safety foundation

RC1 remains the non-functional safety and packaging milestone.

Planned RC1 completion requirements:

- reproducible arm64 Zygisk build and Magisk ZIP packaging
- source guard and native ELF validation
- no-hook pass-through payload for `system_server`
- ordinary app children unload the module
- shell UID routing reserves a post-specialization bootstrap point without loading manager code
- safe cleanup of withdrawn Alpha 1 and Alpha 3 state
- installer cleanup returns to the installer instead of terminating it
- one-crash fuse for an unfinished hook-install generation
- Magisk disable-marker recovery path
- Android 16 / API 36 and Magisk 30.7 target checks
- no test provider, Android mock-location setting, framework replacement, Watchdog modification, telephony access, EFS access, modem access, or block-device access

RC1 is not the working location-virtualization release and does not contain the working manager UI.

## RC2 — functional system-wide virtualization and manager

RC2 is the first milestone intended to implement GeoVeil's complete user-facing behavior. The parasitic manager is a required RC2 component, not a later optional add-on.

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

### Required parasitic manager

- ReLSPosed-style parasitic Material 3 manager
- launched from Magisk's GeoVeil module Action
- hosted through the specialized `com.android.shell` child
- no separately installed launcher-visible manager package
- a targeted `com.android.shell` restart is allowed only when explicitly opening the parasitic manager
- filled Material 3 coordinate fields with inline animated validation
- Material You dynamic colors, light/dark themes, rounded surfaces, and Material Symbols Outlined
- remembered coordinates while virtualization remains disabled by default
- current engine, pass-through, and emergency-latch status
- altitude, speed, bearing, and accuracy controls
- Easy Location Switch clipboard mode, disabled by default
- module-disable and emergency-recovery controls through the root companion
- manager close or crash does not change engine state or block `system_server`
- manager DEX/resources load only after Shell specialization
- denylist/mount compatibility behavior reviewed without copying ReLSPosed code before GPL-compatible licensing is finalized

See [`MANAGER.md`](MANAGER.md) for the complete manager process contract, UI behavior, state bridge, recovery controls, and release tests.

### Movement controls

- movable joystick overlay launched from the manager
- foreground-activity injection without requesting Android's system overlay permission
- 360-degree movement
- mutually exclusive walking and jogging modes
- speed saturation at 50 percent of joystick radius
- UI rendering separated from the lower-rate coordinate update stream
- joystick release stops movement without clearing the selected static coordinate

### Integration and validation

- framework `LocationManager` verification
- fused-location verification, including Google Maps behavior on the target device
- genuine-location restoration after disabling GeoVeil
- repeated manager launch, close, reopen, enable, disable, movement, and recovery cycles
- cold-boot, warm-reboot, and deliberate `system_server` failure recovery tests
- deliberate manager failure must not crash or block the location engine

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
- the manager opens reliably from Magisk Action without a separate launcher package
- the manager verifies successful attachment after one bounded `com.android.shell` restart
- manager close, reopen, and deliberate failure do not destabilize `system_server`
- invalid input cannot reach the companion's published state snapshot
- Google Maps and fused-location consumers observe the intended coherent location state
- disabling GeoVeil restores genuine location without rebooting
- calls, SMS, mobile data, SIM state, IMEI, Wi-Fi connectivity, and Bluetooth connectivity remain unchanged
- repeated reboot and forced-failure recovery tests pass
- the resulting ZIP includes the reviewed manager payload, checksum, ELF metadata, source guard results, license notices, and release notes

## Permanent exclusions

GeoVeil will not add:

- Android test-provider or Developer Options mock-location mechanisms
- per-app hooks that hardcode mock-status or Settings results
- Watchdog or Rescue Party modifications
- blocking IPC in `system_server` callback paths
- telephony, IMEI, EFS, modem, RIL, IMS, SIM, call, SMS, or mobile-data hooks
- custom kernel modules or partition replacement trees
- claims of universal undetectability
