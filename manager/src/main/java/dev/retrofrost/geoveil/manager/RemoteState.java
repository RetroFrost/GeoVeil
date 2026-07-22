package dev.retrofrost.geoveil.manager;

import android.content.SharedPreferences;

import io.github.libxposed.service.XposedService;

/** Keys shared between the manager and every LSPosed-injected GeoVeil process. */
public final class RemoteState {
    public static final String GROUP = "geoveil";
    public static final String ENABLED = "enabled";
    public static final String HAS_COORDINATES = "has_coordinates";
    public static final String LATITUDE = "latitude";
    public static final String LONGITUDE = "longitude";
    public static final String AUTOMATIC_ALTITUDE = "automatic_altitude";
    public static final String ALTITUDE = "altitude";
    public static final String SPEED = "speed";
    public static final String BEARING = "bearing";
    public static final String ACCURACY = "accuracy";
    public static final String JOYSTICK = "joystick";
    public static final String MOVEMENT_MODE = "movement_mode";
    public static final String GENERATION = "generation";

    private RemoteState() {}

    static SharedPreferences preferences() {
        XposedService service = GeoVeilApplication.service();
        return service == null ? null : service.getRemotePreferences(GROUP);
    }

    static void write(GeoState state, long generation) {
        SharedPreferences prefs = preferences();
        if (prefs == null) throw new IllegalStateException(
                "LSPosed has not connected to GeoVeil yet. Enable GeoVeil in LSPosed first.");
        if (!prefs.edit()
                .putBoolean(ENABLED, state.enabled)
                .putBoolean(HAS_COORDINATES, state.hasCoordinates)
                .putLong(LATITUDE, Double.doubleToRawLongBits(state.latitude))
                .putLong(LONGITUDE, Double.doubleToRawLongBits(state.longitude))
                .putBoolean(AUTOMATIC_ALTITUDE, state.automaticAltitude)
                .putLong(ALTITUDE, Double.doubleToRawLongBits(state.altitude))
                .putFloat(SPEED, state.speed)
                .putFloat(BEARING, state.bearing)
                .putFloat(ACCURACY, state.accuracy)
                .putBoolean(JOYSTICK, state.joystickEnabled)
                .putInt(MOVEMENT_MODE, state.movementMode)
                .putLong(GENERATION, generation)
                .commit()) {
            throw new IllegalStateException("LSPosed did not accept the GeoVeil state update.");
        }
    }
}
