# GeoAvil

GeoAvil is built from the pinned FakeGPS base at `8502952b815c134be6514d71f0cfb76acd68e7c3`, then applies `geoavil.patch` and the `modernize_geoavil.py` release layer.

## 0.3.0-alpha1

- Full Material 3 theming with Material You dynamic colour.
- Material 3 main screen and floating analog controller.
- Rootless privileged backend through Shizuku UserService.
- Shizuku shell mode uses Android's supported test-provider commands.
- Root-backed Shizuku/Sui (UID 0) uses `LocationManagerService.injectLocation` instead of a test provider, so GeoAvil does not create the location through the API path that forces `Location.isMock()` to true.
- Legacy `su` test-provider fallback remains available when Shizuku/Sui is unavailable.
- Same application id (`com.github.fakegps`) and the same stable legacy signing certificate are used so current GeoAvil installs can update in place.
- Versioning: `0.3.0-alpha1`, `versionCode 30001`.

## Release outputs

A successful workflow publishes both:

- `GeoAvil-Android-0.3.0-alpha1.apk` — immutable versioned build.
- `GeoAvil-latest.apk` — convenience alias for the newest published build.

The workflow also verifies the APK certificate with `apksigner`, publishes build/signature logs, and commits the release files with `[skip ci]` to prevent recursive builds.

## Signing note

The current install lineage already uses FakeGPS's repository keystore. GeoAvil deliberately keeps that certificate for this release so users do not have to uninstall before updating. It is a fixed certificate, but because the upstream keystore is public it should not be considered a private production signing identity. A future private-key migration would need an Android signing-lineage migration rather than silently replacing this key.
