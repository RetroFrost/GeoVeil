#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "geoavil")
APP = ROOT / "app"


def write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def replace(path: Path, old: str, new: str):
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"Expected text not found in {path}: {old[:120]!r}")
    path.write_text(text.replace(old, new), encoding="utf-8")


# Release bump: documentation is user-visible functionality.
build = APP / "build.gradle"
text = build.read_text(encoding="utf-8")
text = text.replace('versionCode 30003', 'versionCode 30004')
text = text.replace('versionName "0.3.0-alpha3"', 'versionName "0.3.0-alpha4"')
build.write_text(text, encoding="utf-8")

# A dedicated NoActionBar MD3 theme for the documentation activity.
styles = APP / "src/main/res/values/styles.xml"
style_text = styles.read_text(encoding="utf-8")
if 'Theme.GeoAvil.Documentation' not in style_text:
    style_text = style_text.replace(
        '</resources>',
        '''    <style name="Theme.GeoAvil.Documentation" parent="Theme.Material3.DayNight.NoActionBar">\n'''
        '''        <item name="materialAlertDialogTheme">@style/ThemeOverlay.Material3.MaterialAlertDialog</item>\n'''
        '''    </style>\n</resources>'''
    )
styles.write_text(style_text, encoding="utf-8")

# Add a clearly visible Help & documentation button to the main MD3 card.
main_layout = APP / "src/main/res/layout/activity_main.xml"
layout = main_layout.read_text(encoding="utf-8")
anchor = '''                <com.google.android.material.button.MaterialButton\n                    android:id="@+id/btn_restore_analog"\n                    style="@style/Widget.Material3.Button.OutlinedButton"\n                    android:layout_width="match_parent"\n                    android:layout_height="wrap_content"\n                    android:layout_marginTop="6dp"\n                    android:text="Restore analog" />'''
replacement = anchor + '''\n\n                <com.google.android.material.button.MaterialButton\n                    android:id="@+id/btn_documentation"\n                    style="@style/Widget.Material3.Button.TextButton"\n                    android:layout_width="match_parent"\n                    android:layout_height="wrap_content"\n                    android:layout_marginTop="4dp"\n                    android:text="Help &amp; documentation"\n                    app:icon="@android:drawable/ic_menu_help"\n                    app:iconGravity="textStart" />'''
if 'btn_documentation' not in layout:
    if anchor not in layout:
        raise SystemExit('Could not find Restore analog button in activity_main.xml')
    layout = layout.replace(anchor, replacement)
main_layout.write_text(layout, encoding="utf-8")

# Wire the new button into the existing MainActivity without changing the start/spoof path.
main = APP / "src/main/java/com/github/fakegps/ui/MainActivity.java"
main_text = main.read_text(encoding="utf-8")
if 'DocumentationActivity.start(this)' not in main_text:
    main_text = main_text.replace(
        '        initListView();\n\n        registerBroadcastReceiver();',
        '        initListView();\n\n        findViewById(R.id.btn_documentation).setOnClickListener(v -> DocumentationActivity.start(this));\n\n        registerBroadcastReceiver();'
    )
main.write_text(main_text, encoding="utf-8")

# Documentation activity: deliberately static/offline so setup help is always available.
write(APP / "src/main/java/com/github/fakegps/ui/DocumentationActivity.java", r'''package com.github.fakegps.ui;

import android.content.Context;
import android.content.Intent;
import android.os.Bundle;

import androidx.appcompat.app.AppCompatActivity;

import com.google.android.material.appbar.MaterialToolbar;
import com.tencent.fakegps.R;

public final class DocumentationActivity extends AppCompatActivity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_documentation);

        MaterialToolbar toolbar = findViewById(R.id.documentation_toolbar);
        toolbar.setNavigationOnClickListener(v -> finish());
    }

    public static void start(Context context) {
        context.startActivity(new Intent(context, DocumentationActivity.class));
    }
}
''')

