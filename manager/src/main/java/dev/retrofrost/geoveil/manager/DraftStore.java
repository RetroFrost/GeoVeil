package dev.retrofrost.geoveil.manager;

import android.content.Context;
import android.content.SharedPreferences;

/** Stores only the manager draft. The native bridge remains the authority for active engine state. */
final class DraftStore {
    private static final String PREFS = "geoveil_manager_draft_v1";

    private DraftStore() {
    }

    static GeoState load(Context context) {
        SharedPreferences preferences = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        GeoState state = new GeoState();
        state.enabled = false;
        state.hasCoordinates = preferences.getBoolean("has_coordinates", false);
        state.latitude = Double.longBitsToDouble(preferences.getLong("latitude", 0L));
        state.longitude = Double.longBitsToDouble(preferences.getLong("longitude", 0L));
        state.automaticAltitude = preferences.getBoolean("automatic_altitude", true);
        state.altitude = Double.longBitsToDouble(preferences.getLong("altitude", 0L));
        state.speed = Float.intBitsToFloat(preferences.getInt("speed", Float.floatToRawIntBits(0.0f)));
        state.bearing = Float.intBitsToFloat(preferences.getInt("bearing", Float.floatToRawIntBits(0.0f)));
        state.accuracy = Float.intBitsToFloat(preferences.getInt("accuracy", Float.floatToRawIntBits(5.0f)));
        state.easyLocationSwitch = preferences.getBoolean("easy_switch", false);
        return state;
    }

    static void save(Context context, GeoState state) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .edit()
                .putBoolean("has_coordinates", state.hasCoordinates)
                .putLong("latitude", Double.doubleToRawLongBits(state.latitude))
                .putLong("longitude", Double.doubleToRawLongBits(state.longitude))
                .putBoolean("automatic_altitude", state.automaticAltitude)
                .putLong("altitude", Double.doubleToRawLongBits(state.altitude))
                .putInt("speed", Float.floatToRawIntBits(state.speed))
                .putInt("bearing", Float.floatToRawIntBits(state.bearing))
                .putInt("accuracy", Float.floatToRawIntBits(state.accuracy))
                .putBoolean("easy_switch", state.easyLocationSwitch)
                .apply();
    }

    static void clear(Context context) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().clear().apply();
    }
}
