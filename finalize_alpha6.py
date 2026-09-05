#!/usr/bin/env python3
from pathlib import Path
import re
import sys

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "geoavil")
APP = ROOT / "app"


def write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def replace_required(path: Path, old: str, new: str):
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"Expected text not found in {path}: {old[:120]!r}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def regex_replace_required(path: Path, pattern: str, replacement: str, flags=0):
    text = path.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, text, flags=flags)
    if count != 1:
        raise SystemExit(f"Expected exactly one regex match in {path}, got {count}: {pattern[:120]!r}")
    path.write_text(updated, encoding="utf-8")


# Canonical alpha6 identity and fail-the-build lint policy.
build = APP / "build.gradle"
text = build.read_text(encoding="utf-8")
text = text.replace('versionCode 30005', 'versionCode 30006')
text = text.replace('versionName "0.3.0-alpha5"', 'versionName "0.3.0-alpha6"')
text = text.replace('abortOnError false', 'abortOnError true\n        checkReleaseBuilds true')
build.write_text(text, encoding="utf-8")

# Pure geographic math. Joystick directions are screen-relative and NEVER use device
# sensors, compass, accelerometer or rotation. The configured step remains approximately
# latitude-degrees per second at full stick deflection, but east/west motion is converted
# through metres so physical speed and diagonal direction remain consistent by latitude.
write(APP / "src/main/java/com/github/fakegps/GeoMath.java", r'''package com.github.fakegps;

import com.github.fakegps.model.LocPoint;

public final class GeoMath {
    private static final double EARTH_RADIUS_M = 6371008.8;
    private static final double METERS_PER_LAT_DEGREE = 111320.0;
    private static final double MAX_LAT = 89.999999;

    private GeoMath() { }

    public static boolean isFinite(double value) {
        return !Double.isNaN(value) && !Double.isInfinite(value);
    }

    public static boolean isValidCoordinate(double latitude, double longitude) {
        return isFinite(latitude) && isFinite(longitude)
                && latitude >= -90.0 && latitude <= 90.0
                && longitude >= -180.0 && longitude <= 180.0;
    }

    public static double clampLatitude(double latitude) {
        return Math.max(-MAX_LAT, Math.min(MAX_LAT, latitude));
    }

    public static double wrapLongitude(double longitude) {
        if (!isFinite(longitude)) return 0.0;
        double wrapped = ((longitude + 180.0) % 360.0 + 360.0) % 360.0 - 180.0;
        return wrapped == -180.0 && longitude > 0.0 ? 180.0 : wrapped;
    }

    public static LocPoint moveScreenRelative(LocPoint start, float stickX, float stickY,
                                               double degreeStepPerSecond, double seconds) {
        if (start == null || !isFinite(degreeStepPerSecond) || degreeStepPerSecond <= 0
                || !isFinite(seconds) || seconds <= 0) {
            return start == null ? null : new LocPoint(start);
        }
        double x = Math.max(-1.0, Math.min(1.0, stickX));
        double y = Math.max(-1.0, Math.min(1.0, stickY));
        double magnitude = Math.hypot(x, y);
        if (magnitude > 1.0) {
            x /= magnitude;
            y /= magnitude;
        }
        if (Math.hypot(x, y) < 0.02) return new LocPoint(start);

        double metersPerSecond = degreeStepPerSecond * METERS_PER_LAT_DEGREE;
        double northMeters = -y * metersPerSecond * seconds;
        double eastMeters = x * metersPerSecond * seconds;

        double latRad = Math.toRadians(start.getLatitude());
        double newLat = start.getLatitude()
                + Math.toDegrees(northMeters / EARTH_RADIUS_M);
        newLat = clampLatitude(newLat);

        double meanLatRad = (latRad + Math.toRadians(newLat)) * 0.5;
        double cos = Math.max(1.0e-6, Math.abs(Math.cos(meanLatRad)));
        double newLon = start.getLongitude()
                + Math.toDegrees(eastMeters / (EARTH_RADIUS_M * cos));
        newLon = wrapLongitude(newLon);
        return new LocPoint(newLat, newLon);
    }

    public static double distanceMeters(LocPoint a, LocPoint b) {
        if (a == null || b == null) return 0.0;
        double lat1 = Math.toRadians(a.getLatitude());
        double lat2 = Math.toRadians(b.getLatitude());
        double dLat = lat2 - lat1;
        double dLon = Math.toRadians(b.getLongitude() - a.getLongitude());
        double sinLat = Math.sin(dLat / 2.0);
        double sinLon = Math.sin(dLon / 2.0);
        double h = sinLat * sinLat + Math.cos(lat1) * Math.cos(lat2) * sinLon * sinLon;
        return EARTH_RADIUS_M * 2.0 * Math.atan2(Math.sqrt(h), Math.sqrt(Math.max(0.0, 1.0 - h)));
    }

    public static float bearingDegrees(LocPoint from, LocPoint to) {
        if (from == null || to == null || distanceMeters(from, to) < 0.01) return 0f;
        double lat1 = Math.toRadians(from.getLatitude());
        double lat2 = Math.toRadians(to.getLatitude());
        double dLon = Math.toRadians(to.getLongitude() - from.getLongitude());
        double y = Math.sin(dLon) * Math.cos(lat2);
        double x = Math.cos(lat1) * Math.sin(lat2)
                - Math.sin(lat1) * Math.cos(lat2) * Math.cos(dLon);
        return (float) ((Math.toDegrees(Math.atan2(y, x)) + 360.0) % 360.0);
    }

    public static LocPoint interpolate(LocPoint from, LocPoint to, double factor) {
        if (from == null) return to == null ? null : new LocPoint(to);
        if (to == null) return new LocPoint(from);
        double f = Math.max(0.0, Math.min(1.0, factor));
        double lat = from.getLatitude() + (to.getLatitude() - from.getLatitude()) * f;
        double lonDelta = wrapLongitude(to.getLongitude() - from.getLongitude());
        double lon = wrapLongitude(from.getLongitude() + lonDelta * f);
        return new LocPoint(clampLatitude(lat), lon);
    }
}
''')

write(APP / "src/main/java/com/github/fakegps/FakeGpsUtils.java", r'''package com.github.fakegps;

import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.widget.EditText;

import com.github.fakegps.model.LocPoint;

import tiger.radio.loggerlibrary.Logger;

public final class FakeGpsUtils {
    private static final String TAG = "FakeGpsUtils";
    private FakeGpsUtils() { }

    public static void copyToClipboard(Context context, String content) {
        ClipboardManager clipboard = (ClipboardManager) context.getSystemService(Context.CLIPBOARD_SERVICE);
        if (clipboard != null && content != null) {
            clipboard.setPrimaryClip(ClipData.newPlainText("GeoAvil Location", content.trim()));
        }
    }

    public static LocPoint getLocPointFromInput(Context context, EditText editText) {
        if (editText == null) return null;
        String text = editText.getText().toString().replace("(", "").replace(")", "");
        String[] split = text.split(",");
        if (split.length != 2) return null;
        try {
            double lat = Double.parseDouble(split[0].trim());
            double lon = Double.parseDouble(split[1].trim());
            return GeoMath.isValidCoordinate(lat, lon) ? new LocPoint(lat, lon) : null;
        } catch (NumberFormatException e) {
            Logger.e(TAG, "Parse location error", e);
            return null;
        }
    }

    public static double getMoveStepFromInput(Context context, EditText editText) {
        if (editText == null) return 0;
        try {
            double value = Double.parseDouble(editText.getText().toString().trim());
            return GeoMath.isFinite(value) && value > 0.0 ? value : 0.0;
        } catch (NumberFormatException e) {
            Logger.e(TAG, "Parse move step error", e);
            return 0;
        }
    }

    public static int getIntValueFromInput(Context context, EditText editText) {
        if (editText == null) return 0;
        try {
            return Integer.parseInt(editText.getText().toString().trim());
        } catch (NumberFormatException e) {
            Logger.e(TAG, "Parse integer error", e);
            return 0;
        }
    }
}
''')

