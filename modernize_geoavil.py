#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "geoavil")
APP = ROOT / "app"


def write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def replace(path: Path, old: str, new: str, required=True):
    text = path.read_text(encoding="utf-8")
    if old not in text:
        if required:
            raise SystemExit(f"Expected text not found in {path}: {old[:100]!r}")
        return False
    path.write_text(text.replace(old, new), encoding="utf-8")
    return True


# Stable release identity. This deliberately keeps the same application id and the
# legacy repository keystore so existing GeoAvil installs can update in place.
write(APP / "build.gradle", r'''apply plugin: 'com.android.application'

android {
    namespace "com.tencent.fakegps"
    compileSdk 34

    defaultConfig {
        applicationId "com.github.fakegps"
        minSdk 23
        targetSdk 34
        versionCode 30001
        versionName "0.3.0-alpha1"
    }

    buildFeatures {
        aidl true
    }

    signingConfigs {
        geoavil {
            storeFile file('../keystore.debug.jks')
            storePassword 'apptest'
            keyAlias 'apptest'
            keyPassword 'apptest'
        }
    }

    buildTypes {
        debug {
            signingConfig signingConfigs.geoavil
        }
        release {
            signingConfig signingConfigs.geoavil
            minifyEnabled false
            proguardFiles getDefaultProguardFile('proguard-android.txt'), 'proguard-rules.pro'
        }
    }

    applicationVariants.configureEach { variant ->
        variant.outputs.configureEach { output ->
            outputFileName = "GeoAvil-Android-${variant.versionName}-${variant.buildType.name}.apk"
        }
    }

    compileOptions {
        sourceCompatibility JavaVersion.VERSION_17
        targetCompatibility JavaVersion.VERSION_17
    }

    lint {
        abortOnError false
    }
}

dependencies {
    implementation fileTree(include: ['*.jar'], dir: 'libs')
    testImplementation 'junit:junit:4.13.2'
    implementation files('libs/lite-orm-1.9.2.jar')
    implementation project(':loggerlibrary')
    implementation 'androidx.appcompat:appcompat:1.7.0'
    implementation 'androidx.core:core:1.13.1'
    implementation 'androidx.localbroadcastmanager:localbroadcastmanager:1.1.0'
    implementation 'com.google.android.material:material:1.12.0'
    implementation 'dev.rikka.shizuku:api:13.1.5'
    implementation 'dev.rikka.shizuku:provider:13.1.5'
}
''')

# Material 3 globally. Dynamic colour is enabled from the Application below.
write(APP / "src/main/res/values/styles.xml", r'''<resources>
    <style name="Theme.GeoAvil" parent="Theme.Material3.DayNight">
        <item name="android:windowActionModeOverlay">true</item>
        <item name="materialAlertDialogTheme">@style/ThemeOverlay.Material3.MaterialAlertDialog</item>
    </style>

    <!-- Keep the old names as aliases so every existing activity/layout inherits MD3. -->
    <style name="AppTheme" parent="Theme.GeoAvil" />
    <style name="FullscreenTheme" parent="Theme.GeoAvil" />
    <style name="FullscreenActionBarStyle" parent="Widget.Material3.ActionBar.Solid" />
</resources>
''')

