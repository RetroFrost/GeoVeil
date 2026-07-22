# GeoVeil RC2 manager source

This directory is reserved for the RC2 parasitic Material 3 manager.

Current state: architecture scaffold only. No manager DEX, resources, activity, or shell-host bootstrap is implemented yet, and nothing from this directory is packaged into automated development ZIPs.

Implementation rules:

- no separately installed launcher-visible package
- bootstrap only inside the specialized `com.android.shell` child
- no manager loading during zygote or pre-specialization callbacks
- no force-stop, kill, or restart of `com.android.shell`
- no direct synchronous calls from the UI into `system_server`
- manager state goes through the versioned companion bridge
- all coordinate validation occurs before publishing a new state generation
- closing or crashing the manager must not alter the active engine state
- no network telemetry, test provider, Settings mock path, telephony, EFS, modem, or block-device access

See [`../docs/MANAGER.md`](../docs/MANAGER.md) for the complete RC2 manager contract and release tests.

ReLSPosed architecture may be studied for compatibility behavior, but source code must not be copied until GeoVeil has finalized a GPL-compatible project license and preserved all required copyright and license notices.
