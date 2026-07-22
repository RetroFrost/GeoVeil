# GeoVeil LSPosed manager

This directory builds one installable APK that is both the GeoVeil launcher app and its LSPosed module payload.

- `META-INF/xposed/java_init.list` registers `GeoVeilModule`.
- `GeoVeilApplication` binds LSPosed's `XposedService`.
- The launcher writes live state to the `geoveil` remote-preferences group.
- Each app process selected in LSPosed reads that state and installs location getter and `LocationManager` hooks.
- The optional joystick is injected into the selected app's own activity view hierarchy; it does not use the system-overlay permission.

Build with Android API 36 SDK and Build Tools 36.0.0:

```bash
ANDROID_HOME=/path/to/android-sdk ./manager/build-manager.sh
```

Output: `manager/build/GeoVeil-LSPosed.apk`.
