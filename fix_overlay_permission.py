#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "geoavil")
APP = ROOT / "app"

build = APP / "build.gradle"
text = build.read_text(encoding="utf-8")
text = text.replace('versionCode 30004', 'versionCode 30005')
text = text.replace('versionName "0.3.0-alpha4"', 'versionName "0.3.0-alpha5"')
build.write_text(text, encoding="utf-8")

main = APP / "src/main/java/com/github/fakegps/ui/MainActivity.java"
m = main.read_text(encoding="utf-8")

# GeoAvil's old patch accidentally redirected the overlay request to generic App info.
# On Samsung/One UI that does not grant SYSTEM_ALERT_WINDOW. Restore Android's
# app-specific Display over other apps page instead.
m = m.replace('Settings.ACTION_APPLICATION_DETAILS_SETTINGS', 'Settings.ACTION_MANAGE_OVERLAY_PERMISSION')

# Give Restore analog its own overlay-permission result path.
if 'REQUEST_CODE_OVERLAY_RESTORE' not in m:
    m = m.replace(
        'private static final int REQUEST_CODE_OVERLAY = 2001;',
        'private static final int REQUEST_CODE_OVERLAY = 2001;\n    private static final int REQUEST_CODE_OVERLAY_RESTORE = 2004;'
    )

old_restore = '        mBtnRestoreAnalog.setOnClickListener(v -> JoyStickManager.get().restoreJoyStick());'
new_restore = '''        mBtnRestoreAnalog.setOnClickListener(v -> {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M && !Settings.canDrawOverlays(this)) {
                openOverlaySettings(REQUEST_CODE_OVERLAY_RESTORE);
            } else {
                JoyStickManager.get().restoreJoyStick();
            }
        });'''
if old_restore in m:
    m = m.replace(old_restore, new_restore)

# Replace the direct startActivityForResult call in the normal Start permission flow
# with a helper that falls back to the system overlay list if an OEM lacks the package page.
old_launch = '''                                Intent intent = new Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                                        Uri.parse("package:" + getPackageName()));
                                startActivityForResult(intent, REQUEST_CODE_OVERLAY);'''
new_launch = '''                                openOverlaySettings(REQUEST_CODE_OVERLAY);'''
if old_launch in m:
    m = m.replace(old_launch, new_launch)

# Handle Restore analog independently so returning from settings immediately retries it.
needle = '''        if (requestCode == REQUEST_CODE_OVERLAY) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M && Settings.canDrawOverlays(this)) {
                // Overlay granted, continue the chain
                checkPermissionsAndStart();
            } else {
                Toast.makeText(this, "Overlay permission was not granted", Toast.LENGTH_SHORT).show();
            }
        }'''
replacement = needle + ''' else if (requestCode == REQUEST_CODE_OVERLAY_RESTORE) {
            if (Build.VERSION.SDK_INT < Build.VERSION_CODES.M || Settings.canDrawOverlays(this)) {
                JoyStickManager.get().restoreJoyStick();
            } else {
                Toast.makeText(this, "Display over other apps is still disabled", Toast.LENGTH_SHORT).show();
            }
        }'''
if needle in m and 'requestCode == REQUEST_CODE_OVERLAY_RESTORE' not in m.split('protected void onActivityResult', 1)[-1]:
    m = m.replace(needle, replacement)

# Some source variants still have the original translated toast. Patch that form too.
needle2 = '''        if (requestCode == REQUEST_CODE_OVERLAY) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M && Settings.canDrawOverlays(this)) {
                // Overlay granted, continue the chain
                checkPermissionsAndStart();
            } else {
                Toast.makeText(this, "悬浮窗权限未授予", Toast.LENGTH_SHORT).show();
            }
        }'''
replacement2 = '''        if (requestCode == REQUEST_CODE_OVERLAY) {
            if (Build.VERSION.SDK_INT < Build.VERSION_CODES.M || Settings.canDrawOverlays(this)) {
                checkPermissionsAndStart();
            } else {
                Toast.makeText(this, "Display over other apps is still disabled", Toast.LENGTH_SHORT).show();
            }
        } else if (requestCode == REQUEST_CODE_OVERLAY_RESTORE) {
            if (Build.VERSION.SDK_INT < Build.VERSION_CODES.M || Settings.canDrawOverlays(this)) {
                JoyStickManager.get().restoreJoyStick();
            } else {
                Toast.makeText(this, "Display over other apps is still disabled", Toast.LENGTH_SHORT).show();
            }
        }'''
if needle2 in m:
    m = m.replace(needle2, replacement2)

# Add the OEM-safe launcher before updateBtnStart().
if 'private void openOverlaySettings(int requestCode)' not in m:
    anchor = '    private void updateBtnStart() {'
    helper = '''    private void openOverlaySettings(int requestCode) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.M) return;
        try {
            Intent intent = new Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                    Uri.parse("package:" + getPackageName()));
            startActivityForResult(intent, requestCode);
        } catch (Throwable packagePageError) {
            try {
                startActivityForResult(new Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION), requestCode);
            } catch (Throwable ignored) {
                Toast.makeText(this,
                        "Open Settings > Apps > Special access > Display over other apps and allow GeoAvil",
                        Toast.LENGTH_LONG).show();
            }
        }
    }

'''
    if anchor not in m:
        raise SystemExit('Could not locate updateBtnStart() in MainActivity')
    m = m.replace(anchor, helper + anchor)

main.write_text(m, encoding="utf-8")

# Keep the in-app docs aligned with the actual fixed behaviour.
docs = APP / "src/main/res/layout/activity_documentation.xml"
if docs.exists():
    d = docs.read_text(encoding="utf-8")
    d = d.replace('GeoAvil 0.3.0-alpha4', 'GeoAvil 0.3.0-alpha5')
    d = d.replace(
        'Grant Display over other apps if you want the floating analogue controller.',
        'Grant Display over other apps when GeoAvil opens the Android permission page. This is required for the floating analogue controller.'
    )
    docs.write_text(d, encoding="utf-8")

print("GeoAvil alpha5 overlay-permission fix applied")
