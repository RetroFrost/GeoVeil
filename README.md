# GeoVeil

GeoVeil is an experimental Android 16 **LSPosed** location-virtualization module with a normal launcher-visible manager APK.

## What this build does

- uses the official libxposed module API and LSPosed remote preferences; it has no Magisk Action, Zygisk companion, `su` shell, or custom root daemon;
- installs only inside apps you explicitly select for GeoVeil in LSPosed;
- intercepts `Location` latitude, longitude, altitude, speed, bearing, and accuracy reads, plus `LocationManager.getLastKnownLocation` results, in those target processes;
- applies manager changes live through LSPosed shared preferences—no target-app force-stop or Android framework restart;
- parses a copied Maps coordinate pair or URL;
- provides an optional in-app D-pad joystick inside selected target activities, without the Android system-overlay permission.

## Install

1. Install and activate LSPosed for the same Magisk environment.
2. Install `GeoVeil-LSPosed.apk`.
3. In LSPosed, enable GeoVeil and select only the apps whose location view you want to virtualize.
4. Open GeoVeil, confirm **LSPosed connected**, paste coordinates, and enable Virtual location.
5. Reopen a selected target app after enabling the joystick.

This is scoped app-process virtualization, not a system GPS replacement. Apps outside the selected LSPosed scope continue to receive genuine location. No Android mock provider, Developer Options mock-location setting, telephony/IMEI, modem, EFS, partition, Watchdog, Rescue Party, `system_server`, zygote, or Shell manipulation is included.

## Status

The APK source and packaging are validated in CI. Device behavior still needs Android 16 validation across the target apps, location APIs, and OEM build before claiming broad compatibility.