# Shizuku UserService. Root sessions also publish a narrow system-property marker so the
# system-server hook only sanitizes GeoAvil's own immediately-published coordinates.
write(APP / "src/main/java/com/github/fakegps/ShizukuLocationService.java", r'''package com.github.fakegps;

import android.content.Context;
import android.system.Os;

import androidx.annotation.Keep;

import java.util.Locale;
import java.util.concurrent.TimeUnit;

public final class ShizukuLocationService extends IGeoAvilService.Stub {
    public ShizukuLocationService() { }
    @Keep public ShizukuLocationService(Context context) { }

    @Override public int backendUid() { return Os.getuid(); }

    @Override
    public boolean setupProviders() {
        removeProvider("gps");
        removeProvider("network");
        boolean gpsAdd = run("cmd location providers add-test-provider gps");
        boolean netAdd = run("cmd location providers add-test-provider network");
        boolean gpsEnable = gpsAdd && run("cmd location providers set-test-provider-enabled gps true");
        boolean netEnable = netAdd && run("cmd location providers set-test-provider-enabled network true");
        boolean ok = gpsAdd && netAdd && gpsEnable && netEnable;
        if (ok && backendUid() == 0) run("setprop debug.geoavil.active 1");
        return ok;
    }

    @Override
    public boolean publish(double latitude, double longitude, long time) {
        if (!GeoMath.isValidCoordinate(latitude, longitude)) return false;
        long publishTime = time > 0 ? time : System.currentTimeMillis();
        if (backendUid() == 0) {
            String marker = String.format(Locale.US, "%d,%.7f,%.7f", publishTime, latitude, longitude);
            run("setprop debug.geoavil.target " + marker);
            run("setprop debug.geoavil.active 1");
        }
        String value = String.format(Locale.US, "%.7f,%.7f", latitude, longitude);
        String command = "cmd location providers set-test-provider-location %s --location %s --time %d";
        boolean gps = run(String.format(Locale.US, command, "gps", value, publishTime));
        boolean network = run(String.format(Locale.US, command, "network", value, publishTime));
        return gps && network;
    }

    @Override
    public void removeProviders() {
        removeProvider("gps");
        removeProvider("network");
        if (backendUid() == 0) {
            run("setprop debug.geoavil.active 0");
            run("setprop debug.geoavil.target ''");
        }
    }

    private static void removeProvider(String provider) {
        run("cmd location providers set-test-provider-enabled " + provider + " false");
        run("cmd location providers remove-test-provider " + provider);
    }

    @Override public void destroy() {
        try { removeProviders(); } catch (Throwable ignored) { }
        System.exit(0);
    }

    private static boolean run(String command) {
        Process process = null;
        try {
            process = new ProcessBuilder("/system/bin/sh", "-c", command).redirectErrorStream(true).start();
            if (!process.waitFor(4, TimeUnit.SECONDS)) {
                process.destroyForcibly();
                return false;
            }
            return process.exitValue() == 0;
        } catch (Throwable ignored) {
            return false;
        } finally {
            if (process != null) try { process.destroy(); } catch (Throwable ignored) { }
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
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

import rikka.shizuku.Shizuku;

public final class RootBridge {
    private enum Backend { NONE, SHIZUKU, ROOT }

    private static final int SHIZUKU_PERMISSION = 0x4703;
    private static final int SERVICE_VERSION = 30006;
    private static final long BIND_WAIT_MS = 3500L;

    private static volatile Context appContext;
    private static volatile IGeoAvilService service;
    private static volatile boolean binding;
    private static volatile boolean listenersAdded;
    private static volatile CountDownLatch bindLatch = new CountDownLatch(0);
    private static volatile Backend backend = Backend.NONE;
    private static volatile Boolean rootAvailable;
    private static volatile String lastError = "Not started";

    private RootBridge() { }

    public static synchronized void init(Context context) {
        appContext = context.getApplicationContext();
        if (listenersAdded) return;
        listenersAdded = true;
        Shizuku.addBinderReceivedListenerSticky(() -> {
            try {
                if (Shizuku.checkSelfPermission() == PackageManager.PERMISSION_GRANTED) bindUserService();
                else if (!Shizuku.shouldShowRequestPermissionRationale()) Shizuku.requestPermission(SHIZUKU_PERMISSION);
            } catch (Throwable ignored) { }
        });
        Shizuku.addBinderDeadListener(() -> {
            service = null;
            binding = false;
            releaseBindWaiters();
        });
        Shizuku.addRequestPermissionResultListener((requestCode, grantResult) -> {
            if (requestCode == SHIZUKU_PERMISSION && grantResult == PackageManager.PERMISSION_GRANTED) bindUserService();
        });
    }

    private static void releaseBindWaiters() {
        CountDownLatch latch = bindLatch;
        while (latch.getCount() > 0) latch.countDown();
    }

    public static boolean shizukuGranted() {
        try {
            return Shizuku.pingBinder() && Shizuku.checkSelfPermission() == PackageManager.PERMISSION_GRANTED;
        } catch (Throwable ignored) {
            return false;
        }
    }

    private static synchronized void bindUserService() {
        if (appContext == null || service != null || binding || !shizukuGranted()) return;
        try {
            ComponentName component = new ComponentName(appContext.getPackageName(), ShizukuLocationService.class.getName());
            Shizuku.UserServiceArgs args = new Shizuku.UserServiceArgs(component)
                    .processNameSuffix("geoavil").daemon(false).tag("geoavil-location").version(SERVICE_VERSION);
            bindLatch = new CountDownLatch(1);
            binding = true;
            Shizuku.bindUserService(args, CONNECTION);
        } catch (Throwable t) {
            binding = false;
            lastError = "Unable to bind Shizuku UserService: " + t.getClass().getSimpleName();
            releaseBindWaiters();
        }
    }

    private static final ServiceConnection CONNECTION = new ServiceConnection() {
        @Override public void onServiceConnected(ComponentName name, IBinder binder) {
            service = IGeoAvilService.Stub.asInterface(binder);
            binding = false;
            releaseBindWaiters();
        }
        @Override public void onServiceDisconnected(ComponentName name) {
            service = null;
            binding = false;
            releaseBindWaiters();
        }
    };

    private static IGeoAvilService awaitService() {
        IGeoAvilService remote = service;
        if (remote != null) return remote;
        if (!shizukuGranted()) return null;
        bindUserService();
        try {
            CountDownLatch latch = bindLatch;
            if (latch.getCount() > 0) latch.await(BIND_WAIT_MS, TimeUnit.MILLISECONDS);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
        return service;
    }

    public static boolean hasRoot() {
        Boolean cached = rootAvailable;
        if (cached != null) return cached;
        boolean available = runRoot("id");
        rootAvailable = available;
        return available;
    }

    public static boolean privilegedBackendExpected() {
        return shizukuGranted() || hasRoot();
    }

    public static synchronized boolean setupProviders() {
        backend = Backend.NONE;
        if (shizukuGranted()) {
            IGeoAvilService remote = awaitService();
            if (remote == null) {
                lastError = "Shizuku permission is granted but its UserService did not connect";
                return false;
            }
            try {
                if (remote.setupProviders()) {
                    backend = Backend.SHIZUKU;
                    lastError = "";
                    return true;
                }
                lastError = "Shizuku connected, but Android rejected test-provider setup";
                return false;
            } catch (Throwable t) {
                service = null;
                lastError = "Shizuku provider setup failed: " + t.getClass().getSimpleName();
                return false;
            }
        }
        if (hasRoot()) {
            removeRootProvider("gps");
            removeRootProvider("network");
            boolean gpsAdd = runRoot("cmd location providers add-test-provider gps");
            boolean netAdd = runRoot("cmd location providers add-test-provider network");
            boolean gpsEnable = gpsAdd && runRoot("cmd location providers set-test-provider-enabled gps true");
            boolean netEnable = netAdd && runRoot("cmd location providers set-test-provider-enabled network true");
            if (gpsAdd && netAdd && gpsEnable && netEnable) {
                runRoot("setprop debug.geoavil.active 1");
                backend = Backend.ROOT;
                lastError = "";
                return true;
            }
            removeRootProvider("gps");
            removeRootProvider("network");
            lastError = "Root is available, but Android rejected test-provider setup";
            return false;
        }
        lastError = "No privileged backend available";
        return false;
    }

    public static boolean publish(double latitude, double longitude, long time) {
        if (!GeoMath.isValidCoordinate(latitude, longitude)) {
            lastError = "Refusing invalid coordinates";
            return false;
        }
        Backend selected = backend;
        if (selected == Backend.SHIZUKU) {
            IGeoAvilService remote = service != null ? service : awaitService();
            if (remote == null) {
                lastError = "Shizuku disconnected while spoofing";
                return false;
            }
            try {
                boolean ok = remote.publish(latitude, longitude, time);
                if (!ok) lastError = "Shizuku publish command failed";
                return ok;
            } catch (Throwable t) {
                service = null;
                lastError = "Shizuku publish failed: " + t.getClass().getSimpleName();
                return false;
            }
        }
        if (selected == Backend.ROOT) {
            long publishTime = time > 0 ? time : System.currentTimeMillis();
            String marker = String.format(Locale.US, "%d,%.7f,%.7f", publishTime, latitude, longitude);
            runRoot("setprop debug.geoavil.target " + marker);
            runRoot("setprop debug.geoavil.active 1");
            String value = String.format(Locale.US, "%.7f,%.7f", latitude, longitude);
            String command = "cmd location providers set-test-provider-location %s --location %s --time %d";
            boolean gps = runRoot(String.format(Locale.US, command, "gps", value, publishTime));
            boolean network = runRoot(String.format(Locale.US, command, "network", value, publishTime));
            if (!(gps && network)) lastError = "Root publish command failed";
            return gps && network;
        }
        lastError = "No privileged backend selected";
        return false;
    }

    public static synchronized void removeProviders() {
        Backend selected = backend;
        backend = Backend.NONE;
        if (selected == Backend.SHIZUKU) {
            IGeoAvilService remote = service != null ? service : awaitService();
            if (remote != null) try { remote.removeProviders(); } catch (Throwable ignored) { }
            return;
        }
        if (selected == Backend.ROOT) {
            removeRootProvider("gps");
            removeRootProvider("network");
            runRoot("setprop debug.geoavil.active 0");
            runRoot("setprop debug.geoavil.target ''");
        }
    }

    private static void removeRootProvider(String provider) {
        runRoot("cmd location providers set-test-provider-enabled " + provider + " false");
        runRoot("cmd location providers remove-test-provider " + provider);
    }

    public static String lastError() { return lastError; }

    public static int privilegedUid() {
        IGeoAvilService remote = service;
        if (remote == null) return -1;
        try { return remote.backendUid(); } catch (Throwable ignored) { return -1; }
    }

    public static String backendLabel() {
        Backend selected = backend;
        int uid = privilegedUid();
        if (selected == Backend.SHIZUKU && uid == 0) return "Shizuku/Sui root · live provider · GeoAvil-scoped system marker";
        if (selected == Backend.SHIZUKU && uid == 2000) return "Shizuku shell · live test-provider backend";
        if (selected == Backend.SHIZUKU) return "Shizuku UID " + uid;
        if (selected == Backend.ROOT) return "Direct su root · live test-provider backend";
        if (shizukuGranted()) return binding ? "Shizuku granted · UserService connecting" : "Shizuku granted · idle";
        return hasRoot() ? "Root available · idle" : "Standard mock-provider mode";
    }

    private static boolean runRoot(String command) {
        Process process = null;
        try {
            process = new ProcessBuilder("su", "-c", command).redirectErrorStream(true).start();
            if (!process.waitFor(4, TimeUnit.SECONDS)) {
                process.destroyForcibly();
                return false;
            }
            return process.exitValue() == 0;
        } catch (Throwable ignored) {
            return false;
        } finally {
            if (process != null) try { process.destroy(); } catch (Throwable ignored) { }
        }
    }
}
''')