# Main screen rebuilt with MD3 components while preserving every ID used by the
# existing Java controller and the GeoAvil analog/mock-status patch.
write(APP / "src/main/res/layout/activity_main.xml", r'''<?xml version="1.0" encoding="utf-8"?>
<androidx.core.widget.NestedScrollView
    xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:app="http://schemas.android.com/apk/res-auto"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    android:fillViewport="true"
    android:clipToPadding="false"
    android:padding="16dp">

    <LinearLayout
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:orientation="vertical">

        <com.google.android.material.card.MaterialCardView
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            app:cardCornerRadius="28dp"
            app:cardUseCompatPadding="true">

            <LinearLayout
                android:id="@+id/ll_edit"
                android:layout_width="match_parent"
                android:layout_height="wrap_content"
                android:orientation="vertical"
                android:padding="16dp">

                <TextView
                    android:layout_width="wrap_content"
                    android:layout_height="wrap_content"
                    android:text="@string/location"
                    android:textAppearance="?attr/textAppearanceTitleLarge" />

                <com.google.android.material.textfield.TextInputLayout
                    android:layout_width="match_parent"
                    android:layout_height="wrap_content"
                    android:layout_marginTop="12dp"
                    android:hint="@string/loc_input_hint"
                    app:boxBackgroundMode="outline">

                    <com.google.android.material.textfield.TextInputEditText
                        android:id="@+id/inputLoc"
                        android:layout_width="match_parent"
                        android:layout_height="wrap_content"
                        android:inputType="text" />
                </com.google.android.material.textfield.TextInputLayout>

                <com.google.android.material.textfield.TextInputLayout
                    android:id="@+id/ll_move_step"
                    android:layout_width="match_parent"
                    android:layout_height="wrap_content"
                    android:layout_marginTop="10dp"
                    android:hint="@string/move_step"
                    app:boxBackgroundMode="outline"
                    app:helperText="@string/move_step_hint">

                    <com.google.android.material.textfield.TextInputEditText
                        android:id="@+id/inputStep"
                        android:layout_width="match_parent"
                        android:layout_height="wrap_content"
                        android:inputType="numberDecimal" />
                </com.google.android.material.textfield.TextInputLayout>

                <com.google.android.material.checkbox.MaterialCheckBox
                    android:id="@+id/checkbox_auto_show_analog"
                    android:layout_width="match_parent"
                    android:layout_height="wrap_content"
                    android:layout_marginTop="8dp"
                    android:text="Show analog automatically when starting" />

                <com.google.android.material.button.MaterialButton
                    android:id="@+id/btn_restore_analog"
                    style="@style/Widget.Material3.Button.OutlinedButton"
                    android:layout_width="match_parent"
                    android:layout_height="wrap_content"
                    android:layout_marginTop="6dp"
                    android:text="Restore analog" />
            </LinearLayout>
        </com.google.android.material.card.MaterialCardView>

        <TextView
            android:id="@+id/tv_bookmark"
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:layout_marginStart="4dp"
            android:layout_marginTop="18dp"
            android:layout_marginEnd="4dp"
            android:layout_marginBottom="8dp"
            android:text="@string/bookmark"
            android:textAppearance="?attr/textAppearanceTitleMedium" />

        <com.google.android.material.card.MaterialCardView
            android:id="@+id/fl_list"
            android:layout_width="match_parent"
            android:layout_height="280dp"
            app:cardCornerRadius="24dp">

            <FrameLayout
                android:layout_width="match_parent"
                android:layout_height="match_parent">

                <ListView
                    android:id="@+id/list_bookmark"
                    android:layout_width="match_parent"
                    android:layout_height="match_parent"
                    android:cacheColorHint="@android:color/transparent"
                    android:divider="@android:color/transparent"
                    android:dividerHeight="4dp"
                    android:padding="8dp" />

                <TextView
                    android:id="@+id/empty_view"
                    android:layout_width="wrap_content"
                    android:layout_height="wrap_content"
                    android:layout_gravity="center"
                    android:text="@string/no_data"
                    android:textAppearance="?attr/textAppearanceBodyLarge" />
            </FrameLayout>
        </com.google.android.material.card.MaterialCardView>

        <LinearLayout
            android:id="@+id/ll_btn_container"
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:layout_marginTop="16dp"
            android:gravity="center_vertical"
            android:orientation="horizontal">

            <com.google.android.material.button.MaterialButton
                android:id="@+id/btn_start"
                android:layout_width="0dp"
                android:layout_height="wrap_content"
                android:layout_weight="1"
                android:text="@string/btn_start" />

            <com.google.android.material.button.MaterialButton
                android:id="@+id/btn_set_loc"
                style="@style/Widget.Material3.Button.TonalButton"
                android:layout_width="0dp"
                android:layout_height="wrap_content"
                android:layout_marginStart="8dp"
                android:layout_weight="1"
                android:text="@string/btn_set_new_loc" />
        </LinearLayout>
    </LinearLayout>
</androidx.core.widget.NestedScrollView>
''')

