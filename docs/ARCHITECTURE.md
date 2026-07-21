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

## Android Watchdog policy

GeoVeil never hooks, clears, delays, bypasses, or disables Android's `system_server` Watchdog. It must not alter handler-checker lists, checker timeouts, or Watchdog scheduling. A stalled GeoVeil hook is a GeoVeil defect; suppressing the operating system's recovery mechanism is not an acceptable workaround.

Every location hook follows a strict fast-path budget:

- no file, socket, Binder, or network I/O
- no class lookup or reflection
- no companion round trip
- no allocation-heavy parsing
- no unbounded loop, wait, sleep, or contended mutex
- no detached thread creation per delivered location

The hook reads one immutable, versioned state snapshot and either copies the virtual fields or immediately returns the original location.

## JNI and class-loader discipline

The payload caches `JavaVM`, required class references, field IDs, and method IDs during one guarded initialization phase. Cached classes are retained with global references and released only when the host process exits.

A native worker that genuinely requires JNI must call `JavaVM::GetEnv` first. Only a thread not already attached may use `AttachCurrentThreadAsDaemon`, and GeoVeil must detach only threads that it attached itself. Hook callbacks normally use the `JNIEnv` supplied by their already-attached calling thread.

Framework-private classes are resolved through the loader that loaded the target framework class. Repeated `FindClass` calls in delivery hooks are forbidden. A class-loader or signature mismatch aborts the entire hook installation and leaves genuine-location pass-through active.

## Companion IPC discipline

Persistent configuration is owned by the Zygisk root companion. Any companion channel needed by `system_server` is opened during the supported pre-specialization phase and retained through an exempt file descriptor. The delivery hook never waits for IPC.

The companion publishes validated state into a bounded shared snapshot. The hook consumes the newest complete generation with acquire/release ordering; a torn, stale, malformed, or unavailable snapshot is treated as disabled state.

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

## Previous-install migration

Before installing RC1, the installer asks a detected legacy GeoVeil controller to restore genuine location, stops only a PID verified as the old `geoveild` process, removes stale runtime state, and uninstalls known obsolete standalone-manager package IDs. It never kills or restarts Zygote, `system_server`, or `com.android.shell`.

The new module starts with an emergency-disable marker and no enabled-location state. Magisk handles replacement of the old module directory on reboot.

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

- clean install, previous-alpha migration, and uninstall
- ten cold boots and ten warm reboots
- forced `system_server` restart recovery
- repeated spoofing enable/disable cycles
- manager open/close cycles without shell death
- invalid/manual coordinate validation
- Easy Location Switch disabled by default
- genuine location restoration
- calls, SMS, mobile data, SIM state, and IMEI remain unchanged
- source guard and native build checks
