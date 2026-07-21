# GeoVeil

GeoVeil is an experimental Magisk + Zygisk module for centrally virtualizing Android's framework-visible location state.

> **Status:** early development. There is no safe flashable release yet. Do not package or flash the repository until the release checklist is complete.

## Frozen design

- Zygisk payload for `system_server` only for central location virtualization.
- ReLSPosed-style parasitic Material 3 manager hosted through `com.android.shell`.
- Filled Material 3 text fields and Material Symbols Outlined icons.
- Manual coordinates with strict latitude/longitude validation.
- Optional **Easy Location Switch** clipboard watcher, disabled by default.
- Optional movable analog control with mutually exclusive walking/jogging modes.
- Spoofing disabled by default; first use requires valid coordinates.
- No Android mock-location setting, test provider, `Settings.Secure` write, framework replacement, or custom-kernel component.
- No telephony, IMEI, EFS, modem, RIL, IMS, SIM, calls, SMS, or mobile-data hooks.

## Stability policy

GeoVeil must fail open: when a compatibility probe or hook fails, Android's genuine location passes through unchanged. The project will not publish a release until repeated reboot, `system_server` restart, manager launch, enable/disable, and recovery tests pass on the target Android build.

## Target

Initial target: arm64, Android 16 / API 36, Magisk 30.7 with Zygisk enabled.

## License

A project license will be finalized before importing or adapting ReLSPosed-derived manager code. ReLSPosed-compatible code requires preserving its applicable GPL terms.
