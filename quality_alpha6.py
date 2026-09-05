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


# libxposed's hook(Method -> Executable) surface is only meaningful inside modern
# system_server/LSPosed. Avoid API-26 Java helpers in our own code and document the
# deliberate framework-only lint suppression at the narrowest scope.
xposed = APP / "src/main/java/com/github/fakegps/xposed/GeoAvilSystemModule.java"
xt = xposed.read_text(encoding="utf-8")
if "import android.annotation.SuppressLint;" not in xt:
    xt = xt.replace("package com.github.fakegps.xposed;\n\n", "package com.github.fakegps.xposed;\n\nimport android.annotation.SuppressLint;\n")
xt = xt.replace('method.getParameterCount() == 1', 'method.getParameterTypes().length == 1')
xt = xt.replace('    @Override public void onPackageReady(@NonNull PackageReadyParam param) {',
                '    @SuppressLint("NewApi")\n    @Override public void onPackageReady(@NonNull PackageReadyParam param) {')
xposed.write_text(xt, encoding="utf-8")

# Process.destroyForcibly() and Process.waitFor(timeout, unit) are API 26; GeoAvil's
# minSdk is 24. Use exitValue() polling against System.nanoTime() for a real bounded wait
# that works on every supported Android release.
for rel, marker in [
    ("src/main/java/com/github/fakegps/ShizukuLocationService.java", "    private static boolean run(String command) {\n"),
    ("src/main/java/com/github/fakegps/RootBridge.java", "    private static boolean runRoot(String command) {\n"),
]:
    p = APP / rel
    t = p.read_text(encoding="utf-8")
    t = t.replace("process.destroyForcibly();", "process.destroy();")
    t = t.replace("if (!process.waitFor(4, TimeUnit.SECONDS)) {", "if (!waitForProcess(process, 4000L)) {")
    if "private static boolean waitForProcess(Process process, long timeoutMs)" not in t:
        helper = '''    private static boolean waitForProcess(Process process, long timeoutMs) {
        long deadline = System.nanoTime() + timeoutMs * 1_000_000L;
        while (System.nanoTime() < deadline) {
            try {
                process.exitValue();
                return true;
            } catch (IllegalThreadStateException stillRunning) {
                try {
                    Thread.sleep(20L);
                } catch (InterruptedException interrupted) {
                    Thread.currentThread().interrupt();
                    return false;
                }
            }
        }
        return false;
    }

'''
        if marker not in t:
            raise SystemExit(f"Could not add API-24 process wait helper to {p}")
        t = t.replace(marker, helper + marker)
    p.write_text(t, encoding="utf-8")

# Cross-thread stop flag is written by the UI thread and read by HandlerThread.
# The pre-Android-12 branch intentionally uses the old Criteria integer contract; newer
# SDK annotations describe the ProviderProperties contract even for this overload, so
# suppress only that known lint mismatch on provider creation.
loc_thread = APP / "src/main/java/com/github/fakegps/LocationThread.java"
lt = loc_thread.read_text(encoding="utf-8")
if "import android.annotation.SuppressLint;" not in lt:
    lt = lt.replace("package com.github.fakegps;\n\n", "package com.github.fakegps;\n\nimport android.annotation.SuppressLint;\n")
lt = lt.replace("    private boolean stopping;", "    private volatile boolean stopping;")
lt = lt.replace("    private final Context context;\n", "")
lt = lt.replace("        this.context = context.getApplicationContext();\n", "")
lt = lt.replace("    private boolean addLocalProviders() {\n", "    @SuppressLint(\"WrongConstant\")\n    private boolean addLocalProviders() {\n")
loc_thread.write_text(lt, encoding="utf-8")

# A non-sticky service does not need to override stopService(). Manager.stop() changes
# its state before asking Android to stop the service, so onDestroy can safely distinguish
# external service death from an intentional shutdown without a redundant flag.
service = APP / "src/main/java/com/github/fakegps/FakeLocationService.java"
st = service.read_text(encoding="utf-8")
st = st.replace("    private boolean explicitlyStopped;\n", "")
st = st.replace("        explicitlyStopped = false;\n", "")
st = st.replace("        if (!explicitlyStopped && JoyStickManager.get().isActiveOrStarting()) {",
                "        if (JoyStickManager.get().isActiveOrStarting()) {")
st = st.replace("    @Override public boolean stopService(Intent name) { explicitlyStopped = true; return super.stopService(name); }\n", "")
service.write_text(st, encoding="utf-8")

# Do not run a 4-second `su` probe on the UI thread merely to render a diagnostic label.
bridge = APP / "src/main/java/com/github/fakegps/RootBridge.java"
br = bridge.read_text(encoding="utf-8")
br = br.replace('''        if (shizukuGranted()) return binding ? "Shizuku granted · UserService connecting" : "Shizuku granted · idle";
        return hasRoot() ? "Root available · idle" : "Standard mock-provider mode";''',
'''        if (shizukuGranted()) return binding ? "Shizuku granted · UserService connecting" : "Shizuku granted · idle";
        Boolean root = rootAvailable;
        if (Boolean.TRUE.equals(root)) return "Root available · idle";
        if (Boolean.FALSE.equals(root)) return "Standard mock-provider mode";
        return "No active privileged backend";''')
bridge.write_text(br, encoding="utf-8")

# Clamp a visible overlay again after configuration/display changes so rotating the app
# underneath the system overlay cannot strand the controller outside the new bounds.
joy = APP / "src/main/java/com/github/fakegps/ui/JoyStickView.java"
jt = joy.read_text(encoding="utf-8")
if "import android.content.res.Configuration;" not in jt:
    jt = jt.replace("import android.content.SharedPreferences;\n", "import android.content.SharedPreferences;\nimport android.content.res.Configuration;\n")
