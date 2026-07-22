package dev.retrofrost.geoveil.xposed;

import android.app.Activity;
import android.content.SharedPreferences;
import android.location.Location;
import android.util.Log;

import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Set;
import java.util.WeakHashMap;

import dev.retrofrost.geoveil.manager.RemoteState;
import io.github.libxposed.api.XposedInterface;
import io.github.libxposed.api.XposedModule;
import io.github.libxposed.api.XposedModuleInterface;

/**
 * LSPosed entry point. It operates only in packages selected in LSPosed; genuine
 * framework location remains untouched outside that scope.
 */
public final class GeoVeilModule extends XposedModule {
    private static final String TAG = "GeoVeil";
    private final Set<Method> installed = Collections.newSetFromMap(new WeakHashMap<>());
    private SharedPreferences prefs;

    @Override public void onModuleLoaded(ModuleLoadedParam param) {
        try {
            prefs = getRemotePreferences(RemoteState.GROUP);
            log(Log.INFO, TAG, "Remote preferences connected in " + param.getProcessName());
        } catch (Throwable t) {
            log(Log.ERROR, TAG, "Remote preferences unavailable", t);
        }
    }

    @Override public void onPackageReady(PackageReadyParam param) {
        try {
            installLocationGetters();
            installLocationManager();
            installActivityHook();
            log(Log.INFO, TAG, "Installed app hooks for " + param.getPackageName());
        } catch (Throwable t) {
            log(Log.ERROR, TAG, "Could not install hooks for " + param.getPackageName(), t);
        }
    }

    /**
     * The system-wide path. LSPosed must scope this module to System Framework
     * (package `android`) for this callback to run. The location is copied before
     * LocationProviderManager distributes it to any requesting application.
     */
    @Override public void onSystemServerStarting(SystemServerStartingParam param) {
        try {
            installSystemDelivery(param.getClassLoader());
            log(Log.INFO, TAG, "Installed system-wide LocationProviderManager delivery hook");
        } catch (Throwable t) {
            log(Log.ERROR, TAG, "System-wide delivery hook unavailable; app scopes still work", t);
        }
    }

    private void installLocationGetters() {
        for (Method method : Location.class.getDeclaredMethods()) {
            String n = method.getName();
            if (n.equals("getLatitude") || n.equals("getLongitude") || n.equals("getAltitude")
                    || n.equals("getSpeed") || n.equals("getBearing") || n.equals("getAccuracy")
                    || n.equals("hasAltitude") || n.equals("hasSpeed") || n.equals("hasBearing")
                    || n.equals("hasAccuracy")) {
                install(method, chain -> {
                    State state = state();
                    if (!state.active) return chain.proceed();
                    switch (chain.getExecutable().getName()) {
                        case "getLatitude": return state.latitude;
                        case "getLongitude": return state.longitude;
                        case "getAltitude": return state.automaticAltitude ? 0.0d : state.altitude;
                        case "getSpeed": return state.speed;
                        case "getBearing": return state.bearing;
                        case "getAccuracy": return state.accuracy;
                        default: return true;
                    }
                });
            }
        }
    }

    private void installLocationManager() {
        try {
            Class<?> manager = Class.forName("android.location.LocationManager");
            for (Method method : manager.getDeclaredMethods()) {
                if (!method.getName().equals("getLastKnownLocation")
                        || !Location.class.isAssignableFrom(method.getReturnType())) continue;
                install(method, chain -> {
                    Object result = chain.proceed();
                    State state = state();
                    if (!state.active || !(result instanceof Location)) return result;
                    Location copy = new Location((Location) result);
                    state.apply(copy);
                    return copy;
                });
            }
        } catch (Throwable t) {
            log(Log.WARN, TAG, "LocationManager hook unavailable", t);
        }
    }

    private void installActivityHook() {
        try {
            Method resume = Activity.class.getDeclaredMethod("onResume");
            install(resume, chain -> {
                Object result = chain.proceed();
                if (state().joystick) JoystickOverlay.install((Activity) chain.getThisObject(), prefs);
                return result;
            });
        } catch (Throwable t) {
            log(Log.WARN, TAG, "In-app joystick hook unavailable", t);
        }
    }

    private void installSystemDelivery(ClassLoader loader) throws Exception {
        Class<?> providerManager = Class.forName(
                "com.android.server.location.provider.LocationProviderManager", false, loader);
        Class<?> locationResult = Class.forName("android.location.LocationResult", false, loader);
        Method asList = locationResult.getDeclaredMethod("asList");
        Method wrap = locationResult.getDeclaredMethod("wrap", List.class);
        for (Method method : providerManager.getDeclaredMethods()) {
            if (!method.getName().equals("onReportLocation")) continue;
            boolean acceptsResult = false;
            for (Class<?> parameter : method.getParameterTypes()) {
                if (parameter == locationResult) { acceptsResult = true; break; }
            }
            if (!acceptsResult) continue;
            install(method, chain -> {
                State state = state();
                if (!state.active) return chain.proceed();
                Object[] args = chain.getArgs().toArray();
                for (int i = 0; i < args.length; i++) {
                    if (args[i] == null || !locationResult.isInstance(args[i])) continue;
                    @SuppressWarnings("unchecked")
                    List<Location> incoming = (List<Location>) asList.invoke(args[i]);
                    ArrayList<Location> replaced = new ArrayList<>(incoming.size());
                    for (Location original : incoming) {
                        Location copy = new Location(original);
                        state.apply(copy);
                        replaced.add(copy);
                    }
                    args[i] = wrap.invoke(null, replaced);
                }
                return chain.proceed(args);
            });
        }
    }

    private void install(Method method, XposedInterface.Hooker hooker) {
        if (installed.add(method)) hook(method).intercept(hooker);
    }

    private State state() {
        SharedPreferences p = prefs;
        if (p == null) return State.OFF;
        try {
            boolean active = p.getBoolean(RemoteState.ENABLED, false)
                    && p.getBoolean(RemoteState.HAS_COORDINATES, false);
            return new State(active,
                    Double.longBitsToDouble(p.getLong(RemoteState.LATITUDE, 0L)),
                    Double.longBitsToDouble(p.getLong(RemoteState.LONGITUDE, 0L)),
                    p.getBoolean(RemoteState.AUTOMATIC_ALTITUDE, true),
                    Double.longBitsToDouble(p.getLong(RemoteState.ALTITUDE, 0L)),
                    p.getFloat(RemoteState.SPEED, 0f), p.getFloat(RemoteState.BEARING, 0f),
                    p.getFloat(RemoteState.ACCURACY, 5f), p.getBoolean(RemoteState.JOYSTICK, false));
        } catch (Throwable ignored) {
            return State.OFF;
        }
    }

    private static final class State {
        static final State OFF = new State(false, 0, 0, true, 0, 0, 0, 5, false);
        final boolean active, automaticAltitude, joystick;
        final double latitude, longitude, altitude;
        final float speed, bearing, accuracy;
        State(boolean active, double latitude, double longitude, boolean automaticAltitude,
              double altitude, float speed, float bearing, float accuracy, boolean joystick) {
            this.active = active; this.latitude = latitude; this.longitude = longitude;
            this.automaticAltitude = automaticAltitude; this.altitude = altitude;
            this.speed = speed; this.bearing = bearing; this.accuracy = accuracy; this.joystick = joystick;
        }
        void apply(Location location) {
            location.setLatitude(latitude); location.setLongitude(longitude);
            if (automaticAltitude) location.removeAltitude(); else location.setAltitude(altitude);
            location.setSpeed(speed); location.setBearing(bearing); location.setAccuracy(accuracy);
        }
    }
}
