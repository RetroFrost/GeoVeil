package dev.retrofrost.geoveil.manager;

import android.content.Context;
import android.content.SharedPreferences;

/** Stores only the manager draft. The native bridge remains the authority for active engine state. */
final class DraftStore {
    private static final String PREFS = "geoveil_manager_draft_v2";

    private DraftStore() {}

    static GeoState load(Context context) {
        SharedPreferences preferences = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        GeoState state = new GeoState();
        state.enabled = preferences.getBoolean("enabled", false);
        state.hasCoordinates = preferences.getBoolean("has_coordinates", false);
        state.latitude = Double.longBitsToDouble(preferences.getLong("latitude", 0L));
        state.longitude = Double.longBitsToDouble(preferences.getLong("longitude", 0L));
        state.automaticAltitude = preferences.getBoolean("automatic_altitude", true);
        state.altitude = Double.longBitsToDouble(preferences.getLong("altitude", 0L));
        state.speed = Float.intBitsToFloat(preferences.getInt("speed", Float.floatToRawIntBits(0.0f)));
        state.bearing = Float.intBitsToFloat(preferences.getInt("bearing", Float.floatToRawIntBits(0.0f)));
        state.accuracy = Float.intBitsToFloat(preferences.getInt("accuracy", Float.floatToRawIntBits(5.0f)));
        state.easyLocationSwitch = preferences.getBoolean("easy_switch", false);
        state.joystickEnabled = preferences.getBoolean("joystick_enabled", false);
        state.movementMode = preferences.getInt("movement_mode", NativeBridge.MOVEMENT_WALKING);
        if (state.movementMode != NativeBridge.MOVEMENT_WALKING
                && state.movementMode != NativeBridge.MOVEMENT_JOGGING) {
            state.movementMode = NativeBridge.MOVEMENT_WALKING;
        }
        return state;
    }

    static void save(Context context, GeoState state) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .edit()
                .putBoolean("enabled", state.enabled)
                .putBoolean("has_coordinates", state.hasCoordinates)
                .putLong("latitude", Double.doubleToRawLongBits(state.latitude))
                .putLong("longitude", Double.doubleToRawLongBits(state.longitude))
                .putBoolean("automatic_altitude", state.automaticAltitude)
                .putLong("altitude", Double.doubleToRawLongBits(state.altitude))
                .putInt("speed", Float.floatToRawIntBits(state.speed))
                .putInt("bearing", Float.floatToRawIntBits(state.bearing))
                .putInt("accuracy", Float.floatToRawIntBits(state.accuracy))
                .putBoolean("easy_switch", state.easyLocationSwitch)
                .putBoolean("joystick_enabled", state.joystickEnabled)
                .putInt("movement_mode", state.movementMode)
                .apply();
    }

    static void clear(Context context) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().clear().apply();
    }
}
