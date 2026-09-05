#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "geoavil")
APP = ROOT / "app"


def patch(path: Path, old: str, new: str, required=True):
    text = path.read_text(encoding="utf-8")
    if old not in text:
        if required:
            raise SystemExit(f"Expected text not found in {path}: {old[:120]!r}")
        return False
    path.write_text(text.replace(old, new), encoding="utf-8")
    return True


# Android 16 is the current stable target (API 36). AGP 8.10.x supports API 36 and
# requires exactly the Gradle 8.11.1 wrapper already pinned by the upstream base.
root_build = ROOT / "build.gradle"
rbt = root_build.read_text(encoding="utf-8")
rbt = rbt.replace("classpath 'com.android.tools.build:gradle:8.7.3'",
                  "classpath 'com.android.tools.build:gradle:8.10.1'")
root_build.write_text(rbt, encoding="utf-8")

app_build = APP / "build.gradle"
abt = app_build.read_text(encoding="utf-8")
abt = abt.replace("compileSdk 34", "compileSdk 36")
abt = abt.replace("targetSdk 34", "targetSdk 36")
# Keep the known-good AppCompat/Material versions from alpha5/alpha6 and only update
# AndroidX Core to the newest line compatible with API 36/AGP 8.10. Core 1.19 targets
# API 37 and requires AGP 9.1+, which is the Android 17 preview toolchain.
abt = abt.replace("androidx.core:core:1.13.1", "androidx.core:core:1.16.0")
app_build.write_text(abt, encoding="utf-8")

# The old status-bar reflection helper is no longer used by the overlay and is incorrect
# for dynamic insets. Keep the API for legacy callers but return no synthetic offset.
screen = APP / "src/main/java/com/github/fakegps/ScreenUtils.java"
st = screen.read_text(encoding="utf-8")
old_status = '''    public static int getStatusBarHeight(Context context) {
        int id = context.getResources().getIdentifier("status_bar_height", "dimen", "android");
        return id > 0 ? context.getResources().getDimensionPixelSize(id) : 0;
    }
'''
if old_status in st:
    st = st.replace(old_status, '''    public static int getStatusBarHeight(Context context) {
        return 0;
    }
''')
screen.write_text(st, encoding="utf-8")

# Android 16 enforces modern large-screen/orientation behavior. Do not lock the three
# legacy activities to portrait; the floating overlay separately reclamps itself when the
# display configuration changes.
manifest = APP / "src/main/AndroidManifest.xml"
mt = manifest.read_text(encoding="utf-8").replace('android:screenOrientation="portrait"',
                                                   'android:screenOrientation="unspecified"')
manifest.write_text(mt, encoding="utf-8")

# Give the main scroll root a stable ID and apply real system-bar/display-cutout insets.
main_layout = APP / "src/main/res/layout/activity_main.xml"
ml = main_layout.read_text(encoding="utf-8")
if 'android:id="@+id/main_root"' not in ml:
    ml = ml.replace('<androidx.core.widget.NestedScrollView\n',
                    '<androidx.core.widget.NestedScrollView\n    android:id="@+id/main_root"\n', 1)
main_layout.write_text(ml, encoding="utf-8")

main = APP / "src/main/java/com/github/fakegps/ui/MainActivity.java"
mat = main.read_text(encoding="utf-8")
if 'import androidx.core.graphics.Insets;' not in mat:
    mat = mat.replace('import androidx.core.app.ActivityCompat;\n',
                      'import androidx.core.app.ActivityCompat;\nimport androidx.core.graphics.Insets;\nimport androidx.core.view.ViewCompat;\nimport androidx.core.view.WindowInsetsCompat;\n')
if 'ViewCompat.setOnApplyWindowInsetsListener(mainRoot' not in mat:
    anchor = '''        if (savedInstanceState != null) {
            Object savedPoint = savedInstanceState.getSerializable(STATE_PENDING_POINT);
            if (savedPoint instanceof LocPoint) mPendingStartPoint = (LocPoint) savedPoint;
            mPendingStartStep = savedInstanceState.getDouble(STATE_PENDING_STEP, 0.0);
        }
'''
    inset_block = anchor + '''
        View mainRoot = findViewById(R.id.main_root);
        final int initialLeft = mainRoot.getPaddingLeft();
        final int initialTop = mainRoot.getPaddingTop();
        final int initialRight = mainRoot.getPaddingRight();
        final int initialBottom = mainRoot.getPaddingBottom();
        ViewCompat.setOnApplyWindowInsetsListener(mainRoot, (view, insets) -> {
            Insets bars = insets.getInsets(WindowInsetsCompat.Type.systemBars()
                    | WindowInsetsCompat.Type.displayCutout());
            view.setPadding(initialLeft + bars.left, initialTop + bars.top,
                    initialRight + bars.right, initialBottom + bars.bottom);
            return insets;
        });
        ViewCompat.requestApplyInsets(mainRoot);
'''
    if anchor not in mat:
        raise SystemExit("Could not add Android 16 insets handling to MainActivity")
    mat = mat.replace(anchor, inset_block, 1)
main.write_text(mat, encoding="utf-8")

# Other simple screens can let the framework fit their root content around system UI.
for rel in ["activity_bookmark.xml", "activity_fly.xml", "activity_documentation.xml"]:
    p = APP / "src/main/res/layout" / rel
    if not p.exists():
        continue
    text = p.read_text(encoding="utf-8")
    if 'android:fitsSystemWindows="true"' not in text:
        first_width = 'android:layout_width="match_parent"'
        text = text.replace(first_width,
                            'android:fitsSystemWindows="true"\n    ' + first_width, 1)
    # Let Material 3 own the bookmark background instead of painting it twice.
    if rel == "activity_bookmark.xml":
        text = text.replace('              android:background="@android:color/background_light"\n', '')
    p.write_text(text, encoding="utf-8")