write(APP / "src/main/java/com/github/fakegps/JoyStickManager.java", r'''package com.github.fakegps;

import android.content.Context;
import android.content.Intent;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.core.content.ContextCompat;

import com.github.fakegps.model.LocPoint;
import com.github.fakegps.ui.BookmarkActivity;
import com.github.fakegps.ui.FlyToActivity;
import com.github.fakegps.ui.JoyStickView;
import com.github.fakegps.ui.MainActivity;

import tiger.radio.loggerlibrary.Logger;

public class JoyStickManager implements IJoyStickPresenter {
    private static final String TAG = "JoyStickManager";
    public static double STEP_DEFAULT = 0.0000125;
    private static final String PREFS = "geoavil_preferences";
    private static final String PREF_AUTO_SHOW = "auto_show_analog";
    private static final String PREF_MOVE_STEP = "move_step";

    private enum State { STOPPED, STARTING, RUNNING }
    private static final JoyStickManager INSTANCE = new JoyStickManager();
    private final Handler mainHandler = new Handler(Looper.getMainLooper());

    private Context mContext;
    private LocationThread mLocationThread;
    private State state = State.STOPPED;
    private double mMoveStep = STEP_DEFAULT;
    private float mAnalogX;
    private float mAnalogY;
    private LocPoint mCurrentLocPoint;
    private LocPoint mFlyStartLocPoint;
    private LocPoint mTargetLocPoint;
    private long mFlyStartElapsedNanos;
    private long mFlyDurationNanos;
    private boolean mIsFlyMode;
    private JoyStickView mJoyStickView;

    private JoyStickManager() { }
    public static JoyStickManager get() { return INSTANCE; }

    public synchronized void init(Context context) {
        mContext = context.getApplicationContext();
        RootBridge.init(mContext);
        float saved = mContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .getFloat(PREF_MOVE_STEP, (float) STEP_DEFAULT);
        if (saved > 0 && Float.isFinite(saved)) mMoveStep = saved;
    }

    public synchronized boolean isStarted() { return state == State.RUNNING; }
    public synchronized boolean isStarting() { return state == State.STARTING; }
    public synchronized boolean isActiveOrStarting() { return state != State.STOPPED; }

    public void start(@NonNull LocPoint locPoint) {
        synchronized (this) {
            if (state != State.STOPPED) return;
            if (!GeoMath.isValidCoordinate(locPoint.getLatitude(), locPoint.getLongitude())) return;
            mCurrentLocPoint = new LocPoint(locPoint);
            mAnalogX = 0f;
            mAnalogY = 0f;
            mIsFlyMode = false;
            state = State.STARTING;
            mLocationThread = new LocationThread(mContext, this);
            mLocationThread.startThread();
        }
    }

    void onBackendReady() {
        synchronized (this) {
            if (state != State.STARTING) return;
            state = State.RUNNING;
        }
        startForegroundService();
        if (isAutoShowEnabled()) showJoyStick();
    }

    void onBackendFailure(String reason) {
        synchronized (this) {
            state = State.STOPPED;
            mLocationThread = null;
            mAnalogX = 0f;
            mAnalogY = 0f;
            mIsFlyMode = false;
        }
        stopForegroundService();
        hideJoyStick();
        mainHandler.post(() -> Toast.makeText(mContext,
                "GeoAvil could not start: " + (reason == null ? "unknown backend error" : reason),
                Toast.LENGTH_LONG).show());
    }

    void onRuntimePublishFailure(String reason) {
        synchronized (this) {
            if (state == State.STOPPED) return;
            state = State.STOPPED;
            mLocationThread = null;
            mAnalogX = 0f;
            mAnalogY = 0f;
            mIsFlyMode = false;
        }
        stopForegroundService();
        hideJoyStick();
        mainHandler.post(() -> Toast.makeText(mContext,
                "GeoAvil stopped because location publishing failed: " + reason,
                Toast.LENGTH_LONG).show());
    }

    public void stop() {
        LocationThread thread;
        synchronized (this) {
            state = State.STOPPED;
            thread = mLocationThread;
            mLocationThread = null;
            mAnalogX = 0f;
            mAnalogY = 0f;
            mIsFlyMode = false;
        }
        if (thread != null) thread.stopThread();
        stopForegroundService();
        hideJoyStick();
    }

    public void onForegroundServiceDestroyed() {
        if (isActiveOrStarting()) stop();
    }

    private void startForegroundService() {
        try {
            ContextCompat.startForegroundService(mContext, new Intent(mContext, FakeLocationService.class));
        } catch (Throwable e) {
            Logger.e(TAG, "Failed to start foreground service", e);
            stop();
        }
    }

    private void stopForegroundService() {
        try { mContext.stopService(new Intent(mContext, FakeLocationService.class)); }
        catch (Throwable e) { Logger.e(TAG, "Failed to stop foreground service", e); }
    }

    public void showJoyStick() {
        mainHandler.post(() -> {
            try {
                if (!isStarted()) return;
                if (mJoyStickView == null) {
                    mJoyStickView = new JoyStickView(mContext);
                    mJoyStickView.setJoyStickPresenter(this);
                }
                if (!mJoyStickView.isShowing()) mJoyStickView.addToWindow();
            } catch (Throwable t) {
                Logger.e(TAG, "Failed to create/show analog controller", t);
                mJoyStickView = null;
            }
        });
    }

    public void hideJoyStick() {
        mainHandler.post(() -> {
            try {
                if (mJoyStickView != null && mJoyStickView.isShowing()) mJoyStickView.removeFromWindow();
            } catch (Throwable t) { Logger.e(TAG, "Failed to hide analog controller", t); }
        });
    }

    public void restoreJoyStick() { if (isStarted()) showJoyStick(); }

    public boolean isAutoShowEnabled() {
        return mContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getBoolean(PREF_AUTO_SHOW, true);
    }

    public void setAutoShowEnabled(boolean enabled) {
        mContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putBoolean(PREF_AUTO_SHOW, enabled).apply();
        if (!enabled) hideJoyStick();
    }

    public synchronized LocPoint getCurrentLocPoint() {
        return mCurrentLocPoint == null ? null : new LocPoint(mCurrentLocPoint);
    }

    synchronized LocPoint advanceForTick(double seconds, long elapsedRealtimeNanos) {
        if (mCurrentLocPoint == null) return null;
        if (state != State.RUNNING) return new LocPoint(mCurrentLocPoint);
        if (mIsFlyMode && mFlyStartLocPoint != null && mTargetLocPoint != null && mFlyDurationNanos > 0) {
            double factor = (double) (elapsedRealtimeNanos - mFlyStartElapsedNanos) / (double) mFlyDurationNanos;
            if (factor >= 1.0) {
                mCurrentLocPoint = new LocPoint(mTargetLocPoint);
                mIsFlyMode = false;
            } else {
                mCurrentLocPoint = GeoMath.interpolate(mFlyStartLocPoint, mTargetLocPoint, factor);
            }
        } else {
            mCurrentLocPoint = GeoMath.moveScreenRelative(mCurrentLocPoint, mAnalogX, mAnalogY, mMoveStep, seconds);
        }
        return new LocPoint(mCurrentLocPoint);
    }

    public synchronized void jumpToLocation(@NonNull LocPoint location) {
        if (!GeoMath.isValidCoordinate(location.getLatitude(), location.getLongitude())) return;
        mIsFlyMode = false;
        mCurrentLocPoint = new LocPoint(location);
    }

    public synchronized void flyToLocation(@NonNull LocPoint location, int flyTimeSeconds) {
        if (mCurrentLocPoint == null || flyTimeSeconds <= 0
                || !GeoMath.isValidCoordinate(location.getLatitude(), location.getLongitude())) return;
        mFlyStartLocPoint = new LocPoint(mCurrentLocPoint);
        mTargetLocPoint = new LocPoint(location);
        mFlyStartElapsedNanos = SystemClock.elapsedRealtimeNanos();
        mFlyDurationNanos = flyTimeSeconds * 1_000_000_000L;
        mIsFlyMode = true;
        mAnalogX = 0f;
        mAnalogY = 0f;
    }

    public synchronized boolean isFlyMode() { return mIsFlyMode; }
    public synchronized void stopFlyMode() { mIsFlyMode = false; }

    public synchronized void setMoveStep(double moveStep) {
        if (!GeoMath.isFinite(moveStep) || moveStep <= 0) return;
        mMoveStep = moveStep;
        mContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
                .putFloat(PREF_MOVE_STEP, (float) moveStep).apply();
    }
    public synchronized double getMoveStep() { return mMoveStep; }

    @Override
    public synchronized void onAnalogMove(float x, float y) {
        float nx = Math.max(-1f, Math.min(1f, x));
        float ny = Math.max(-1f, Math.min(1f, y));
        if (Math.hypot(nx, ny) < 0.02) { nx = 0f; ny = 0f; }
        if (nx != 0f || ny != 0f) mIsFlyMode = false;
        mAnalogX = nx;
        mAnalogY = ny;
    }

    @Override public void onSetLocationClick() { MainActivity.startPage(mContext); }
    @Override public void onFlyClick() {
        if (isFlyMode()) { stopFlyMode(); Toast.makeText(mContext, "Stop Fly", Toast.LENGTH_SHORT).show(); }
        else FlyToActivity.startPage(mContext);
    }
    @Override public void onBookmarkLocationClick() {
        LocPoint point = getCurrentLocPoint();
        if (point != null) BookmarkActivity.startPage(mContext, "Bookmark", point);
        else Toast.makeText(mContext, "Service is not started", Toast.LENGTH_SHORT).show();
    }
    @Override public void onCopyLocationClick() {
        LocPoint point = getCurrentLocPoint();
        if (point != null) FakeGpsUtils.copyToClipboard(mContext, point.toString());
    }

    @Override public void onArrowUpClick() { onAnalogNudge(0f, -1f); }
    @Override public void onArrowDownClick() { onAnalogNudge(0f, 1f); }
    @Override public void onArrowLeftClick() { onAnalogNudge(-1f, 0f); }
    @Override public void onArrowRightClick() { onAnalogNudge(1f, 0f); }

    private synchronized void onAnalogNudge(float x, float y) {
        if (mCurrentLocPoint != null) mCurrentLocPoint = GeoMath.moveScreenRelative(mCurrentLocPoint, x, y, mMoveStep, 1.0);
    }
}
''')

