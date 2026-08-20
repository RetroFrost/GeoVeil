# GeoAvil

GeoAvil is built from the pinned FakeGPS base at `8502952b815c134be6514d71f0cfb76acd68e7c3`, then applies `geoavil.patch`, `modernize_geoavil.py`, and `root_system_hook.py`.

## 0.3.0-alpha1

- Full Material 3 theming with Material You dynamic colour.
- Material 3 main screen and floating analog controller.
- Rootless privileged backend through Shizuku UserService.
- Shizuku shell mode uses Android's supported live test-provider commands, so joystick movement continues to publish locations normally.
- Root-backed Shizuku/Sui uses the same live provider path and the APK also contains a modern LSPosed module scoped only to `system`. When that root module is enabled, it clears the mock bit inside `system_server` immediately before a `MockLocationProvider` result is dispatched, so consumers receive `Location.isMock() == false` / `isFromMockProvider() == false` while continuous movement still works.
- The LSPosed system scope is intentionally narrow. Without the system hook enabled, Android correctly reports Shizuku/test-provider locations as mock even when the command itself was issued by UID 0.
- Legacy `su` test-provider fallback remains available when Shizuku/Sui is unavailable.
- Same application id (`com.github.fakegps`) and the same stable legacy signing certificate are used so current GeoAvil installs can update in place.
- Versioning: `0.3.0-alpha1`, `versionCode 30001`.

## Why the root path is not `injectLocation()`

Android's hidden `ILocationManager.injectLocation()` calls `injectLastLocation()`. Current AOSP only seeds that cache if no fine last location exists; it is not a streaming provider API. Using it for GeoAvil would make an initial coordinate appear plausible but would break repeated joystick updates. The system-server sanitizer therefore keeps Android's live provider pipeline and changes only the mock metadata before listener dispatch.

## Root activation

Install/update the same GeoAvil APK. On a rooted device using LSPosed, enable **GeoAvil** for the **System Framework (`system`)** scope and restart the framework/device. GeoAvil's root backend can then use Shizuku/Sui while the system-server module sanitizes the mock bit. Non-root users do not enable this module; they use Shizuku shell mode and Android will continue to expose the standard mock flag.

## Release outputs

A successful workflow publishes both:

- `GeoAvil-Android-0.3.0-alpha1.apk` — immutable versioned build.
- `GeoAvil-latest.apk` — convenience alias for the newest published build.

The workflow verifies the APK certificate with `apksigner`, publishes build/signature diagnostics, and commits release files with `[skip ci]` to prevent recursive builds.

## Signing note

The current install lineage already uses FakeGPS's repository keystore. GeoAvil deliberately keeps that certificate for this release so existing installs can update in place. It is a fixed certificate, but because the upstream keystore is public it should not be considered a private production signing identity. A future private-key migration would require an Android signing-lineage migration rather than silently replacing this key.