# Correct monochrome notification icon instead of reusing the full-color launcher bitmap.
notification_icon = APP / "src/main/res/drawable/ic_stat_geoavil.xml"
notification_icon.write_text(r'''<?xml version="1.0" encoding="utf-8"?>
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="24dp"
    android:height="24dp"
    android:viewportWidth="24"
    android:viewportHeight="24">
    <path
        android:fillColor="#FFFFFFFF"
        android:pathData="M12,2C8.13,2 5,5.13 5,9c0,5.25 7,13 7,13s7,-7.75 7,-13c0,-3.87 -3.13,-7 -7,-7zM12,11.5c-1.38,0 -2.5,-1.12 -2.5,-2.5s1.12,-2.5 2.5,-2.5 2.5,1.12 2.5,2.5 -1.12,2.5 -2.5,2.5z" />
</vector>
''', encoding="utf-8")
service = APP / "src/main/java/com/github/fakegps/FakeLocationService.java"
sv = service.read_text(encoding="utf-8").replace('setSmallIcon(R.drawable.icon_app)',
                                                   'setSmallIcon(R.drawable.ic_stat_geoavil)')
service.write_text(sv, encoding="utf-8")

# A backend label alone cannot prove that the LSPosed system hook is actually effective.
# Expose whether a root sanitizer is expected, then let the in-app tester verify the
# EFFECT on a fresh location that matches GeoAvil's current coordinate.
bridge = APP / "src/main/java/com/github/fakegps/RootBridge.java"
br = bridge.read_text(encoding="utf-8")
if 'public static boolean rootSanitizerExpected()' not in br:
    marker = '    public static String lastError() { return lastError; }\n'
    method = '''    public static boolean rootSanitizerExpected() {
        Backend selected = backend;
        if (selected == Backend.ROOT) return true;
        return selected == Backend.SHIZUKU && privilegedUid() == 0;
    }

'''
    if marker not in br:
        raise SystemExit("Could not add root hook expectation to RootBridge")
    br = br.replace(marker, method + marker)
bridge.write_text(br, encoding="utf-8")

mat = main.read_text(encoding="utf-8")
if 'freshGeoAvilLocation' not in mat:
    mat = mat.replace('            boolean foundLocation = false;\n',
                      '            boolean foundLocation = false;\n'
                      '            boolean freshGeoAvilLocation = false;\n'
                      '            boolean freshGeoAvilNonMock = false;\n')
    marker = '                foundLocation = true;\n'
    check = marker + '''                LocPoint expected = JoyStickManager.get().getCurrentLocPoint();
                long locationAgeMs = getLocationAgeMillis(location);
                if (expected != null && locationAgeMs >= 0 && locationAgeMs <= 2500
                        && Math.abs(location.getLatitude() - expected.getLatitude()) <= 0.00002
                        && Math.abs(location.getLongitude() - expected.getLongitude()) <= 0.00002) {
                    freshGeoAvilLocation = true;
                    if (!isMockLocation(location)) freshGeoAvilNonMock = true;
                }
'''
    if marker not in mat:
        raise SystemExit("Could not add fresh-location hook verification")
    mat = mat.replace(marker, check, 1)
    before_found = '            if (!foundLocation) {\n'
    verification = '''            if (RootBridge.rootSanitizerExpected() && JoyStickManager.get().isStarted()) {
                builder.append("\nSystem hook effect: ");
                if (freshGeoAvilNonMock) {
                    builder.append("verified — fresh GeoAvil location isMock=false\n");
                } else if (freshGeoAvilLocation) {
                    builder.append("not effective — fresh GeoAvil location is still mock\n");
                } else {
                    builder.append("waiting for a fresh GeoAvil location\n");
                }
            }

'''
    if before_found not in mat:
        raise SystemExit("Could not add hook verification result")
    mat = mat.replace(before_found, verification + before_found, 1)
    before_age = '    private String getLocationAge(Location location) {\n'
    age_helper = '''    private long getLocationAgeMillis(Location location) {
        long elapsedNanos = location.getElapsedRealtimeNanos();
        if (elapsedNanos <= 0) return -1L;
        return Math.max(0L, (SystemClock.elapsedRealtimeNanos() - elapsedNanos) / 1000000L);
    }

'''
    if before_age not in mat:
        raise SystemExit("Could not add location-age helper")
    mat = mat.replace(before_age, age_helper + before_age, 1)
main.write_text(mat, encoding="utf-8")

# Keep documentation aligned with the actual diagnostic behavior.
docs = APP / "src/main/res/layout/activity_documentation.xml"
if docs.exists():
    dt = docs.read_text(encoding="utf-8")
    dt = dt.replace(
        'On rooted setups, also check the backend label. The intended system-hook setup is rooted Shizuku/Sui plus the GeoAvil LSPosed module loaded in System Framework.',
        'On rooted setups, the tester also verifies the system-hook effect against a fresh GeoAvil coordinate. “verified” means that matching live location arrived with isMock=false; “not effective” means the matching live location is still marked mock.'
    )
    docs.write_text(dt, encoding="utf-8")

print("GeoAvil alpha6 Android 16/platform compatibility pass applied")
