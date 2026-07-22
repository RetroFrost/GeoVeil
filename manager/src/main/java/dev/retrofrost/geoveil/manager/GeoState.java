package dev.retrofrost.geoveil.manager;

import java.util.Locale;

/** Versioned manager-side representation of the state shared through LSPosed. */
public final class GeoState {
    public static final int SCHEMA_VERSION = 2;

    public boolean enabled;
    public boolean hasCoordinates;
    public double latitude;
    public double longitude;
    public boolean automaticAltitude = true;
    public double altitude;
    public float speed;
    public float bearing;
    public float accuracy = 5.0f;
    public boolean easyLocationSwitch;
    public boolean joystickEnabled;
    public int movementMode = NativeBridge.MOVEMENT_NONE;
    public long generation = System.nanoTime();

    public Validation validate() {
        if (!hasCoordinates) {
            return enabled
                    ? Validation.error("Enter both latitude and longitude before enabling GeoVeil.")
                    : Validation.ok();
        }
        if (!Double.isFinite(latitude) || latitude < -90.0d || latitude > 90.0d) {
            return Validation.error("Latitude must be a finite value from -90 to 90.");
        }
        if (!Double.isFinite(longitude) || longitude < -180.0d || longitude > 180.0d) {
            return Validation.error("Longitude must be a finite value from -180 to 180.");
        }
        if (latitude == 0.0d && longitude == 0.0d) {
            return Validation.error("Android rejects a non-mock framework location at exactly 0, 0.");
        }
        if (!automaticAltitude && (!Double.isFinite(altitude) || altitude < -500.0d || altitude > 9000.0d)) {
            return Validation.error("Manual altitude must be from -500 to 9000 metres.");
        }
        if (!Float.isFinite(speed) || speed < 0.0f || speed > 150.0f) {
            return Validation.error("Speed must be from 0 to 150 m/s.");
        }
        if (!Float.isFinite(bearing) || bearing < 0.0f || bearing >= 360.0f) {
            return Validation.error("Bearing must be from 0 up to, but not including, 360 degrees.");
        }
        if (!Float.isFinite(accuracy) || accuracy <= 0.0f || accuracy > 1000.0f) {
            return Validation.error("Accuracy must be greater than 0 and no more than 1000 metres.");
        }
        if (movementMode < NativeBridge.MOVEMENT_NONE || movementMode > NativeBridge.MOVEMENT_JOGGING) {
            return Validation.error("Movement mode is incompatible with this manager.");
        }
        if (joystickEnabled && movementMode == NativeBridge.MOVEMENT_NONE) {
            return Validation.error("Select walking or jogging before enabling the joystick.");
        }
        return Validation.ok();
    }

    public String coordinateSummary() {
        if (!hasCoordinates) {
            return "No saved coordinate";
        }
        return String.format(Locale.US, "%.6f, %.6f", latitude, longitude);
    }

    public static Double parseFiniteDouble(String value) {
        if (value == null) {
            return null;
        }
        String normalized = value.trim().replace(',', '.');
        if (normalized.isEmpty()) {
            return null;
        }
        try {
            double parsed = Double.parseDouble(normalized);
            return Double.isFinite(parsed) ? parsed : null;
        } catch (NumberFormatException ignored) {
            return null;
        }
    }

    public static Float parseFiniteFloat(String value) {
        Double parsed = parseFiniteDouble(value);
        if (parsed == null || parsed > Float.MAX_VALUE || parsed < -Float.MAX_VALUE) {
            return null;
        }
        return parsed.floatValue();
    }

    public static final class Validation {
        public final boolean valid;
        public final String message;

        private Validation(boolean valid, String message) {
            this.valid = valid;
            this.message = message;
        }

        public static Validation ok() {
            return new Validation(true, "");
        }

        public static Validation error(String message) {
            return new Validation(false, message);
        }
    }
}
