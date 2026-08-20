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
        raise SystemExit(f"Expected text not found in {path}: {old!r}")
    path.write_text(text.replace(old, new), encoding="utf-8")


# Shizuku 13.1.5 declares API 24 as its supported floor.
build = APP / "build.gradle"
text = build.read_text(encoding="utf-8")
text = text.replace("        minSdk 23\n", "        minSdk 24\n")

# Modern libxposed API is compile-only: LSPosed supplies it inside system_server.
if "io.github.libxposed:api" not in text:
    text = text.replace(
        "    implementation 'dev.rikka.shizuku:provider:13.1.5'\n",
        "    implementation 'dev.rikka.shizuku:provider:13.1.5'\n"
        "    compileOnly 'io.github.libxposed:api:102.0.0'\n"
    )
build.write_text(text, encoding="utf-8")

# Keep root and rootless location updates on Android's live test-provider path.
# On rooted devices the bundled LSPosed module clears the mock bit in system_server
# immediately before LocationResult is dispatched. This avoids the broken alternative
# of ILocationManager.injectLocation(), which only seeds an empty last-location cache.
write(APP / "src/main/java/com/github/fakegps/ShizukuLocationService.java", r'''package com.github.fakegps;

import android.content.Context;
import android.system.Os;

import androidx.annotation.Keep;

import java.util.Locale;
import java.util.concurrent.TimeUnit;

/** Privileged location command service hosted by Shizuku/Sui. */
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
        // remove is intentionally best-effort so stale providers from a previous crash
        // cannot make add-test-provider fail.
        run("cmd location providers remove-test-provider gps");
        run("cmd location providers remove-test-provider network");
        run("cmd location providers add-test-provider gps");
        run("cmd location providers add-test-provider network");
        boolean gps = run("cmd location providers set-test-provider-enabled gps true");
        boolean network = run("cmd location providers set-test-provider-enabled network true");
        return gps && network;
    }

    @Override
    public boolean publish(double latitude, double longitude, long time) {
        String value = String.format(Locale.US, "%f,%f", latitude, longitude);
        String command = "cmd location providers set-test-provider-location %s --location %s --time %d";
        return run(String.format(Locale.US, command, "gps", value, time))
                && run(String.format(Locale.US, command, "network", value, time));
    }

    @Override
    public void removeProviders() {
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

# Correct the status label created by the base modernization layer.
root_bridge = APP / "src/main/java/com/github/fakegps/RootBridge.java"
rb = root_bridge.read_text(encoding="utf-8")
rb = rb.replace(
    'if (uid == 0) return "Shizuku/Sui root · direct LocationManager injection";',
    'if (uid == 0) return "Shizuku/Sui root · live provider · system hook can clear isMock";'
)
root_bridge.write_text(rb, encoding="utf-8")

# Modern LSPosed system-server module. Scope is deliberately only `system`.
# We intercept AbstractLocationProvider.reportLocation while the concrete provider is
# MockLocationProvider. Android has already marked the Location mock at that point, but
# has not yet handed LocationResult to LocationProviderManager/listeners, so clearing the
# bit here preserves continuous provider updates while consumers receive isMock=false.
write(APP / "src/main/java/com/github/fakegps/xposed/GeoAvilSystemModule.java", r'''package com.github.fakegps.xposed;

import android.location.Location;
import android.util.Log;

import androidx.annotation.NonNull;

import java.lang.reflect.Method;

import io.github.libxposed.api.XposedModule;

public final class GeoAvilSystemModule extends XposedModule {
    private static final String TAG = "GeoAvilSystem";
    private static final String MOCK_PROVIDER =
            "com.android.server.location.provider.MockLocationProvider";

    @Override
    public void onModuleLoaded(@NonNull ModuleLoadedParam param) {
        log(Log.INFO, TAG, "GeoAvil system-server module loaded in " + param.getProcessName());
    }

    @Override
    public void onPackageReady(@NonNull PackageReadyParam param) {
        try {
            final ClassLoader loader = param.getClassLoader();
            final Class<?> providerBase = Class.forName(
                    "com.android.server.location.provider.AbstractLocationProvider", false, loader);
            final Class<?> locationResult = Class.forName(
                    "android.location.LocationResult", false, loader);
            final Method reportLocation = providerBase.getDeclaredMethod(
                    "reportLocation", locationResult);
            final Method size = locationResult.getDeclaredMethod("size");
            final Method get = locationResult.getDeclaredMethod("get", int.class);

            Method clearMock;
            try {
                clearMock = Location.class.getDeclaredMethod("setMock", boolean.class);
            } catch (NoSuchMethodException ignored) {
                clearMock = Location.class.getDeclaredMethod(
                        "setIsFromMockProvider", boolean.class);
            }
            clearMock.setAccessible(true);
            final Method clearMockMethod = clearMock;

            hook(reportLocation)
                    .setExceptionMode(ExceptionMode.PROTECTIVE)
                    .intercept(chain -> {
                        Object provider = chain.getThisObject();
                        if (provider != null && MOCK_PROVIDER.equals(provider.getClass().getName())) {
                            Object result = chain.getArg(0);
                            int count = ((Number) size.invoke(result)).intValue();
                            for (int i = 0; i < count; i++) {
                                Object location = get.invoke(result, i);
                                if (location instanceof Location) {
                                    clearMockMethod.invoke(location, false);
                                }
                            }
                        }
                        return chain.proceed();
                    });

            log(Log.INFO, TAG, "Hooked MockLocationProvider before listener dispatch");
        } catch (Throwable t) {
            log(Log.ERROR, TAG, "Unable to install GeoAvil system-server hook", t);
        }
    }
}
''')

write(APP / "src/main/resources/META-INF/xposed/java_init.list",
      "com.github.fakegps.xposed.GeoAvilSystemModule\n")
write(APP / "src/main/resources/META-INF/xposed/scope.list", "system\n")
write(APP / "src/main/resources/META-INF/xposed/module.prop", r'''minApiVersion=101
targetApiVersion=102
staticScope=true
exceptionMode=protective
autoHotReload=false
''')

print("GeoAvil root system-server sanitizer added")