write(APP / "src/main/java/com/github/fakegps/LocationThread.java", r'''package com.github.fakegps;

import android.content.Context;
import android.location.Location;
import android.location.LocationManager;
import android.location.provider.ProviderProperties;
import android.os.Build;
import android.os.Handler;
import android.os.HandlerThread;
import android.os.SystemClock;

import com.github.fakegps.model.LocPoint;

import java.util.HashSet;
import java.util.Set;

import tiger.radio.loggerlibrary.Logger;

public class LocationThread extends HandlerThread {
    private static final String TAG = "LocationThread";
    private static final String[] PROVIDERS = {LocationManager.GPS_PROVIDER, LocationManager.NETWORK_PROVIDER};
    private static final long UPDATE_MS = 200L;

    private final Context context;
    private JoyStickManager manager;
    private final LocationManager locationManager;
    private Handler handler;
    private final Set<String> localProviders = new HashSet<>();
    private boolean privilegedBackend;
    private boolean stopping;
    private LocPoint lastPoint;
    private long lastElapsedNanos;
    private int consecutivePublishFailures;

    public LocationThread(Context context, JoyStickManager manager) {
        super("GeoAvilLocationThread");
        this.context = context.getApplicationContext();
        this.manager = manager;
        this.locationManager = (LocationManager) context.getSystemService(Context.LOCATION_SERVICE);
    }

    @Override public synchronized void start() {
        super.start();
        handler = new Handler(getLooper());
        handler.post(this::setupAndRun);
    }
    public void startThread() { start(); }

    public void stopThread() {
        stopping = true;
        Handler h = handler;
        if (h == null) { quitSafely(); return; }
        h.removeCallbacksAndMessages(null);
        h.post(() -> { cleanupProviders(); manager = null; quitSafely(); });
    }

    private void setupAndRun() {
        if (stopping || manager == null) return;
        privilegedBackend = RootBridge.setupProviders();
        if (!privilegedBackend) {
            if (RootBridge.privilegedBackendExpected()) {
                failStart(RootBridge.lastError());
                return;
            }
            if (!addLocalProviders()) {
                failStart("Android rejected mock-provider setup. Select GeoAvil as the mock location app, or start Shizuku/root.");
                return;
            }
        }
        lastElapsedNanos = SystemClock.elapsedRealtimeNanos();
        manager.onBackendReady();
        handler.post(updateLocation);
    }

    private void failStart(String reason) {
        cleanupProviders();
        JoyStickManager m = manager;
        manager = null;
        if (m != null) m.onBackendFailure(reason);
        quitSafely();
    }

    private boolean addLocalProviders() {
        if (locationManager == null) return false;
        for (String provider : PROVIDERS) {
            try {
                try { locationManager.removeTestProvider(provider); } catch (Throwable ignored) { }
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                    locationManager.addTestProvider(provider, false, false, false, false, false,
                            true, true, ProviderProperties.POWER_USAGE_LOW, ProviderProperties.ACCURACY_FINE);
                } else {
                    locationManager.addTestProvider(provider, false, false, false, false, false,
                            true, true, android.location.Criteria.POWER_LOW, android.location.Criteria.ACCURACY_FINE);
                }
                locationManager.setTestProviderEnabled(provider, true);
                localProviders.add(provider);
            } catch (Throwable t) {
                Logger.e(TAG, "Unable to add local test provider " + provider, t);
                removeLocalProviders();
                return false;
            }
        }
        return localProviders.size() == PROVIDERS.length;
    }

    private void removeLocalProviders() {
        if (locationManager == null) return;
        for (String provider : new HashSet<>(localProviders)) {
            try { locationManager.setTestProviderEnabled(provider, false); } catch (Throwable ignored) { }
            try { locationManager.removeTestProvider(provider); } catch (Throwable ignored) { }
            localProviders.remove(provider);
        }
    }

    private void cleanupProviders() {
        if (privilegedBackend) RootBridge.removeProviders();
        else removeLocalProviders();
        privilegedBackend = false;
    }

    private final Runnable updateLocation = new Runnable() {
        @Override public void run() {
            JoyStickManager m = manager;
            if (stopping || m == null) return;
            long nowElapsed = SystemClock.elapsedRealtimeNanos();
            double seconds = Math.max(0.001, Math.min(1.0, (nowElapsed - lastElapsedNanos) / 1_000_000_000.0));
            lastElapsedNanos = nowElapsed;
            LocPoint point = m.advanceForTick(seconds, nowElapsed);
            if (point == null || !GeoMath.isValidCoordinate(point.getLatitude(), point.getLongitude())) {
                runtimeFailure("Generated coordinates became invalid");
                return;
            }

            boolean ok = privilegedBackend ? publishPrivileged(point) : publishLocal(point, seconds, nowElapsed);
            if (!ok) {
                consecutivePublishFailures++;
                if (consecutivePublishFailures >= 3) {
                    runtimeFailure(privilegedBackend ? RootBridge.lastError() : "Android rejected provider updates");
                    return;
                }
            } else {
                consecutivePublishFailures = 0;
            }
            lastPoint = new LocPoint(point);
            handler.postDelayed(this, UPDATE_MS);
        }
    };

    private boolean publishPrivileged(LocPoint point) {
        return RootBridge.publish(point.getLatitude(), point.getLongitude(), System.currentTimeMillis());
    }

    private boolean publishLocal(LocPoint point, double seconds, long elapsedNanos) {
        double distance = lastPoint == null ? 0.0 : GeoMath.distanceMeters(lastPoint, point);
        float speed = (float) (distance / Math.max(0.001, seconds));
        float bearing = lastPoint == null ? 0f : GeoMath.bearingDegrees(lastPoint, point);
        boolean all = true;
        for (String provider : PROVIDERS) {
            if (!localProviders.contains(provider)) return false;
            try {
                Location location = new Location(provider);
                location.setLatitude(point.getLatitude());
                location.setLongitude(point.getLongitude());
                location.setAltitude(50.0);
                location.setAccuracy(1.0f);
                location.setTime(System.currentTimeMillis());
                location.setElapsedRealtimeNanos(elapsedNanos);
                location.setSpeed(speed);
                location.setBearing(bearing);
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    location.setBearingAccuracyDegrees(distance > 0.01 ? 1.0f : 180.0f);
                    location.setVerticalAccuracyMeters(1.0f);
                    location.setSpeedAccuracyMetersPerSecond(0.2f);
                }
                locationManager.setTestProviderLocation(provider, location);
            } catch (Throwable t) {
                Logger.e(TAG, "Failed to publish " + provider, t);
                all = false;
            }
        }
        return all;
    }

    private void runtimeFailure(String reason) {
        stopping = true;
        cleanupProviders();
        JoyStickManager m = manager;
        manager = null;
        if (m != null) m.onRuntimePublishFailure(reason == null ? "unknown error" : reason);
        quitSafely();
    }

    public Handler getHandler() { return handler; }
}
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

public class AnalogJoystickView extends View {
    public interface Listener { void onMove(float x, float y); void onRelease(); }
    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final PointF knob = new PointF();
    private Listener listener;
    private float radius;
    private float knobRadius;

    public AnalogJoystickView(Context context, AttributeSet attrs) {
        super(context, attrs);
        setFocusable(true);
        setClickable(true);
        paint.setStyle(Paint.Style.FILL);
    }
    public void setListener(Listener listener) { this.listener = listener; }
    @Override protected void onSizeChanged(int w, int h, int oldw, int oldh) {
        radius = Math.min(w, h) * 0.46f;
        knobRadius = radius * 0.32f;
        center();
    }
    private void center() { knob.set(getWidth() / 2f, getHeight() / 2f); }
    @Override protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        paint.setColor(MaterialColors.getColor(this, com.google.android.material.R.attr.colorSurfaceContainerHighest));
        canvas.drawCircle(getWidth()/2f, getHeight()/2f, radius, paint);
        paint.setColor(MaterialColors.getColor(this, com.google.android.material.R.attr.colorPrimary));
        canvas.drawCircle(knob.x, knob.y, knobRadius, paint);
    }
    @Override public boolean onTouchEvent(MotionEvent event) {
        int action = event.getActionMasked();
        if (action == MotionEvent.ACTION_UP || action == MotionEvent.ACTION_CANCEL) {
            center(); invalidate();
            if (listener != null) listener.onRelease();
            performClick();
            return true;
        }
        if (action == MotionEvent.ACTION_DOWN || action == MotionEvent.ACTION_MOVE) {
            float cx = getWidth()/2f, cy = getHeight()/2f;
            float dx = event.getX()-cx, dy = event.getY()-cy;
            float max = Math.max(1f, radius-knobRadius);
            float distance = (float)Math.hypot(dx, dy);
            if (distance > max && distance > 0f) { dx = dx/distance*max; dy = dy/distance*max; }
            knob.set(cx+dx, cy+dy); invalidate();
            float x = dx/max, y = dy/max;
            if (Math.hypot(x, y) < 0.06) { x=0f; y=0f; }
            if (listener != null) listener.onMove(x, y);
            return true;
        }
        return super.onTouchEvent(event);
    }
    @Override public boolean performClick() { super.performClick(); return true; }
}
''')