if "protected void onConfigurationChanged(Configuration newConfig)" not in jt:
    marker = "    private void clamp() {\n"
    insertion = '''    @Override
    protected void onConfigurationChanged(Configuration newConfig) {
        super.onConfigurationChanged(newConfig);
        post(() -> {
            clamp();
            updatePosition();
            savePosition();
        });
    }

'''
    if marker not in jt:
        raise SystemExit("Could not add JoyStickView configuration handling")
    jt = jt.replace(marker, insertion + marker)
# Accessibility services can invoke performClick directly; panel dragging itself has no
# click action, but forwarding it is still the correct custom-view contract.
if "public boolean performClick()" not in jt:
    marker = "    private void clamp() {\n"
    click = '''    @Override
    public boolean performClick() {
        super.performClick();
        return true;
    }

'''
    jt = jt.replace(marker, click + marker)
joy.write_text(jt, encoding="utf-8")

# Preserve an in-progress start request if Android recreates MainActivity while returning
# from runtime/special-access permission settings.
main = APP / "src/main/java/com/github/fakegps/ui/MainActivity.java"
mt = main.read_text(encoding="utf-8")
if 'STATE_PENDING_POINT' not in mt:
    mt = mt.replace('    private static final int REQUEST_CODE_NOTIFICATION = 2003;\n',
                    '    private static final int REQUEST_CODE_NOTIFICATION = 2003;\n'
                    '    private static final String STATE_PENDING_POINT = "pending_start_point";\n'
                    '    private static final String STATE_PENDING_STEP = "pending_start_step";\n')
    anchor = '        setContentView(R.layout.activity_main);\n'
    restore = '''        setContentView(R.layout.activity_main);

        if (savedInstanceState != null) {
            Object savedPoint = savedInstanceState.getSerializable(STATE_PENDING_POINT);
            if (savedPoint instanceof LocPoint) mPendingStartPoint = (LocPoint) savedPoint;
            mPendingStartStep = savedInstanceState.getDouble(STATE_PENDING_STEP, 0.0);
        }
'''
    if anchor not in mt:
        raise SystemExit("Could not add MainActivity pending state restore")
    mt = mt.replace(anchor, restore, 1)
    before_destroy = '    @Override\n    protected void onDestroy() {'
    save_method = '''    @Override
    protected void onSaveInstanceState(@NonNull Bundle outState) {
        super.onSaveInstanceState(outState);
        if (mPendingStartPoint != null) outState.putSerializable(STATE_PENDING_POINT, mPendingStartPoint);
        outState.putDouble(STATE_PENDING_STEP, mPendingStartStep);
    }

'''
    if before_destroy not in mt:
        raise SystemExit("Could not add MainActivity pending state save")
    mt = mt.replace(before_destroy, save_method + before_destroy)
main.write_text(mt, encoding="utf-8")

# Keep Fly UI consistent when an automatically completed flight is revisited.
fly = APP / "src/main/java/com/github/fakegps/ui/FlyToActivity.java"
ft = fly.read_text(encoding="utf-8")
if "protected void onResume()" not in ft:
    marker = "    private void updateBtn() {\n"
    resume = '''    @Override
    protected void onResume() {
        super.onResume();
        updateBtn();
    }

'''
    if marker not in ft:
        raise SystemExit("Could not add FlyToActivity onResume refresh")
    ft = ft.replace(marker, resume + marker)
fly.write_text(ft, encoding="utf-8")

# AppCompat menu namespace is required when AppCompat owns the action bar.
menu = APP / "src/main/res/menu/main_menu.xml"
menu.write_text('''<?xml version="1.0" encoding="utf-8"?>
<menu xmlns:android="http://schemas.android.com/apk/res/android"
      xmlns:app="http://schemas.android.com/apk/res-auto">
    <item
        android:id="@+id/menu_mock_status"
        android:title="Mock status tester"
        app:showAsAction="never" />
</menu>
''', encoding="utf-8")

# Legacy D-pad resource is no longer used by the analog UI, but the class still compiles
# as part of the source tree. Keep it correct for AppCompat and accessibility instead of
# suppressing or deleting a class that old layouts may still reference.
button = APP / "src/main/java/com/github/fakegps/ui/JoyStickButton.java"
button.write_text(r'''package com.github.fakegps.ui;

import android.content.Context;
import android.util.AttributeSet;
import android.view.MotionEvent;

import androidx.appcompat.widget.AppCompatImageButton;

import tiger.radio.loggerlibrary.Logger;

public class JoyStickButton extends AppCompatImageButton {
    private static final String TAG = "JoyStickButton";
    private boolean pressDown;

    public JoyStickButton(Context context) { super(context); }
    public JoyStickButton(Context context, AttributeSet attrs) { super(context, attrs); }

    @Override
    public boolean onTouchEvent(MotionEvent event) {
        switch (event.getActionMasked()) {
            case MotionEvent.ACTION_DOWN:
                pressDown = true;
                postDelayed(longPressRunnable, 1000L);
                break;
            case MotionEvent.ACTION_UP:
            case MotionEvent.ACTION_CANCEL:
                removeCallbacks(longPressRunnable);
                pressDown = false;
                break;
            default:
                break;
        }
        return super.onTouchEvent(event);
    }

    @Override
    public boolean performClick() {
        super.performClick();
        return true;
    }

    private final Runnable longPressRunnable = new Runnable() {
        @Override public void run() {
            if (pressDown) {
                Logger.d(TAG, "invoke click");
                performClick();
                postDelayed(this, 500L);
            }
        }
    };
}
''', encoding="utf-8")

print("GeoAvil alpha6 strict-quality fixes applied")