# Floating controller in a Material surface; custom analog view obtains its colours
# from the active MD3 scheme.
write(APP / "src/main/res/layout/joystick_layout.xml", r'''<?xml version="1.0" encoding="utf-8"?>
<com.google.android.material.card.MaterialCardView
    xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:app="http://schemas.android.com/apk/res-auto"
    android:layout_width="@dimen/joystick_width"
    android:layout_height="@dimen/joystick_height"
    app:cardCornerRadius="28dp"
    app:cardElevation="6dp">

    <LinearLayout
        android:layout_width="match_parent"
        android:layout_height="match_parent"
        android:orientation="vertical"
        android:padding="6dp">

        <LinearLayout
            android:layout_width="match_parent"
            android:layout_height="34dp"
            android:orientation="horizontal">

            <com.google.android.material.button.MaterialButton
                android:id="@+id/btn_set_loc"
                style="@style/Widget.Material3.Button.TextButton"
                android:layout_width="0dp"
                android:layout_height="34dp"
                android:layout_weight="1"
                android:minHeight="0dp"
                android:minWidth="0dp"
                android:padding="0dp"
                android:text="Set"
                android:textSize="10sp" />

            <com.google.android.material.button.MaterialButton
                android:id="@+id/btn_fly_to"
                style="@style/Widget.Material3.Button.TextButton"
                android:layout_width="0dp"
                android:layout_height="34dp"
                android:layout_weight="1"
                android:minHeight="0dp"
                android:minWidth="0dp"
                android:padding="0dp"
                android:text="Fly"
                android:textSize="10sp" />

            <com.google.android.material.button.MaterialButton
                android:id="@+id/btn_bookmark"
                style="@style/Widget.Material3.Button.TextButton"
                android:layout_width="0dp"
                android:layout_height="34dp"
                android:layout_weight="1"
                android:minHeight="0dp"
                android:minWidth="0dp"
                android:padding="0dp"
                android:text="Save"
                android:textSize="10sp" />
        </LinearLayout>

        <com.github.fakegps.ui.AnalogJoystickView
            android:id="@+id/analog_joystick"
            android:layout_width="150dp"
            android:layout_height="150dp"
            android:layout_gravity="center"
            android:contentDescription="Analog movement joystick" />

        <com.google.android.material.button.MaterialButton
            android:id="@+id/btn_hide_joystick"
            style="@style/Widget.Material3.Button.TextButton"
            android:layout_width="match_parent"
            android:layout_height="32dp"
            android:minHeight="0dp"
            android:text="Hide"
            android:textSize="10sp" />
    </LinearLayout>
</com.google.android.material.card.MaterialCardView>
''')

write(APP / "src/main/java/com/github/fakegps/ui/AnalogJoystickView.java", r'''package com.github.fakegps.ui;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.PointF;
import android.util.AttributeSet;
import android.view.MotionEvent;
import android.view.View;

import com.google.android.material.color.MaterialColors;
import com.tencent.fakegps.R;

/** Material 3 floating analog stick. Values are normalized to -1..1. */
public class AnalogJoystickView extends View {
    public interface Listener {
        void onMove(float x, float y);
        void onRelease();
    }

    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final PointF knob = new PointF();
    private Listener listener;
    private float radius;
    private float knobRadius;

    public AnalogJoystickView(Context context, AttributeSet attrs) {
        super(context, attrs);
        setFocusable(true);
        paint.setStyle(Paint.Style.FILL);
    }

    public void setListener(Listener listener) {
        this.listener = listener;
    }

    @Override
    protected void onSizeChanged(int width, int height, int oldWidth, int oldHeight) {
        radius = Math.min(width, height) * 0.42f;
        knobRadius = radius * 0.34f;
        centerKnob();
    }

    private void centerKnob() {
        knob.set(getWidth() / 2f, getHeight() / 2f);
    }

    @Override
    protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        float cx = getWidth() / 2f;
        float cy = getHeight() / 2f;
        int surface = MaterialColors.getColor(this, com.google.android.material.R.attr.colorSurfaceContainerHighest);
        int primary = MaterialColors.getColor(this, com.google.android.material.R.attr.colorPrimary);
        paint.setColor(surface);
        canvas.drawCircle(cx, cy, radius, paint);
        paint.setColor(primary);
        canvas.drawCircle(knob.x, knob.y, knobRadius, paint);
    }

    @Override
    public boolean onTouchEvent(MotionEvent event) {
        if (event.getAction() == MotionEvent.ACTION_UP || event.getAction() == MotionEvent.ACTION_CANCEL) {
            centerKnob();
            invalidate();
            if (listener != null) listener.onRelease();
            return true;
        }
        if (event.getAction() == MotionEvent.ACTION_DOWN || event.getAction() == MotionEvent.ACTION_MOVE) {
            float cx = getWidth() / 2f;
            float cy = getHeight() / 2f;
            float dx = event.getX() - cx;
            float dy = event.getY() - cy;
            float distance = (float) Math.hypot(dx, dy);
            float max = Math.max(1f, radius - knobRadius);
            if (distance > max) {
                dx = dx / distance * max;
                dy = dy / distance * max;
            }
            knob.set(cx + dx, cy + dy);
            invalidate();
            if (listener != null) listener.onMove(dx / max, dy / max);
            return true;
        }
        return true;
    }
}
''')