write(APP / "src/main/java/com/github/fakegps/ui/JoyStickView.java", r'''package com.github.fakegps.ui;

import android.content.Context;
import android.content.SharedPreferences;
import android.graphics.PixelFormat;
import android.os.Build;
import android.provider.Settings;
import android.view.Gravity;
import android.view.LayoutInflater;
import android.view.MotionEvent;
import android.view.View;
import android.view.WindowManager;
import android.widget.FrameLayout;
import android.widget.Toast;

import com.github.fakegps.IJoyStickPresenter;
import com.github.fakegps.JoyStickManager;
import com.github.fakegps.ScreenUtils;
import com.tencent.fakegps.R;

import tiger.radio.loggerlibrary.Logger;

public class JoyStickView extends FrameLayout {
    private static final String TAG = "JoyStickView";
    private static final String PREFS = "geoavil_preferences";
    private static final String PREF_X = "joystick_x";
    private static final String PREF_Y = "joystick_y";
    private final WindowManager windowManager;
    private final WindowManager.LayoutParams params;
    private final int viewWidth;
    private final int viewHeight;
    private float downRawX, downRawY;
    private int downWindowX, downWindowY;
    private boolean showing;
    private IJoyStickPresenter presenter;

    public JoyStickView(Context context) {
        super(context);
        windowManager = (WindowManager) context.getSystemService(Context.WINDOW_SERVICE);
        LayoutInflater.from(context).inflate(R.layout.joystick_layout, this);
        viewWidth = context.getResources().getDimensionPixelSize(R.dimen.joystick_width);
        viewHeight = context.getResources().getDimensionPixelSize(R.dimen.joystick_height);
        params = new WindowManager.LayoutParams();
        params.type = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                ? WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY : WindowManager.LayoutParams.TYPE_PHONE;
        params.format = PixelFormat.RGBA_8888;
        params.flags = WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL | WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE;
        params.gravity = Gravity.START | Gravity.TOP;
        params.width = viewWidth;
        params.height = viewHeight;

        findViewById(R.id.btn_set_loc).setOnClickListener(clickListener);
        findViewById(R.id.btn_fly_to).setOnClickListener(clickListener);
        findViewById(R.id.btn_bookmark).setOnClickListener(clickListener);
        findViewById(R.id.btn_bookmark).setOnLongClickListener(v -> { if (presenter != null) presenter.onCopyLocationClick(); return true; });
        findViewById(R.id.btn_hide_joystick).setOnClickListener(v -> JoyStickManager.get().hideJoyStick());
        AnalogJoystickView analog = findViewById(R.id.analog_joystick);
        analog.setListener(new AnalogJoystickView.Listener() {
            @Override public void onMove(float x, float y) { if (presenter != null) presenter.onAnalogMove(x, y); }
            @Override public void onRelease() { if (presenter != null) presenter.onAnalogMove(0f, 0f); }
        });
    }

    public void setJoyStickPresenter(IJoyStickPresenter value) { presenter = value; }
    public boolean isShowing() { return showing; }

    public void addToWindow() {
        if (showing) return;
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M && !Settings.canDrawOverlays(getContext())) {
                Toast.makeText(getContext(), "Allow Display over other apps to show the analog controller", Toast.LENGTH_LONG).show();
                return;
            }
            if (windowManager == null) return;
            SharedPreferences prefs = getContext().getSharedPreferences(PREFS, Context.MODE_PRIVATE);
            int defaultX = Math.max(0, ScreenUtils.getScreenWidth(getContext()) - viewWidth - ScreenUtils.dip2px(getContext(), 12));
            int defaultY = Math.max(0, ScreenUtils.getScreenHeight(getContext()) - viewHeight - ScreenUtils.dip2px(getContext(), 48));
            params.x = prefs.getInt(PREF_X, defaultX);
            params.y = prefs.getInt(PREF_Y, defaultY);
            clamp();
            windowManager.addView(this, params);
            showing = true;
        } catch (Throwable t) {
            showing = false;
            Logger.e(TAG, "Unable to show analog overlay", t);
        }
    }

    public void removeFromWindow() {
        if (!showing) return;
        try { if (windowManager != null) windowManager.removeView(this); }
        catch (Throwable t) { Logger.e(TAG, "Unable to remove analog overlay", t); }
        finally { showing = false; }
    }

    private final View.OnClickListener clickListener = v -> {
        if (presenter == null) return;
        int id = v.getId();
        if (id == R.id.btn_set_loc) presenter.onSetLocationClick();
        else if (id == R.id.btn_fly_to) presenter.onFlyClick();
        else if (id == R.id.btn_bookmark) presenter.onBookmarkLocationClick();
    };

    @Override public boolean onTouchEvent(MotionEvent event) {
        switch (event.getActionMasked()) {
            case MotionEvent.ACTION_DOWN:
                downRawX = event.getRawX(); downRawY = event.getRawY();
                downWindowX = params.x; downWindowY = params.y;
                return true;
            case MotionEvent.ACTION_MOVE:
                params.x = downWindowX + Math.round(event.getRawX() - downRawX);
                params.y = downWindowY + Math.round(event.getRawY() - downRawY);
                clamp();
                updatePosition();
                return true;
            case MotionEvent.ACTION_UP:
            case MotionEvent.ACTION_CANCEL:
                savePosition();
                return true;
            default: return super.onTouchEvent(event);
        }
    }

    private void clamp() {
        int maxX = Math.max(0, ScreenUtils.getScreenWidth(getContext()) - viewWidth);
        int maxY = Math.max(0, ScreenUtils.getScreenHeight(getContext()) - viewHeight);
        params.x = Math.max(0, Math.min(maxX, params.x));
        params.y = Math.max(0, Math.min(maxY, params.y));
    }
    private void updatePosition() {
        try { if (showing && windowManager != null) windowManager.updateViewLayout(this, params); }
        catch (Throwable t) { Logger.e(TAG, "Unable to move analog overlay", t); }
    }
    private void savePosition() {
        getContext().getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
                .putInt(PREF_X, params.x).putInt(PREF_Y, params.y).apply();
    }
}
''')

