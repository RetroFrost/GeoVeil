# GeoVeil

GeoVeil is an experimental Magisk + Zygisk module for centrally virtualizing Android's framework-visible location state.

> **Status:** RC2 manager implementation is now present in source, including Shell-child loading, Magisk Action launch, programmatic filled-field UI, validation, saved drafts, and a bounded bridge client. The central location engine and bridge server are still absent, and no device-tested working release exists yet.

## Current implementation

- Zygisk retains itself only in the Android Shell child and `system_server`; ordinary app children unload it.
- Post-specialization Shell bootstrap loads the compiled manager DEX archive from `/data/local/tmp/geoveil/manager.apk`.
- Magisk's module Action stages the archive and opens a Shell bug-report activity carrying GeoVeil's launch category.
- The manager attaches through activity lifecycle callbacks without installing a separate launcher-visible package.
- Programmatic Material-3-inspired filled fields use dynamic system-color lookup with light/dark fallbacks.
- Latitude, longitude, altitude, speed, bearing, and accuracy are validated before bridge publication.
- Valid coordinate drafts are remembered while virtualization remains disabled by default.
- The bridge client performs bounded socket work on a background executor, never on the UI thread.
- Missing or incompatible bridge state produces explicit pass-through status rather than a false success.

## Frozen design

- Central location virtualization belongs only in the specialized `system_server` child.
- The manager is hosted through `com.android.shell` and launched from Magisk's module Action.
- Optional **Easy Location Switch** starts disabled.
- The movable joystick, central bridge server, and location hook remain RC2 work.
- No Android mock-location setting, test provider, `Settings.Secure` write, framework replacement, Watchdog modification, or custom-kernel component.
- No telephony, IMEI, EFS, modem, RIL, IMS, SIM, calls, SMS, or mobile-data hooks.

## Release plan

- **RC1:** safety scaffold, reproducible packaging, legacy cleanup, source guards, API-target alignment, recovery paths, and the one-crash fuse.
- **RC2:** implemented manager plus the still-required global location engine, exact Android 16 compatibility probes, atomic hooks, root bridge server, lock-free state, joystick, fused-location verification, and device recovery tests.

See [`docs/ROADMAP.md`](docs/ROADMAP.md) for the complete scope and release blockers. The manager contract and current limitations are in [`docs/MANAGER.md`](docs/MANAGER.md) and [`manager/README.md`](manager/README.md).

## Stability policy

GeoVeil must fail open: when a compatibility probe, bridge, or hook fails, Android's genuine location passes through unchanged. The project will not publish a functional release until repeated reboot, `system_server` restart, manager launch, enable/disable, movement, connectivity, and recovery tests pass on the target Android build.

## Target

Initial target: arm64, Android 16 / API 36, Magisk 30.7 with Zygisk enabled.

## License

The current manager implementation is original GeoVeil code and does not copy ReLSPosed source. A project license must still be finalized before importing or adapting GPL-covered ReLSPosed code.