# Shizuku UserService AIDL. Transaction 16777114 is the reserved Shizuku destroy call.
write(APP / "src/main/aidl/com/github/fakegps/IGeoAvilService.aidl", r'''package com.github.fakegps;

interface IGeoAvilService {
    void destroy() = 16777114;
    int backendUid() = 1;
    boolean setupProviders() = 2;
    boolean publish(double latitude, double longitude, long time) = 3;
    void removeProviders() = 4;
}
''')

write(APP / "src/main/java/com/github/fakegps/ShizukuLocationService.java", r'''package com.github.fakegps;

import android.content.Context;
import android.location.Location;
import android.os.IBinder;
import android.os.SystemClock;
import android.system.Os;

import androidx.annotation.Keep;

import java.lang.reflect.Method;
import java.util.Locale;
import java.util.concurrent.TimeUnit;

/**
 * Runs inside Shizuku/Sui UserService. Shell UID uses Android's supported test-provider
 * commands. UID 0 uses LocationManagerService.injectLocation so the injected Location is
 * not created by a test provider and therefore is not tagged as mock by that API path.
 */
public final class ShizukuLocationService extends IGeoAvilService.Stub {
    public ShizukuLocationService() { }

    @Keep
    public ShizukuLocationService(Context context) { }

    @Override
    public int backendUid() {
        return Os.getuid();
    }

    @Override
    public boolean setupProviders() {
        if (backendUid() == 0) {
            return getLocationBinder() != null;
        }
        run("cmd location providers add-test-provider gps");
        run("cmd location providers add-test-provider network");
        boolean gps = run("cmd location providers set-test-provider-enabled gps true");
        boolean network = run("cmd location providers set-test-provider-enabled network true");
        return gps && network;
    }

    @Override
    public boolean publish(double latitude, double longitude, long time) {
        if (backendUid() == 0) {
            return inject("gps", latitude, longitude, time)
                    && inject("network", latitude, longitude, time);
        }
        String value = String.format(Locale.US, "%f,%f", latitude, longitude);
        String command = "cmd location providers set-test-provider-location %s --location %s --time %d";
        return run(String.format(Locale.US, command, "gps", value, time))
                && run(String.format(Locale.US, command, "network", value, time));
    }

    @Override
    public void removeProviders() {
        if (backendUid() == 0) return;
        run("cmd location providers set-test-provider-enabled gps false");
        run("cmd location providers set-test-provider-enabled network false");
        run("cmd location providers remove-test-provider gps");
        run("cmd location providers remove-test-provider network");
    }

    @Override
    public void destroy() {
        try { removeProviders(); } catch (Throwable ignored) { }
        System.exit(0);
    }

    private static Object getLocationService() {
        try {
            IBinder binder = getLocationBinder();
            if (binder == null) return null;
            Class<?> stub = Class.forName("android.location.ILocationManager$Stub");
            Method asInterface = stub.getDeclaredMethod("asInterface", IBinder.class);
            asInterface.setAccessible(true);
            return asInterface.invoke(null, binder);
        } catch (Throwable ignored) {
            return null;
        }
    }

    private static IBinder getLocationBinder() {
        try {
            Class<?> sm = Class.forName("android.os.ServiceManager");
            Method getService = sm.getDeclaredMethod("getService", String.class);
            getService.setAccessible(true);
            return (IBinder) getService.invoke(null, "location");
        } catch (Throwable ignored) {
            return null;
        }
    }

    private static boolean inject(String provider, double latitude, double longitude, long time) {
        try {
            Object service = getLocationService();
            if (service == null) return false;
            Location location = new Location(provider);
            location.setLatitude(latitude);
            location.setLongitude(longitude);
            location.setAccuracy(1.0f);
            location.setTime(time > 0 ? time : System.currentTimeMillis());
            location.setElapsedRealtimeNanos(SystemClock.elapsedRealtimeNanos());
            Class<?> iface = Class.forName("android.location.ILocationManager");
            Method inject = iface.getMethod("injectLocation", Location.class);
            inject.invoke(service, location);
            return true;
        } catch (Throwable ignored) {
            return false;
        }
    }

    private static boolean run(String command) {
        Process process = null;
        try {
            process = new ProcessBuilder("/system/bin/sh", "-c", command)
                    .redirectErrorStream(true)
                    .start();
            boolean finished = process.waitFor(5, TimeUnit.SECONDS);
            return finished && process.exitValue() == 0;
        } catch (Throwable ignored) {
            return false;
        } finally {
            if (process != null) {
                try { process.destroy(); } catch (Throwable ignored) { }
            }
        }
    }
}
''')

