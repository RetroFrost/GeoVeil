# GeoVeil RC2 parasitic manager

The parasitic manager is a required RC2 component, not an optional follow-up. RC2 is not considered feature-complete unless the manager can be opened from Magisk's module Action and operate without installing a separate launcher-visible application package.

## Goals

- launch from Magisk: Modules -> GeoVeil -> Action
- host the manager through the specialized `com.android.shell` process
- present a Material 3 interface with dynamic system colors and dark-mode support
- keep location virtualization state independent from the manager UI lifecycle
- never force-stop, kill, or restart `com.android.shell`, `system_server`, or zygote
- fail safely: manager bootstrap failure must leave virtualization unchanged and must not destabilize Android

## Process boundary

```text
Magisk module Action
        |
        v
small shell bootstrap request
        |
        v
specialized com.android.shell child
        |
        +-- load embedded manager DEX/resources after specialization
        +-- open the manager activity/window
        +-- read and write validated state through the companion bridge
        +-- optionally request the foreground joystick overlay

system_server child
        |
        +-- consumes only the latest validated, versioned state snapshot
        +-- never depends on the manager process being alive
```

The manager must not contain the location hook itself. Closing or crashing the manager must not unload hooks, unhook ART, restart a process, or silently change the current enabled state.

## Zygisk routing

The native module may retain itself in the shell child only after a minimal pre-specialization UID check. Pre-specialization code must not load DEX, inspect packages, parse configuration, create threads, access files, or perform Java/ART reflection.

All manager bootstrap work occurs after the shell child has specialized. Every unrelated application child unloads the GeoVeil native library.

The implementation must account for the case where `com.android.shell` is denylisted or its Magisk mount namespace is unavailable. Compatibility handling may follow the architectural pattern used by ReLSPosed, but no ReLSPosed source may be copied until GeoVeil's project license and required GPL notices are finalized.

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

The manager must not offer Watchdog modification, Rescue Party suppression, `system_server` restart, zygote restart, Shell force-stop, cache wipe, or telephony repair actions.

## Security and privacy

- no network permission is required for the core manager
- no analytics or telemetry
- no access to telephony identifiers, SIM information, calls, SMS, IMS, modem, EFS, block devices, or vendor radio services
- no Android test-provider or Developer Options mock-location configuration
- no per-application hooks that hardcode mock status or secure-setting results

## RC2 manager release gate

The manager portion of RC2 is blocked until all of these pass on the target Android 16 build:

- launch from Magisk Action on repeated attempts
- launch when the shell process is subject to expected Magisk denylist/mount conditions
- no launcher-visible installed manager package
- no `com.android.shell` death or forced restart
- manager close/reopen preserves the intended state
- invalid coordinate input cannot reach the native state snapshot
- dynamic color, dark mode, filled fields, and inline errors render correctly
- joystick creation, movement, release, repositioning, and removal work repeatedly
- manager crash does not crash or block `system_server`
- engine disable restores genuine location without rebooting
- emergency pass-through and module-disable recovery controls work
- calls, SMS, mobile data, SIM state, IMEI, Wi-Fi connectivity, and Bluetooth connectivity remain unchanged

Until those tests pass, repository code and automated ZIPs must identify the manager as an unvalidated RC2 implementation rather than a working release.