write(APP / "src/main/java/com/github/fakegps/ScreenUtils.java", r'''package com.github.fakegps;

import android.content.Context;
import android.graphics.Rect;
import android.os.Build;
import android.util.DisplayMetrics;
import android.view.WindowManager;

public final class ScreenUtils {
    private ScreenUtils() { }
    public static int getStatusBarHeight(Context context) {
        int id = context.getResources().getIdentifier("status_bar_height", "dimen", "android");
        return id > 0 ? context.getResources().getDimensionPixelSize(id) : 0;
    }
    private static Rect bounds(Context context) {
        WindowManager wm = (WindowManager) context.getSystemService(Context.WINDOW_SERVICE);
        if (wm != null && Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) return wm.getCurrentWindowMetrics().getBounds();
        DisplayMetrics metrics = new DisplayMetrics();
        if (wm != null) wm.getDefaultDisplay().getRealMetrics(metrics);
        else metrics = context.getResources().getDisplayMetrics();
        return new Rect(0, 0, metrics.widthPixels, metrics.heightPixels);
    }
    public static int getScreenWidth(Context context) { return bounds(context).width(); }
    public static int getScreenHeight(Context context) { return bounds(context).height(); }
    public static int dip2px(Context context, float dp) { return Math.round(dp * context.getResources().getDisplayMetrics().density); }
    public static int px2dip(Context context, float px) { return Math.round(px / context.getResources().getDisplayMetrics().density); }
}
''')