write(APP / "src/main/java/com/github/fakegps/RootBridge.java", r'''package com.github.fakegps;

import android.content.ComponentName;
import android.content.Context;
import android.content.ServiceConnection;
import android.content.pm.PackageManager;
import android.os.IBinder;

import java.util.Locale;
import java.util.concurrent.TimeUnit;

import rikka.shizuku.Shizuku;

/**
 * Privileged backend chooser.
 *
 * Preferred: Shizuku/Sui UserService (shell on rootless devices, UID 0 on root-backed
 * Shizuku/Sui). Legacy su test-provider commands are retained only as a fallback.
 */
public final class RootBridge {
    private static final int SHIZUKU_PERMISSION = 0x4703;
    private static final int SERVICE_VERSION = 30001;

    private static volatile Context appContext;
    private static volatile IGeoAvilService service;
    private static volatile boolean binding;
    private static volatile boolean listenersAdded;

    private RootBridge() { }

    public static synchronized void init(Context context) {
        appContext = context.getApplicationContext();
        if (listenersAdded) return;
        listenersAdded = true;

        Shizuku.addBinderReceivedListenerSticky(() -> {
            try {
                if (Shizuku.checkSelfPermission() == PackageManager.PERMISSION_GRANTED) {
                    bindUserService();
                } else if (!Shizuku.shouldShowRequestPermissionRationale()) {
                    Shizuku.requestPermission(SHIZUKU_PERMISSION);
                }
            } catch (Throwable ignored) { }
        });
        Shizuku.addBinderDeadListener(() -> {
            service = null;
            binding = false;
        });
        Shizuku.addRequestPermissionResultListener((requestCode, grantResult) -> {
            if (requestCode == SHIZUKU_PERMISSION && grantResult == PackageManager.PERMISSION_GRANTED) {
                bindUserService();
            }
        });
    }

    private static synchronized void bindUserService() {
        if (appContext == null || service != null || binding) return;
        try {
            ComponentName component = new ComponentName(appContext.getPackageName(),
                    ShizukuLocationService.class.getName());
            Shizuku.UserServiceArgs args = new Shizuku.UserServiceArgs(component)
                    .processNameSuffix("geoavil")
                    .daemon(false)
                    .tag("geoavil-location")
                    .version(SERVICE_VERSION);
            binding = true;
            Shizuku.bindUserService(args, CONNECTION);
        } catch (Throwable ignored) {
            binding = false;
        }
    }

    private static final ServiceConnection CONNECTION = new ServiceConnection() {
        @Override
        public void onServiceConnected(ComponentName name, IBinder binder) {
            service = IGeoAvilService.Stub.asInterface(binder);
            binding = false;
        }

        @Override
        public void onServiceDisconnected(ComponentName name) {
            service = null;
            binding = false;
        }
    };

    public static boolean setupProviders() {
        IGeoAvilService remote = service;
        if (remote != null) {
            try { return remote.setupProviders(); } catch (Throwable ignored) { service = null; }
        }

        // Keep a rooted fallback for devices without Shizuku/Sui. This path still uses
        // test providers and therefore Android can report isMock=true.
        runRoot("cmd location providers add-test-provider gps");
        runRoot("cmd location providers add-test-provider network");
        boolean gps = runRoot("cmd location providers set-test-provider-enabled gps true");
        boolean network = runRoot("cmd location providers set-test-provider-enabled network true");
        return gps && network;
    }

    public static void removeProviders() {
        IGeoAvilService remote = service;
        if (remote != null) {
            try { remote.removeProviders(); return; } catch (Throwable ignored) { service = null; }
        }
        runRoot("cmd location providers set-test-provider-enabled gps false");
        runRoot("cmd location providers set-test-provider-enabled network false");
        runRoot("cmd location providers remove-test-provider gps");
        runRoot("cmd location providers remove-test-provider network");
    }

    public static boolean publish(double latitude, double longitude, long time) {
        IGeoAvilService remote = service;
        if (remote != null) {
            try { return remote.publish(latitude, longitude, time); } catch (Throwable ignored) { service = null; }
        }
        String location = String.format(Locale.US, "%f,%f", latitude, longitude);
        String command = "cmd location providers set-test-provider-location %s --location %s --time %d";
        return runRoot(String.format(Locale.US, command, "gps", location, time))
                && runRoot(String.format(Locale.US, command, "network", location, time));
    }

    public static int privilegedUid() {
        IGeoAvilService remote = service;
        if (remote == null) return -1;
        try { return remote.backendUid(); } catch (Throwable ignored) { return -1; }
    }

    public static String backendLabel() {
        int uid = privilegedUid();
        if (uid == 0) return "Shizuku/Sui root · direct LocationManager injection";
        if (uid == 2000) return "Shizuku shell · test-provider backend";
        if (uid >= 0) return "Shizuku UID " + uid;
        return "Legacy/fallback backend";
    }

    private static boolean runRoot(String command) {
        Process process = null;
        try {
            process = new ProcessBuilder("su", "-c", command)
                    .redirectErrorStream(true)
                    .start();
            boolean finished = process.waitFor(5, TimeUnit.SECONDS);
            return finished && process.exitValue() == 0;
        } catch (Throwable ignored) {
            return false;
        } finally {
            if (process != null) {
                try { process.destroy(); } catch (Throwable ignored) { }
            }
        }
    }
}
''')

