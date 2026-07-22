# GeoAvil patch build

This branch intentionally stays small.

GitHub Actions clones FakeGPS at pinned commit `8502952b815c134be6514d71f0cfb76acd68e7c3`, applies `geoavil.patch`, builds the debug APK, and uploads:

- `GeoAvil-mock-status-tester` when the build succeeds
- `GeoAvil-build-log` on every run, including failures
