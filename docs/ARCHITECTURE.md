# GeoVeil architecture

GeoVeil uses RC1 for the safety foundation and RC2 for the first functional location engine plus the required parasitic manager. Documentation describes intended behavior; a feature is not working until the corresponding source, CI checks, and target-device tests exist.

## Process model

GeoVeil is split by process responsibility. The Zygisk library is loaded into forked child processes; it must not perform GeoVeil work in the zygote daemon itself.

```text
zygote / zygote64
└── register Zygisk callbacks only

system_server child
└── compatibility probe
    └── central location virtualization hooks (only after every probe succeeds)

com.android.shell child
└── post-specialization parasitic-manager bootstrap only
    ├── embedded manager DEX/resources
    ├── validated companion state client
    └── optional foreground joystick controller

all other app children
└── unload GeoVeil immediately unless an explicitly-scoped foreground overlay requires a reviewed future path
```

The RC1 native scaffold now reserves the Shell child using only the dedicated shell UID. It still loads no manager DEX/resources and installs no location hooks.

## Zygote-safety rules

`onLoad()` and all pre-specialization callbacks must remain tiny and deterministic:

- store framework pointers only
- at most perform the minimal shell-UID routing comparison
- no Java/ART method hooks
- no manager DEX/resource loading
- no threads
- no blocking locks
- no network access
- no configuration parsing
- no scanning `/proc` or Android framework files
- no writes to Android settings or properties
- no calls into telephony, radio, IMS, SIM, modem, EFS, block devices, or vendor services

All optional initialization occurs after the target child has specialized. Any error leaves the process in pass-through mode.

## Atomic hook installation

The `system_server` payload uses a two-phase installation:

1. **Probe:** resolve every required class, method, field, signature, and expected API behavior without modifying ART.
2. **Commit:** install the complete known-compatible hook set only if every required probe succeeded.

Partial hook sets are forbidden. A missing or changed Android 16 symbol results in zero hooks and genuine-location pass-through.

## Runtime state

The manager and `system_server` communicate through a small versioned state object owned by the root companion. Reads in hook paths must be lock-free snapshots.

```text
StateV1
├── schema version
├── virtualization enabled
├── valid coordinate flag
├── latitude / longitude
├── altitude mode and value
├── speed / bearing / accuracy
├── movement mode
├── Easy Location Switch enabled
├── Wi-Fi sanitizer enabled
├── Bluetooth sanitizer enabled
└── monotonically increasing generation
```

Virtualization starts disabled. Enabling requires a valid latitude in `[-90, 90]` and longitude in `[-180, 180]`. Empty, malformed, NaN, infinite, incomplete, or out-of-range state is rejected before publication.

Disabling changes state only; it never unloads native code, unhooks ART, restarts `system_server`, or force-stops `com.android.shell`.

## RC2 parasitic manager

The RC2 manager is mandatory and follows the full contract in [`MANAGER.md`](MANAGER.md).

Core properties:

- launched from Magisk's GeoVeil module Action
- hosted through the specialized `com.android.shell` child
- no separately installed launcher-visible package
- manager DEX/resources load only after specialization
- manager UI writes validated state through the companion bridge
- no direct synchronous manager-to-`system_server` calls
- manager close or crash does not change engine state
- no forced Shell restart or death
- Material 3 filled fields, dynamic color, dark mode, inline validation, and Material Symbols Outlined
- optional joystick, Easy Location Switch, altitude, speed, bearing, accuracy, and fail-open network-metadata controls

ReLSPosed may be studied for architecture and denylist compatibility. No ReLSPosed-derived source is imported until GeoVeil adopts a compatible license and preserves all required notices.

## Crash-loop guard

Before hook commit, the companion records an `installing` generation. After the specialized `system_server` remains healthy for a defined observation window, it records `healthy` for that generation.

A new `system_server` instance that observes an unfinished prior generation enters emergency pass-through mode and does not attempt hooks again until the user clears the condition from the manager or module recovery action.

The root-side guard must detect an unexpected `system_server` PID change during the same boot, create GeoVeil's emergency latch, remove the active-hook state, and write Magisk's module `disable` marker for the next reboot. The replacement framework instance installs zero hooks.

This guard supplements Magisk recovery; it does not replace device testing and cannot mathematically guarantee that no first crash will occur.

## Hard exclusion boundary

GeoVeil must not contain code that accesses or hooks:

- `TelephonyManager` identifiers
- IMEI, MEID, serial, subscriber, SIM, or carrier identifiers
- `com.android.phone`, RIL, radio, IMS, telecom, emergency, or SIM Toolkit processes
- `/efs`, `/persist`, `/dev/block`, modem partitions, or vendor radio properties
- Android Watchdog or Rescue Party behavior
- custom kernel modules or kernel patching

The module contains `skip_mount` and no `system`, `vendor`, `product`, or `system_ext` replacement tree.

## Location behavior

No Android test provider or Developer Options mock app is used. When virtualization is enabled, the central framework delivery path receives a coherent copied location object with virtual coordinates and internally consistent timestamps, speed, bearing, accuracy, and altitude state. When disabled or incompatible, the original location object passes through unchanged.

Claims of being universally undetectable are prohibited: GeoVeil avoids Android's ordinary test-provider mechanism, but rooted/Zygisk/ART modification can still be detected by sufficiently privileged or specialized software.

## Release gates

### RC1 safety gate

RC1 is not promoted until these pass:

- clean install and uninstall
- development ZIP builds reproducibly
- legacy cleanup returns to the installer correctly
- no-hook payload loads without framework instability
- ordinary app children unload; Shell child routing stays inert
- one-crash fuse and Magisk disable-marker recovery are implemented
- source guard and native build checks pass

### RC2 functional gate

RC2 is not promoted to a working release until all of the following pass on the target Android build:

- clean install and uninstall
- ten cold boots and ten warm reboots
- forced `system_server` restart recovery
- repeated virtualization enable/disable cycles
- manager open/close/reopen cycles without Shell death
- manager launch from Magisk Action without a separate launcher package
- deliberate manager failure does not destabilize the engine
- invalid/manual coordinate validation
- joystick create, move, release, reposition, and removal cycles
- Easy Location Switch disabled by default
- genuine location restoration
- framework and fused-location verification, including Google Maps
- calls, SMS, mobile data, SIM state, and IMEI remain unchanged
- real Wi-Fi and Bluetooth connectivity remain unchanged
- source guard, native build, manager build, packaging, checksum, and license checks pass
