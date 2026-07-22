# GeoVeil

GeoVeil is an experimental Magisk + Zygisk module for centrally virtualizing Android's framework-visible location state.

> **Status:** early development. RC1 is the safety and packaging foundation; RC2 is the first planned functional virtualization milestone and includes the required parasitic manager. There is no safe working release yet.

## Frozen design

- Zygisk payload for `system_server` only for central location virtualization.
- Required ReLSPosed-style parasitic Material 3 manager hosted through `com.android.shell` in RC2.
- Manager launches from Magisk's module Action with no separately installed launcher-visible package.
- Filled Material 3 text fields and Material Symbols Outlined icons.
- Manual coordinates with strict latitude/longitude validation.
- Optional **Easy Location Switch** clipboard watcher, disabled by default.
- Optional movable analog control with mutually exclusive walking/jogging modes.
- Virtualization disabled by default; first use requires valid coordinates.
- No Android mock-location setting, test provider, `Settings.Secure` write, framework replacement, Watchdog modification, or custom-kernel component.
- No telephony, IMEI, EFS, modem, RIL, IMS, SIM, calls, SMS, or mobile-data hooks.

## Release plan

- **RC1:** no-hook safety scaffold, reproducible packaging, legacy cleanup, source guards, API-target alignment, recovery paths, one-crash fuse, and inert Shell-host routing for the future manager.
- **RC2:** global location virtualization, Android 16 compatibility probes, atomic hooks, companion IPC, lock-free state, working parasitic manager, joystick, movement modes, controls, fused-location verification, and optional fail-open Wi-Fi/Bluetooth metadata sanitization.

See [`docs/ROADMAP.md`](docs/ROADMAP.md) for the complete RC1/RC2 scope and release blockers. The dedicated manager contract is in [`docs/MANAGER.md`](docs/MANAGER.md).

## Stability policy

GeoVeil must fail open: when a compatibility probe or hook fails, Android's genuine location passes through unchanged. The project will not publish a functional release until repeated reboot, `system_server` restart, manager launch, enable/disable, movement, connectivity, and recovery tests pass on the target Android build.

## Target

Initial target: arm64, Android 16 / API 36, Magisk 30.7 with Zygisk enabled.

## License

A project license will be finalized before importing or adapting ReLSPosed-derived manager code. ReLSPosed-compatible code requires preserving its applicable GPL terms.