write(APP / "src/main/java/com/github/fakegps/FakeLocationService.java", r'''package com.github.fakegps;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.os.Build;
import android.os.IBinder;

import com.github.fakegps.ui.MainActivity;
import com.tencent.fakegps.R;

public class FakeLocationService extends Service {
    private static final String CHANNEL_ID = "geoavil_location_channel";
    private static final int NOTIFICATION_ID = 1001;
    private boolean explicitlyStopped;

    @Override public void onCreate() { super.onCreate(); createNotificationChannel(); }
    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        explicitlyStopped = false;
        startForeground(NOTIFICATION_ID, buildNotification());
        return START_NOT_STICKY;
    }
    @Override public void onDestroy() {
        if (!explicitlyStopped && JoyStickManager.get().isActiveOrStarting()) {
            JoyStickManager.get().onForegroundServiceDestroyed();
        }
        super.onDestroy();
    }
    @Override public boolean stopService(Intent name) { explicitlyStopped = true; return super.stopService(name); }
    @Override public IBinder onBind(Intent intent) { return null; }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(CHANNEL_ID, "GeoAvil location service", NotificationManager.IMPORTANCE_LOW);
            channel.setDescription("Keeps GeoAvil spoofed location active");
            channel.setShowBadge(false);
            NotificationManager nm = getSystemService(NotificationManager.class);
            if (nm != null) nm.createNotificationChannel(channel);
        }
    }
    private Notification buildNotification() {
        Intent intent = new Intent(this, MainActivity.class).setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent pi = PendingIntent.getActivity(this, 0, intent, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        Notification.Builder builder = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                ? new Notification.Builder(this, CHANNEL_ID) : new Notification.Builder(this);
        return builder.setContentTitle("GeoAvil running")
                .setContentText("Spoofed location is active")
                .setSmallIcon(R.drawable.icon_app).setContentIntent(pi).setOngoing(true).build();
    }
}
''')

# Fix BookmarkAdapter's empty-list and refresh behavior.
write(APP / "src/main/java/com/github/fakegps/ui/BookmarkAdapter.java", r'''package com.github.fakegps.ui;

import android.content.Context;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.BaseAdapter;
import android.widget.TextView;

import com.github.fakegps.model.LocBookmark;
import com.tencent.fakegps.R;

import java.util.ArrayList;
import java.util.List;

public class BookmarkAdapter extends BaseAdapter {
    private final Context context;
    private final List<LocBookmark> items = new ArrayList<>();
    public BookmarkAdapter(Context context) { this.context = context; }
    @Override public int getCount() { return items.size(); }
    @Override public LocBookmark getItem(int position) { return items.get(position); }
    @Override public long getItemId(int position) { return getItem(position).getId(); }
    @Override public View getView(int position, View convertView, ViewGroup parent) {
        ViewHolder holder;
        if (convertView == null) {
            convertView = LayoutInflater.from(context).inflate(R.layout.list_item_bookmark_layout, parent, false);
            holder = new ViewHolder();
            holder.name = convertView.findViewById(R.id.tv_name);
            holder.loc = convertView.findViewById(R.id.tv_loc);
            convertView.setTag(holder);
        } else holder = (ViewHolder) convertView.getTag();
        LocBookmark item = getItem(position);
        holder.name.setText(item.getName());
        holder.loc.setText(item.getLocPoint() == null ? "" : item.getLocPoint().toString());
        return convertView;
    }
    public void setLocBookmarkList(List<LocBookmark> list) {
        items.clear();
        if (list != null) items.addAll(list);
        notifyDataSetChanged();
    }
    public void addBookmark(LocBookmark bookmark) { if (bookmark != null) { items.add(bookmark); notifyDataSetChanged(); } }
    public void clearAll() { items.clear(); notifyDataSetChanged(); }
    static class ViewHolder { TextView name; TextView loc; }
}
''')

# Keep bookmark editor open on validation/DB errors.
bookmark = APP / "src/main/java/com/github/fakegps/ui/BookmarkActivity.java"
bt = bookmark.read_text(encoding="utf-8")
bt = bt.replace('''        if (id == R.id.btn_ok) {\n            saveBookmark();\n            finish();\n''', '''        if (id == R.id.btn_ok) {\n            if (saveBookmark()) finish();\n''')
bt = bt.replace('''    private void saveBookmark() {''', '''    private boolean saveBookmark() {''')
bt = bt.replace('''            Toast.makeText(this, "name cannot be empty!", Toast.LENGTH_SHORT).show();\n            return;''', '''            Toast.makeText(this, "Name cannot be empty", Toast.LENGTH_SHORT).show();\n            return false;''')
bt = bt.replace('''                Toast.makeText(this, "bookmark saved!", Toast.LENGTH_SHORT).show();\n            } else {\n                Toast.makeText(this, "bookmark cannot save!", Toast.LENGTH_SHORT).show();\n            }\n        }\n    }''', '''                Toast.makeText(this, "Bookmark saved", Toast.LENGTH_SHORT).show();\n                return true;\n            } else {\n                Toast.makeText(this, "Bookmark could not be saved", Toast.LENGTH_SHORT).show();\n                return false;\n            }\n        }\n        Toast.makeText(this, "Enter a valid latitude and longitude", Toast.LENGTH_SHORT).show();\n        return false;\n    }''')
bookmark.write_text(bt, encoding="utf-8")

# MainActivity: overlay permission is required only if auto-show is enabled; start/stop
# understands STARTING; inputs are validated before launching the asynchronous backend.
main = APP / "src/main/java/com/github/fakegps/ui/MainActivity.java"
mt = main.read_text(encoding="utf-8")
mt = mt.replace('if (!JoyStickManager.get().isStarted()) {', 'if (!JoyStickManager.get().isActiveOrStarting()) {', 1)
regex_pattern = r'''    private void checkPermissionsAndStart\(\) \{.*?\n    \}\n\n    private void doStart\(\) \{.*?\n    \}'''
regex_replacement = r'''    private void checkPermissionsAndStart() {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION)
                != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(this,
                    new String[]{Manifest.permission.ACCESS_FINE_LOCATION}, REQUEST_CODE_LOCATION);
            return;
        }
        if (Build.VERSION.SDK_INT >= 33
                && ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS)
                != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(this,
                    new String[]{Manifest.permission.POST_NOTIFICATIONS}, REQUEST_CODE_NOTIFICATION);
            return;
        }
        if (JoyStickManager.get().isAutoShowEnabled()
                && Build.VERSION.SDK_INT >= Build.VERSION_CODES.M
                && !Settings.canDrawOverlays(this)) {
            new AlertDialog.Builder(this)
                    .setTitle("Display over other apps required")
                    .setMessage("GeoAvil only needs this permission when the floating analog controller is enabled. You can disable auto-show and spoof without the overlay.")
                    .setPositiveButton("Open permission", (dialog, which) -> openOverlaySettings(REQUEST_CODE_OVERLAY))
                    .setNegativeButton("Cancel", null)
                    .show();
            return;
        }
        doStart();
    }

    private void doStart() {
        if (mPendingStartPoint == null || !GeoMath.isValidCoordinate(
                mPendingStartPoint.getLatitude(), mPendingStartPoint.getLongitude())) {
            Toast.makeText(this, "Enter a valid latitude and longitude", Toast.LENGTH_SHORT).show();
            return;
        }
        if (!GeoMath.isFinite(mPendingStartStep) || mPendingStartStep <= 0) {
            Toast.makeText(this, "Movement step must be greater than zero", Toast.LENGTH_SHORT).show();
            return;
        }
        JoyStickManager.get().setMoveStep(mPendingStartStep);
        JoyStickManager.get().start(mPendingStartPoint);
        mPendingStartPoint = null;
        finish();
    }'''
mt, count = re.subn(regex_pattern, regex_replacement, mt, flags=re.S)
if count != 1:
    raise SystemExit(f"Unable to rewrite MainActivity permission/start flow: {count} matches")
