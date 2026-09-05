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

# Process.destroyForcibly() is API 26; the app supports API 24. A normal destroy is
# sufficient after the bounded wait and preserves the declared minSdk.
for rel in [
    "src/main/java/com/github/fakegps/ShizukuLocationService.java",
    "src/main/java/com/github/fakegps/RootBridge.java",
]:
    p = APP / rel
    t = p.read_text(encoding="utf-8").replace("process.destroyForcibly();", "process.destroy();")
    p.write_text(t, encoding="utf-8")

# Cross-thread stop flag is written by the UI thread and read by HandlerThread.
loc_thread = APP / "src/main/java/com/github/fakegps/LocationThread.java"
lt = loc_thread.read_text(encoding="utf-8")
lt = lt.replace("    private boolean stopping;", "    private volatile boolean stopping;")
lt = lt.replace("    private final Context context;\n", "")
lt = lt.replace("        this.context = context.getApplicationContext();\n", "")
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

print("GeoAvil alpha6 strict-quality fixes applied")
