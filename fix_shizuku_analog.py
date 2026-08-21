#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "geoavil")
APP = ROOT / "app"


def write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# Hotfix release identity.
build = APP / "build.gradle"
text = build.read_text(encoding="utf-8")
text = text.replace('versionCode 30001', 'versionCode 30002')
text = text.replace('versionName "0.3.0-alpha1"', 'versionName "0.3.0-alpha2"')
build.write_text(text, encoding="utf-8")

# Make the Shizuku backend deterministic at start-up. LocationThread starts almost
# immediately after the user taps Start, while UserService binding is asynchronous.
# alpha1 could observe service == null during that race and unexpectedly fall through.
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

/** Shizuku/Sui privileged location backend with a bounded UserService bind wait. */
public final class RootBridge {
    private static final int SHIZUKU_PERMISSION = 0x4703;
    private static final int SERVICE_VERSION = 30002;
    private static final long BIND_WAIT_MS = 3500L;

    private static volatile Context appContext;
    private static volatile IGeoAvilService service;
    private static volatile boolean binding;
    private static volatile boolean listenersAdded;
    private static volatile CountDownLatch bindLatch = new CountDownLatch(0);

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
            CountDownLatch latch = bindLatch;
            while (latch.getCount() > 0) latch.countDown();
        });

        Shizuku.addRequestPermissionResultListener((requestCode, grantResult) -> {
            if (requestCode == SHIZUKU_PERMISSION && grantResult == PackageManager.PERMISSION_GRANTED) {
                bindUserService();
            }
        });
    }

    private static boolean shizukuGranted() {
        try {
            return Shizuku.pingBinder()
                    && Shizuku.checkSelfPermission() == PackageManager.PERMISSION_GRANTED;
        } catch (Throwable ignored) {
            return false;
        }
    }

    private static synchronized void bindUserService() {
        if (appContext == null || service != null || binding || !shizukuGranted()) return;
        try {
            ComponentName component = new ComponentName(appContext.getPackageName(),
                    ShizukuLocationService.class.getName());
            Shizuku.UserServiceArgs args = new Shizuku.UserServiceArgs(component)
                    .processNameSuffix("geoavil")
                    .daemon(false)
                    .tag("geoavil-location")
                    .version(SERVICE_VERSION);
            bindLatch = new CountDownLatch(1);
            binding = true;
            Shizuku.bindUserService(args, CONNECTION);
        } catch (Throwable ignored) {
            binding = false;
            CountDownLatch latch = bindLatch;
            while (latch.getCount() > 0) latch.countDown();
        }
    }

    private static final ServiceConnection CONNECTION = new ServiceConnection() {
        @Override
        public void onServiceConnected(ComponentName name, IBinder binder) {
            service = IGeoAvilService.Stub.asInterface(binder);
            binding = false;
            CountDownLatch latch = bindLatch;
            while (latch.getCount() > 0) latch.countDown();
        }

        @Override
        public void onServiceDisconnected(ComponentName name) {
            service = null;
            binding = false;
            CountDownLatch latch = bindLatch;
            while (latch.getCount() > 0) latch.countDown();
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

    public static boolean setupProviders() {
        IGeoAvilService remote = awaitService();
        if (remote != null) {
            try {
                return remote.setupProviders();
            } catch (Throwable ignored) {
                service = null;
                return false;
            }
        }

        // Root fallback is only used when Shizuku itself is unavailable. If Shizuku is
        // granted but the UserService failed, return false cleanly instead of racing su.
        if (shizukuGranted()) return false;
        runRoot("cmd location providers remove-test-provider gps");
        runRoot("cmd location providers remove-test-provider network");
        runRoot("cmd location providers add-test-provider gps");
        runRoot("cmd location providers add-test-provider network");
        boolean gps = runRoot("cmd location providers set-test-provider-enabled gps true");
        boolean network = runRoot("cmd location providers set-test-provider-enabled network true");
        return gps && network;
    }

    public static void removeProviders() {
        IGeoAvilService remote = service;
        if (remote != null) {
            try {
                remote.removeProviders();
                return;
            } catch (Throwable ignored) {
                service = null;
            }
        }
        if (!shizukuGranted()) {
            runRoot("cmd location providers set-test-provider-enabled gps false");
            runRoot("cmd location providers set-test-provider-enabled network false");
            runRoot("cmd location providers remove-test-provider gps");
            runRoot("cmd location providers remove-test-provider network");
        }
    }

    public static boolean publish(double latitude, double longitude, long time) {
        IGeoAvilService remote = service;
        if (remote == null && shizukuGranted()) remote = awaitService();
        if (remote != null) {
            try {
                return remote.publish(latitude, longitude, time);
            } catch (Throwable ignored) {
                service = null;
                return false;
            }
        }
        if (shizukuGranted()) return false;

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
        if (uid == 0) return "Shizuku/Sui root · live provider · system hook can clear isMock";
        if (uid == 2000) return "Shizuku shell · live test-provider backend";
        if (uid >= 0) return "Shizuku UID " + uid;
        if (shizukuGranted()) return "Shizuku granted · UserService connecting";
        return "Legacy/root fallback backend";
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

# The overlay itself must never be allowed to kill the process. alpha1 called addView()
# naked; a transient overlay permission/window-token problem therefore looked exactly
# like an app crash when Start/Restore Analog was pressed.
write(APP / "src/main/java/com/github/fakegps/ui/JoyStickView.java", r'''package com.github.fakegps.ui;

import android.content.Context;
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

/** Crash-safe Material floating analog controller. */
public class JoyStickView extends FrameLayout {
    private static final String TAG = "JoyStickView";
    private static int sStatusBarHeight;

    private int mViewWidth;
    private int mViewHeight;
    private WindowManager mWindowManager;
    private WindowManager.LayoutParams mWindowLayoutParams;
    private float mXInScreen;
    private float mYInScreen;
    private float mXInView;
    private float mYInView;
    private boolean isShowing = false;
    private IJoyStickPresenter mJoyStickPresenter;

    public JoyStickView(Context context) {
        super(context);
        mWindowManager = (WindowManager) context.getSystemService(Context.WINDOW_SERVICE);
        LayoutInflater.from(context).inflate(R.layout.joystick_layout, this);

        sStatusBarHeight = ScreenUtils.getStatusBarHeight(context);
        mViewWidth = context.getResources().getDimensionPixelSize(R.dimen.joystick_width);
        mViewHeight = context.getResources().getDimensionPixelSize(R.dimen.joystick_height);

        mWindowLayoutParams = new WindowManager.LayoutParams();
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            mWindowLayoutParams.type = WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY;
        } else {
            mWindowLayoutParams.type = WindowManager.LayoutParams.TYPE_PHONE;
        }
        mWindowLayoutParams.format = PixelFormat.RGBA_8888;
        mWindowLayoutParams.flags = WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL
                | WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE;
        mWindowLayoutParams.gravity = Gravity.LEFT | Gravity.TOP;
        mWindowLayoutParams.width = mViewWidth;
        mWindowLayoutParams.height = mViewHeight;
        mWindowLayoutParams.x = Math.max(0, ScreenUtils.getScreenWidth(context) - mViewWidth - 16);
        mWindowLayoutParams.y = Math.max(0, ScreenUtils.getScreenHeight(context) - mViewHeight - 220);

        findViewById(R.id.btn_set_loc).setOnClickListener(mOnClickListener);
        findViewById(R.id.btn_fly_to).setOnClickListener(mOnClickListener);
        findViewById(R.id.btn_bookmark).setOnClickListener(mOnClickListener);
        findViewById(R.id.btn_bookmark).setOnLongClickListener(v -> {
            if (mJoyStickPresenter != null) mJoyStickPresenter.onCopyLocationClick();
            return true;
        });

        findViewById(R.id.btn_hide_joystick).setOnClickListener(v ->
                JoyStickManager.get().hideJoyStick());

        AnalogJoystickView analogJoystick = findViewById(R.id.analog_joystick);
        analogJoystick.setListener(new AnalogJoystickView.Listener() {
            @Override
            public void onMove(float x, float y) {
                if (mJoyStickPresenter != null) mJoyStickPresenter.onAnalogMove(x, y);
            }

            @Override
            public void onRelease() {
                if (mJoyStickPresenter != null) mJoyStickPresenter.onAnalogMove(0f, 0f);
            }
        });
    }

    public boolean addToWindowSafely() {
        if (isShowing) return true;
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M
                    && !Settings.canDrawOverlays(getContext())) {
                Toast.makeText(getContext(), "Allow Display over other apps to show the analog controller", Toast.LENGTH_LONG).show();
                return false;
            }
            if (mWindowManager == null) return false;
            mWindowManager.addView(this, mWindowLayoutParams);
            isShowing = true;
            return true;
        } catch (Throwable t) {
            Logger.e(TAG, "Unable to show analog overlay", t);
            isShowing = false;
            Toast.makeText(getContext(), "Could not show analog controller. Check overlay permission.", Toast.LENGTH_LONG).show();
            return false;
        }
    }

    public void addToWindow() {
        addToWindowSafely();
    }

    public void removeFromWindow() {
        if (!isShowing) return;
        try {
            if (mWindowManager != null) mWindowManager.removeView(this);
        } catch (Throwable t) {
            Logger.e(TAG, "Unable to remove analog overlay", t);
        } finally {
            isShowing = false;
        }
    }

    public boolean isShowing() {
        return isShowing;
    }

    private final View.OnClickListener mOnClickListener = v -> {
        int id = v.getId();
        if (id == R.id.btn_set_loc) {
            if (mJoyStickPresenter != null) mJoyStickPresenter.onSetLocationClick();
        } else if (id == R.id.btn_fly_to) {
            if (mJoyStickPresenter != null) mJoyStickPresenter.onFlyClick();
        } else if (id == R.id.btn_bookmark) {
            if (mJoyStickPresenter != null) mJoyStickPresenter.onBookmarkLocationClick();
        }
    };

    public void setJoyStickPresenter(IJoyStickPresenter joyStickPresenter) {
        mJoyStickPresenter = joyStickPresenter;
    }

    @Override
    public boolean onTouchEvent(MotionEvent event) {
        switch (event.getAction()) {
            case MotionEvent.ACTION_DOWN:
                mXInView = event.getX();
                mYInView = event.getY();
                break;
            case MotionEvent.ACTION_MOVE:
                mXInScreen = event.getRawX();
                mYInScreen = event.getRawY() - sStatusBarHeight;
                updateViewPosition();
                break;
            default:
                break;
        }
        return true;
    }

    private void updateViewPosition() {
        if (!isShowing || mWindowManager == null) return;
        mWindowLayoutParams.x = (int) (mXInScreen - mXInView);
        mWindowLayoutParams.y = (int) (mYInScreen - mYInView);
        try {
            mWindowManager.updateViewLayout(this, mWindowLayoutParams);
        } catch (Throwable t) {
            Logger.e(TAG, "Unable to move analog overlay", t);
            isShowing = false;
        }
    }
}
''')

# Ensure every overlay operation is marshalled to the UI thread. This also prevents a
# future Restore Analog call from a service/broadcast thread from touching WindowManager.
manager = APP / "src/main/java/com/github/fakegps/JoyStickManager.java"
m = manager.read_text(encoding="utf-8")
if 'import android.os.Handler;' not in m:
    m = m.replace('import android.os.Build;\n', 'import android.os.Build;\nimport android.os.Handler;\nimport android.os.Looper;\n')
old_show = '''    public void showJoyStick() {
        if (mJoyStickView == null) {
            mJoyStickView = new JoyStickView(mContext);
            mJoyStickView.setJoyStickPresenter(this);
        }

        if (!mJoyStickView.isShowing()) {
            mJoyStickView.addToWindow();
        }
    }

    public void hideJoyStick() {
        if (mJoyStickView != null && mJoyStickView.isShowing()) {
            mJoyStickView.removeFromWindow();
        }
    }
'''
new_show = '''    public void showJoyStick() {
        Runnable action = () -> {
            try {
                if (mJoyStickView == null) {
                    mJoyStickView = new JoyStickView(mContext);
                    mJoyStickView.setJoyStickPresenter(this);
                }
                if (!mJoyStickView.isShowing()) {
                    mJoyStickView.addToWindowSafely();
                }
            } catch (Throwable t) {
                Logger.e(TAG, "Failed to create/show analog controller", t);
            }
        };
        if (Looper.myLooper() == Looper.getMainLooper()) action.run();
        else new Handler(Looper.getMainLooper()).post(action);
    }

    public void hideJoyStick() {
        Runnable action = () -> {
            try {
                if (mJoyStickView != null && mJoyStickView.isShowing()) {
                    mJoyStickView.removeFromWindow();
                }
            } catch (Throwable t) {
                Logger.e(TAG, "Failed to hide analog controller", t);
            }
        };
        if (Looper.myLooper() == Looper.getMainLooper()) action.run();
        else new Handler(Looper.getMainLooper()).post(action);
    }
'''
if old_show not in m:
    raise SystemExit('JoyStickManager show/hide block not found')
m = m.replace(old_show, new_show)
manager.write_text(m, encoding="utf-8")

# Never let a null location escape into the publisher loop while the backend is binding.
thread = APP / "src/main/java/com/github/fakegps/LocationThread.java"
t = thread.read_text(encoding="utf-8")
needle = '            LocPoint locPoint = mJoyStickManager.getUpdateLocPoint();\n            Logger.d(TAG, "UpdateLocation, " + locPoint);\n'
replacement = '            LocPoint locPoint = mJoyStickManager.getUpdateLocPoint();\n            if (locPoint == null) return;\n            Logger.d(TAG, "UpdateLocation, " + locPoint);\n'
if needle in t:
    t = t.replace(needle, replacement)
thread.write_text(t, encoding="utf-8")

print('GeoAvil 0.3.0-alpha2 Shizuku/analog startup hotfix applied')