write(APP / "src/main/res/layout/activity_documentation.xml", r'''<?xml version="1.0" encoding="utf-8"?>
<androidx.coordinatorlayout.widget.CoordinatorLayout
    xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:app="http://schemas.android.com/apk/res-auto"
    android:layout_width="match_parent"
    android:layout_height="match_parent">

    <com.google.android.material.appbar.AppBarLayout
        android:layout_width="match_parent"
        android:layout_height="wrap_content">

        <com.google.android.material.appbar.MaterialToolbar
            android:id="@+id/documentation_toolbar"
            android:layout_width="match_parent"
            android:layout_height="?attr/actionBarSize"
            android:title="GeoAvil documentation"
            app:navigationIcon="@android:drawable/ic_media_previous" />
    </com.google.android.material.appbar.AppBarLayout>

    <androidx.core.widget.NestedScrollView
        android:layout_width="match_parent"
        android:layout_height="match_parent"
        android:clipToPadding="false"
        android:paddingStart="16dp"
        android:paddingEnd="16dp"
        android:paddingBottom="32dp"
        app:layout_behavior="@string/appbar_scrolling_view_behavior">

        <LinearLayout
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:orientation="vertical">

            <TextView
                android:layout_width="match_parent"
                android:layout_height="wrap_content"
                android:layout_marginTop="20dp"
                android:text="GeoAvil 0.3.0-alpha4"
                android:textAppearance="?attr/textAppearanceHeadlineMedium" />

            <TextView
                android:layout_width="match_parent"
                android:layout_height="wrap_content"
                android:layout_marginTop="6dp"
                android:layout_marginBottom="18dp"
                android:text="Location spoofing with a floating analogue controller. GeoAvil can use Shizuku without root, or a rooted Shizuku/Sui + LSPosed path for additional system integration."
                android:textAppearance="?attr/textAppearanceBodyLarge" />

            <com.google.android.material.card.MaterialCardView
                android:layout_width="match_parent"
                android:layout_height="wrap_content"
                android:layout_marginBottom="12dp"
                app:cardCornerRadius="24dp">
                <LinearLayout
                    android:layout_width="match_parent"
                    android:layout_height="wrap_content"
                    android:orientation="vertical"
                    android:padding="18dp">
                    <TextView
                        android:layout_width="match_parent"
                        android:layout_height="wrap_content"
                        android:text="Choose your setup"
                        android:textAppearance="?attr/textAppearanceTitleLarge" />
                    <TextView
                        android:layout_width="match_parent"
                        android:layout_height="wrap_content"
                        android:layout_marginTop="8dp"
                        android:text="Non-root: use Shizuku running through Wireless debugging or ADB.\n\nRooted: use Shizuku in root mode or Sui. For GeoAvil's system-server mock-flag handling, LSPosed must also be installed and GeoAvil must be enabled for System Framework (system)."
                        android:textAppearance="?attr/textAppearanceBodyLarge" />
                </LinearLayout>
            </com.google.android.material.card.MaterialCardView>

            <com.google.android.material.card.MaterialCardView
                android:layout_width="match_parent"
                android:layout_height="wrap_content"
                android:layout_marginBottom="12dp"
                app:cardCornerRadius="24dp">
                <LinearLayout
                    android:layout_width="match_parent"
                    android:layout_height="wrap_content"
                    android:orientation="vertical"
                    android:padding="18dp">
                    <TextView
                        android:layout_width="match_parent"
                        android:layout_height="wrap_content"
                        android:text="Non-root · Shizuku"
                        android:textAppearance="?attr/textAppearanceTitleLarge" />
                    <TextView
                        android:layout_width="match_parent"
                        android:layout_height="wrap_content"
                        android:layout_marginTop="8dp"
                        android:text="1. Start Shizuku.\n2. Open GeoAvil and grant its Shizuku permission.\n3. Grant location permission.\n4. Grant Display over other apps if you want the floating analogue controller.\n5. Pick a coordinate and movement step, then tap Start.\n6. Use Restore analog if spoofing is active but the controller is hidden.\n\nIn normal non-root Shizuku mode Android may report the generated location as mock. That is expected."
                        android:textAppearance="?attr/textAppearanceBodyLarge" />
                </LinearLayout>
            </com.google.android.material.card.MaterialCardView>

            <com.google.android.material.card.MaterialCardView
                android:layout_width="match_parent"
                android:layout_height="wrap_content"
                android:layout_marginBottom="12dp"
                app:cardCornerRadius="24dp">
                <LinearLayout
                    android:layout_width="match_parent"
                    android:layout_height="wrap_content"
                    android:orientation="vertical"
                    android:padding="18dp">
                    <TextView
                        android:layout_width="match_parent"
                        android:layout_height="wrap_content"
                        android:text="Rooted · Sui / Shizuku + LSPosed"
                        android:textAppearance="?attr/textAppearanceTitleLarge" />
                    <TextView
                        android:layout_width="match_parent"
                        android:layout_height="wrap_content"
                        android:layout_marginTop="8dp"
                        android:text="1. Start Shizuku with root, or use Sui.\n2. Grant GeoAvil access.\n3. Install and enable LSPosed.\n4. In LSPosed, enable the GeoAvil module and scope it only to System Framework (system).\n5. Reboot Android so the system-server hook loads.\n6. Open GeoAvil and start spoofing normally.\n\nWith the system hook active, GeoAvil is designed to clear the mock flag before the location is delivered to apps. Without the LSPosed system scope, spoofing may still work but Android can continue to report isMock=true."
                        android:textAppearance="?attr/textAppearanceBodyLarge" />
                </LinearLayout>
            </com.google.android.material.card.MaterialCardView>

            <com.google.android.material.card.MaterialCardView
                android:layout_width="match_parent"
                android:layout_height="wrap_content"
                android:layout_marginBottom="12dp"
                app:cardCornerRadius="24dp">
                <LinearLayout
                    android:layout_width="match_parent"
                    android:layout_height="wrap_content"
                    android:orientation="vertical"
                    android:padding="18dp">
                    <TextView
                        android:layout_width="match_parent"
                        android:layout_height="wrap_content"
                        android:text="Analogue controller"
                        android:textAppearance="?attr/textAppearanceTitleLarge" />
                    <TextView
                        android:layout_width="match_parent"
                        android:layout_height="wrap_content"
                        android:layout_marginTop="8dp"
                        android:text="Movement step controls how far one location tick moves. Smaller values give finer movement.\n\nDrag the analogue stick to move continuously. Release it to stop movement. The floating panel itself can be dragged around the screen. Use Hide to dismiss it without stopping spoofing, and Restore analog in the main app to show it again.\n\nIf the panel cannot appear, check Android's Display over other apps permission for GeoAvil."
                        android:textAppearance="?attr/textAppearanceBodyLarge" />
                </LinearLayout>
            </com.google.android.material.card.MaterialCardView>

            <com.google.android.material.card.MaterialCardView
                android:layout_width="match_parent"
                android:layout_height="wrap_content"
                android:layout_marginBottom="12dp"
                app:cardCornerRadius="24dp">
                <LinearLayout
                    android:layout_width="match_parent"
                    android:layout_height="wrap_content"
                    android:orientation="vertical"
                    android:padding="18dp">
                    <TextView
                        android:layout_width="match_parent"
                        android:layout_height="wrap_content"
                        android:text="Mock Status Tester"
                        android:textAppearance="?attr/textAppearanceTitleLarge" />
                    <TextView
                        android:layout_width="match_parent"
                        android:layout_height="wrap_content"
                        android:layout_marginTop="8dp"
                        android:text="Use the tester after spoofing starts. It reads Android's current cached Location metadata.\n\nisMock=true means Android marked that Location as mock.\nisMock=false means that particular Location does not carry the mock flag.\n\nOn rooted setups, also check the backend label. The intended system-hook setup is rooted Shizuku/Sui plus the GeoAvil LSPosed module loaded in System Framework."
                        android:textAppearance="?attr/textAppearanceBodyLarge" />
                </LinearLayout>
            </com.google.android.material.card.MaterialCardView>

            <com.google.android.material.card.MaterialCardView
                android:layout_width="match_parent"
                android:layout_height="wrap_content"
                android:layout_marginBottom="12dp"
                app:cardCornerRadius="24dp">
                <LinearLayout
                    android:layout_width="match_parent"
                    android:layout_height="wrap_content"
                    android:orientation="vertical"
                    android:padding="18dp">
                    <TextView
                        android:layout_width="match_parent"
                        android:layout_height="wrap_content"
                        android:text="Troubleshooting"
                        android:textAppearance="?attr/textAppearanceTitleLarge" />
                    <TextView
                        android:layout_width="match_parent"
                        android:layout_height="wrap_content"
                        android:layout_marginTop="8dp"
                        android:text="Spoofing does nothing: confirm Shizuku/Sui is running, GeoAvil has permission, and restart GeoAvil after restarting Shizuku.\n\nAnalogue does not appear: grant Display over other apps, then tap Restore analog. The overlay can fail independently while spoofing continues.\n\nRooted but isMock remains true: confirm LSPosed is active, GeoAvil is enabled for System Framework (system), and reboot after changing module scope.\n\nLocation jumps back: another location source or service may be replacing GeoAvil's updates. Stop other mock-location tools before testing.\n\nAfter updating GeoAvil: the signing identity is fixed, so normal updates should install over the previous GeoAvil build."
                        android:textAppearance="?attr/textAppearanceBodyLarge" />
                </LinearLayout>
            </com.google.android.material.card.MaterialCardView>

            <TextView
                android:layout_width="match_parent"
                android:layout_height="wrap_content"
                android:layout_marginTop="4dp"
                android:text="Tip: if something still fails, capture logcat immediately after reproducing it. Runtime logs are much more useful than changing the backend blindly."
                android:textAppearance="?attr/textAppearanceBodyMedium" />

        </LinearLayout>
    </androidx.core.widget.NestedScrollView>
</androidx.coordinatorlayout.widget.CoordinatorLayout>
''')

# Register the activity. Keep it non-exported; it is only an in-app help destination.
manifest = APP / "src/main/AndroidManifest.xml"
manifest_text = manifest.read_text(encoding="utf-8")
if 'DocumentationActivity' not in manifest_text:
    marker = '    </application>'
    activity = '''        <activity\n            android:name="com.github.fakegps.ui.DocumentationActivity"\n            android:exported="false"\n            android:theme="@style/Theme.GeoAvil.Documentation" />\n\n'''
    if marker not in manifest_text:
        raise SystemExit('Could not find </application> in AndroidManifest.xml')
    manifest_text = manifest_text.replace(marker, activity + marker)
manifest.write_text(manifest_text, encoding="utf-8")

print("GeoAvil 0.3.0-alpha4 in-app documentation added")
