# GeoVeil RC1 architecture

## Process model

GeoVeil is split by process responsibility. The Zygisk library is loaded into forked child processes; it must not perform GeoVeil work in the zygote daemon itself.

```text
zygote / zygote64
└── register Zygisk callbacks only

system_server child
└── compatibility probe
    └── central location virtualization hooks (only after every probe succeeds)

com.android.shell child
└── parasitic manager bootstrap only

all other app children
└── unload GeoVeil immediately unless a future explicitly-scoped UI overlay requires it
```

## Zygote-safety rules

`onLoad()` and all pre-specialization callbacks must remain tiny and deterministic:

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
├── spoofing enabled
├── valid coordinate flag
├── latitude / longitude
├── altitude mode and value
├── speed / bearing / accuracy
├── movement mode
├── Easy Location Switch enabled
└── monotonically increasing generation
```

Spoofing starts disabled. Enabling requires a valid latitude in `[-90, 90]` and longitude in `[-180, 180]`. Disabling changes state only; it never unloads native code, unhooks ART, restarts `system_server`, or force-stops `com.android.shell`.

## Crash-loop guard

Before hook commit, the companion records an `installing` generation. After the specialized `system_server` remains healthy for a defined observation window, it records `healthy` for that generation.

A new `system_server` instance that observes an unfinished prior generation enters emergency pass-through mode and does not attempt hooks again until the user clears the condition from the manager or module recovery action.

This guard supplements Magisk recovery; it does not replace device testing.

## Hard exclusion boundary

GeoVeil must not contain code that accesses or hooks:

- `TelephonyManager` identifiers
- IMEI, MEID, serial, subscriber, SIM, or carrier identifiers
- `com.android.phone`, RIL, radio, IMS, telecom, emergency, or SIM Toolkit processes
- `/efs`, `/persist`, `/dev/block`, modem partitions, or vendor radio properties
- custom kernel modules or kernel patching

The module contains `skip_mount` and no `system`, `vendor`, `product`, or `system_ext` replacement tree.

## Location behavior

No Android test provider or Developer Options mock app is used. When virtualization is enabled, the central framework delivery path receives a coherent copied location object with virtual coordinates and internally consistent timestamps, speed, bearing, accuracy, and altitude state. When disabled or incompatible, the original location object passes through unchanged.

Claims of being universally undetectable are prohibited: GeoVeil avoids Android's ordinary test-provider mechanism, but rooted/Zygisk/ART modification can still be detected by sufficiently privileged or specialized software.

## Release gate

RC1 is not promoted to a flashable release until all of the following pass on the target Android build:

- clean install and uninstall
- ten cold boots and ten warm reboots
- forced `system_server` restart recovery
- repeated spoofing enable/disable cycles
- manager open/close cycles without shell death
- invalid/manual coordinate validation
- Easy Location Switch disabled by default
- genuine location restoration
- calls, SMS, mobile data, SIM state, and IMEI remain unchanged
- source guard and native build checks
