# GeoVeil RC2 standalone manager

The standalone manager is a required RC2 component. It is installed as a normal launcher-visible APK and may be opened from either Android's launcher or Magisk's module Action.

## Goals

- launch from Magisk: Modules -> GeoVeil -> Action
- install the manager as `dev.retrofrost.geoveil.manager`
- present a Material 3 interface with dynamic system colors and dark-mode support
- keep location virtualization state independent from the manager UI lifecycle
- never restart Shell, `system_server`, or zygote to open the manager
- fail safely: an unavailable native bridge must leave virtualization unchanged, keep the APK open, and report pass-through

## Process boundary

```text
Android launcher or Magisk module Action
        |
        v
dev.retrofrost.geoveil.manager process
        |
        +-- open the installed MainActivity
        +-- register the JNI bridge after Zygisk specialization
        +-- read and write validated state through the companion bridge
        +-- optionally request the foreground joystick overlay

system_server child
        |
        +-- consumes only the latest validated, versioned state snapshot
        +-- never depends on the manager process being alive
```

The manager must not contain the location hook itself. Closing or crashing the manager must not unload hooks, unhook ART, restart a process, or silently change the current enabled state.

## Zygisk routing

The native module may retain itself in the manager process only after a minimal pre-specialization process-name check. Pre-specialization code must not load DEX, parse configuration, create threads, access files, or perform Java/ART reflection.

Native bridge registration occurs after the manager child has specialized. Every unrelated application child unloads the GeoVeil native library unless it is the explicitly scoped foreground joystick target. If the manager is denylisted from Zygisk, the UI must report that the bridge is unavailable.

## User interface

RC2 manager requirements:

- Material Design 3
- dynamic Material You colors
- light and dark themes
- filled text fields, not outlined fields
- Material Symbols Outlined icons
- rounded top corners and a bottom active indicator
- floating labels
- numeric coordinate keyboard and paste support
- inline animated validation messages; no blocking popup for ordinary input errors
- no terminal-style interface and no giant warning card replacing the main screen

### Main screen

- master virtualization switch
- latitude and longitude fields
- teleport/apply action disabled until coordinates are valid
- current effective coordinate summary
- manager/engine health status
- emergency pass-through status when the one-crash fuse has activated

Fresh installation starts disabled and contains no fabricated default coordinate. Previously saved valid coordinates may be remembered while the engine remains disabled.

### Advanced controls

- altitude mode: automatic by default
- optional manual altitude with a documented safe validation range
- speed
- bearing
- accuracy
- Easy Location Switch clipboard mode, disabled by default
- optional Wi-Fi and Bluetooth app-visible metadata sanitization, each independently disabled by default

## Shared validation

The manager and native consumer must use the same state schema and validation rules:

- latitude: finite value in `[-90, 90]`
- longitude: finite value in `[-180, 180]`
- reject empty, malformed, NaN, and infinite values
- reject an incomplete latitude/longitude pair
- do not publish a new state generation until the complete state validates
- invalid input never overwrites the previous valid state

## Joystick overlay

RC2 includes a movable foreground joystick launched from the manager:

- injected into the foreground activity without requesting Android's system overlay permission
- 360-degree direction
- walking and jogging are mutually exclusive
- movement speed saturates at 50 percent of the joystick radius
- UI may render at display frame rate while coordinate state is published at a lower bounded rate
- releasing the joystick stops movement cleanly
- overlay removal does not disable the selected static coordinate

The overlay and manager must never perform synchronous file reads or wait for socket responses in a UI-frame or location-callback path.

## State bridge

Manager writes go to the root companion through a versioned binary protocol. The companion validates and publishes an atomic latest-state snapshot. `system_server` reads that snapshot without blocking.

Required properties:

- explicit schema version
- monotonically increasing generation
- bounded message size
- validation before commit
- stale-generation rejection
- no text parsing inside hook paths
- no direct manager-to-`system_server` synchronous request
- pass-through when the state bridge is missing, stale, invalid, or incompatible

## Recovery behavior

The manager must expose:

- current pass-through/armed/enabled/emergency state
- clear saved coordinate state
- clear a resolved emergency latch only after explaining that hooks will be retried on the next safe activation
- disable GeoVeil for the next reboot by creating Magisk's module `disable` marker through the root companion
- view or export GeoVeil-owned logs without scanning unrelated private application data

The manager must not offer Watchdog modification, Rescue Party suppression, `system_server` restart, zygote restart, Shell restart, cache wipe, or telephony repair actions.

## Security and privacy

- no network permission is required for the core manager
- no analytics or telemetry
- no access to telephony identifiers, SIM information, calls, SMS, IMS, modem, EFS, block devices, or vendor radio services
- no Android test-provider or Developer Options mock-location configuration
- no per-application hooks that hardcode mock status or secure-setting results

## RC2 manager release gate

The manager portion of RC2 is blocked until all of these pass on the target Android 16 build:

- launch from Magisk Action on repeated attempts
- launch repeatedly from both Android's launcher and Magisk Action
- report an unavailable bridge without crashing when the module is missing, disabled, or denylisted
- no Shell, `system_server`, or zygote restart during manager launch
- manager close/reopen preserves the intended state
- invalid coordinate input cannot reach the native state snapshot
- dynamic color, dark mode, filled fields, and inline errors render correctly
- joystick creation, movement, release, repositioning, and removal work repeatedly
- manager crash does not crash or block `system_server`
- engine disable restores genuine location without rebooting
- emergency pass-through and module-disable recovery controls work
- calls, SMS, mobile data, SIM state, IMEI, Wi-Fi connectivity, and Bluetooth connectivity remain unchanged

Until those tests pass, repository code and automated ZIPs must identify the manager as an unvalidated RC2 implementation rather than a working release.