mt = mt.replace('import com.github.fakegps.JoyStickManager;\n', 'import com.github.fakegps.JoyStickManager;\nimport com.github.fakegps.GeoMath;\n')
mt = mt.replace('''    private void updateBtnStart() {\n        if (JoyStickManager.get().isStarted()) {\n            mBtnStart.setText(R.string.btn_stop);\n        } else {\n            mBtnStart.setText(R.string.btn_start);\n        }\n    }''', '''    private void updateBtnStart() {\n        if (JoyStickManager.get().isStarting()) {\n            mBtnStart.setText("Starting…");\n        } else if (JoyStickManager.get().isStarted()) {\n            mBtnStart.setText(R.string.btn_stop);\n        } else {\n            mBtnStart.setText(R.string.btn_start);\n        }\n    }''')
main.write_text(mt, encoding="utf-8")

# Selective system-server sanitizer. Only locations matching GeoAvil's root-written
# marker within a narrow time window are modified; unrelated mock-location apps remain mock.
write(APP / "src/main/java/com/github/fakegps/xposed/GeoAvilSystemModule.java", r'''package com.github.fakegps.xposed;

import android.location.Location;
import android.util.Log;

import androidx.annotation.NonNull;

import java.lang.reflect.Method;

import io.github.libxposed.api.XposedModule;

public final class GeoAvilSystemModule extends XposedModule {
    private static final String TAG = "GeoAvilSystem";
    private static final String MOCK_PROVIDER = "com.android.server.location.provider.MockLocationProvider";
    private volatile boolean installed;

    @Override public void onModuleLoaded(@NonNull ModuleLoadedParam param) {
        log(Log.INFO, TAG, "GeoAvil module loaded in " + param.getProcessName());
    }

    @Override public void onPackageReady(@NonNull PackageReadyParam param) {
        if (installed) return;
        try {
            ClassLoader loader = param.getClassLoader();
            Class<?> providerBase = Class.forName("com.android.server.location.provider.AbstractLocationProvider", false, loader);
            Class<?> locationResult = Class.forName("android.location.LocationResult", false, loader);
            Method reportLocation = null;
            for (Method method : providerBase.getDeclaredMethods()) {
                if ("reportLocation".equals(method.getName()) && method.getParameterCount() == 1
                        && method.getParameterTypes()[0].getName().equals(locationResult.getName())) {
                    reportLocation = method; break;
                }
            }
            if (reportLocation == null) throw new NoSuchMethodException("reportLocation(LocationResult)");
            Method size = locationResult.getMethod("size");
            Method get = locationResult.getMethod("get", int.class);
            Method clearMock;
            try { clearMock = Location.class.getDeclaredMethod("setMock", boolean.class); }
            catch (NoSuchMethodException e) { clearMock = Location.class.getDeclaredMethod("setIsFromMockProvider", boolean.class); }
            clearMock.setAccessible(true);
            Method clearMockFinal = clearMock;

            Class<?> systemProperties = Class.forName("android.os.SystemProperties", false, loader);
            Method getProperty = systemProperties.getDeclaredMethod("get", String.class, String.class);
            getProperty.setAccessible(true);

            hook(reportLocation).setExceptionMode(ExceptionMode.PROTECTIVE).intercept(chain -> {
                Object provider = chain.getThisObject();
                if (provider != null && MOCK_PROVIDER.equals(provider.getClass().getName())) {
                    Object result = chain.getArg(0);
                    int count = ((Number) size.invoke(result)).intValue();
                    for (int i = 0; i < count; i++) {
                        Object item = get.invoke(result, i);
                        if (item instanceof Location && isGeoAvilLocation((Location)item, getProperty)) {
                            clearMockFinal.invoke(item, false);
                        }
                    }
                }
                return chain.proceed();
            });
            installed = true;
            log(Log.INFO, TAG, "Installed GeoAvil-scoped mock sanitizer");
        } catch (Throwable t) {
            log(Log.ERROR, TAG, "Unable to install GeoAvil system hook", t);
        }
    }

    private static boolean isGeoAvilLocation(Location location, Method getProperty) {
        try {
            String active = (String) getProperty.invoke(null, "debug.geoavil.active", "0");
            if (!"1".equals(active)) return false;
            String target = (String) getProperty.invoke(null, "debug.geoavil.target", "");
            String[] parts = target.split(",");
            if (parts.length != 3) return false;
            long time = Long.parseLong(parts[0]);
            double lat = Double.parseDouble(parts[1]);
            double lon = Double.parseDouble(parts[2]);
            if (Math.abs(System.currentTimeMillis() - time) > 1800L) return false;
            return Math.abs(location.getLatitude() - lat) <= 0.000002
                    && Math.abs(location.getLongitude() - lon) <= 0.000002;
        } catch (Throwable ignored) {
            return false;
        }
    }
}
''')

# Layout width must include the 150dp stick plus card padding.
dimens = APP / "src/main/res/values/dimens.xml"
d = dimens.read_text(encoding="utf-8").replace('<dimen name="joystick_width">150dp</dimen>', '<dimen name="joystick_width">174dp</dimen>')
dimens.write_text(d, encoding="utf-8")

# Remove unused boot permission. GeoAvil deliberately does not auto-start a spoof session.
manifest = APP / "src/main/AndroidManifest.xml"
manifest_text = manifest.read_text(encoding="utf-8").replace('    <uses-permission android:name="android.permission.RECEIVE_BOOT_COMPLETED"/>\n', '')
manifest.write_text(manifest_text, encoding="utf-8")

# Release logging should not expose every spoofed coordinate through ORM debug mode.
app = APP / "src/main/java/com/github/fakegps/FakeGpsApp.java"
at = app.read_text(encoding="utf-8").replace('sLiteOrm.setDebugged(true);', 'sLiteOrm.setDebugged(false);')
app.write_text(at, encoding="utf-8")

# Documentation aligned with alpha6 behavior.
docs = APP / "src/main/res/layout/activity_documentation.xml"
if docs.exists():
    dt = docs.read_text(encoding="utf-8")
    dt = dt.replace('GeoAvil 0.3.0-alpha5', 'GeoAvil 0.3.0-alpha6')
    dt = dt.replace('Movement step controls how far one location tick moves. Smaller values give finer movement.',
                    'Movement step controls full-stick speed. Smaller values give finer movement. The analog is screen-relative: up is always north, right is east, down is south and left is west. Device rotation, compass, accelerometer and gyroscope do not alter that direction.')
    docs.write_text(dt, encoding="utf-8")

# Small regression tests for direction, geographic normalization and linear fly interpolation.
write(APP / "src/test/java/com/github/fakegps/GeoMathTest.java", r'''package com.github.fakegps;

import static org.junit.Assert.*;

import com.github.fakegps.model.LocPoint;
import org.junit.Test;

public class GeoMathTest {
    @Test public void joystickUpAlwaysMovesNorth() {
        LocPoint p = GeoMath.moveScreenRelative(new LocPoint(51.5, -0.1), 0f, -1f, 0.0000125, 1.0);
        assertTrue(p.getLatitude() > 51.5);
        assertEquals(-0.1, p.getLongitude(), 1e-8);
    }
    @Test public void joystickRightAlwaysMovesEast() {
        LocPoint p = GeoMath.moveScreenRelative(new LocPoint(51.5, -0.1), 1f, 0f, 0.0000125, 1.0);
        assertTrue(p.getLongitude() > -0.1);
        assertEquals(51.5, p.getLatitude(), 1e-8);
    }
    @Test public void longitudeWraps() { assertEquals(-179.0, GeoMath.wrapLongitude(181.0), 1e-9); }
    @Test public void invalidCoordinatesRejected() {
        assertFalse(GeoMath.isValidCoordinate(91, 0));
        assertFalse(GeoMath.isValidCoordinate(Double.NaN, 0));
    }
    @Test public void interpolationUsesFixedEndpoints() {
        LocPoint p = GeoMath.interpolate(new LocPoint(0, 0), new LocPoint(10, 20), 0.5);
        assertEquals(5, p.getLatitude(), 1e-9);
        assertEquals(10, p.getLongitude(), 1e-9);
    }
}
''')

print("GeoAvil 0.3.0-alpha6 canonical runtime finalizer applied")