# Initialise Shizuku as part of the existing manager init and enable Material You dynamic colours.
replace(APP / "src/main/java/com/github/fakegps/JoyStickManager.java",
        "        mContext = context;\n",
        "        mContext = context;\n        RootBridge.init(context);\n")
replace(APP / "src/main/java/com/github/fakegps/FakeGpsApp.java",
        "import com.litesuits.orm.LiteOrm;\n",
        "import com.litesuits.orm.LiteOrm;\nimport com.google.android.material.color.DynamicColors;\n")
replace(APP / "src/main/java/com/github/fakegps/FakeGpsApp.java",
        "        super.onCreate();\n        initLogger();\n",
        "        super.onCreate();\n        DynamicColors.applyToActivitiesIfAvailable(this);\n        initLogger();\n")

# Merge Shizuku provider and switch the dialog activity away from legacy AppCompat styling.
manifest = APP / "src/main/AndroidManifest.xml"
text = manifest.read_text(encoding="utf-8")
text = text.replace('<manifest xmlns:android="http://schemas.android.com/apk/res/android">',
                    '<manifest xmlns:android="http://schemas.android.com/apk/res/android"\n    xmlns:tools="http://schemas.android.com/tools">')
if 'moe.shizuku.manager.permission.API_V23' not in text:
    text = text.replace('    <uses-permission android:name="android.permission.RECEIVE_BOOT_COMPLETED"/>',
                        '    <uses-permission android:name="android.permission.RECEIVE_BOOT_COMPLETED"/>\n    <uses-permission android:name="moe.shizuku.manager.permission.API_V23"/>')
text = text.replace('android:theme="@style/Theme.AppCompat.Dialog"', 'android:theme="@style/Theme.GeoAvil"')
provider = r'''
        <provider
            android:name="rikka.shizuku.ShizukuProvider"
            android:authorities="${applicationId}.shizuku"
            android:enabled="true"
            android:exported="true"
            android:multiprocess="false"
            android:permission="android.permission.INTERACT_ACROSS_USERS_FULL"
            tools:replace="android:authorities" />
'''
if 'rikka.shizuku.ShizukuProvider' not in text:
    text = text.replace('        <service\n            android:name="com.github.fakegps.FakeLocationService"',
                        provider + '\n        <service\n            android:name="com.github.fakegps.FakeLocationService"')
manifest.write_text(text, encoding="utf-8")

# Add backend information to the existing mock-status tester. Root direct injection is expected
# to show isMock=false; shell/test-provider mode remains correctly reported as mock.
main = APP / "src/main/java/com/github/fakegps/ui/MainActivity.java"
mt = main.read_text(encoding="utf-8")
if 'Backend: " + RootBridge.backendLabel()' not in mt:
    if 'import com.github.fakegps.JoyStickManager;' in mt and 'import com.github.fakegps.RootBridge;' not in mt:
        mt = mt.replace('import com.github.fakegps.JoyStickManager;\n',
                        'import com.github.fakegps.JoyStickManager;\nimport com.github.fakegps.RootBridge;\n')
    needle = 'builder.append("Source: Android LocationManager cache\\n");'
    if needle in mt:
        mt = mt.replace(needle, 'builder.append("Backend: ").append(RootBridge.backendLabel()).append("\\n");\n            ' + needle)
main.write_text(mt, encoding="utf-8")

print("GeoAvil modernization applied: 0.3.0-alpha1 / versionCode 30001")
