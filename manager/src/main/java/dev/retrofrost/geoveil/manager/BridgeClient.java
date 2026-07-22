package dev.retrofrost.geoveil.manager;

import android.os.SystemClock;

import java.util.concurrent.atomic.AtomicLong;

/** Bounded manager-side client backed by the persistent Zygisk companion connection. */
final class BridgeClient {
    private static final AtomicLong GENERATION = new AtomicLong(
            Math.max(1L, SystemClock.elapsedRealtimeNanos()));

    Result probe() {
        return decode(NativeBridge.probe());
    }

    Result publish(GeoState state) {
        GeoState.Validation validation = state.validate();
        if (!validation.valid) {
            return Result.error(validation.message, NativeBridge.lastFlags());
        }

        int flags = 0;
        if (state.enabled) flags |= NativeBridge.FLAG_ENABLED;
        if (state.hasCoordinates) flags |= NativeBridge.FLAG_HAS_COORDINATES;
        if (state.automaticAltitude) flags |= NativeBridge.FLAG_AUTOMATIC_ALTITUDE;
        if (state.easyLocationSwitch) flags |= NativeBridge.FLAG_EASY_LOCATION_SWITCH;
        if (state.joystickEnabled) flags |= NativeBridge.FLAG_JOYSTICK_ENABLED;

        long generation = nextGeneration();
        long result = NativeBridge.publish(
                generation,
                flags,
                state.movementMode,
                state.latitude,
                state.longitude,
                state.altitude,
                state.speed,
                state.bearing,
                state.accuracy);
        return decode(result);
    }

    Result move(float normalizedX, float normalizedY, int movementMode, boolean active) {
        long generation = nextGeneration();
        long result = NativeBridge.move(
                generation,
                normalizedX,
                normalizedY,
                movementMode,
                active,
                SystemClock.elapsedRealtimeNanos());
        return decode(result);
    }

    Result clearEmergency() {
        return decode(NativeBridge.clearEmergency());
    }

    Result disableModule() {
        return decode(NativeBridge.disableModule());
    }

    private static long nextGeneration() {
        for (;;) {
            long current = GENERATION.get();
            long clock = Math.max(1L, SystemClock.elapsedRealtimeNanos());
            long next = Math.max(current + 1L, clock);
            if (GENERATION.compareAndSet(current, next)) {
                return next;
            }
        }
    }

    private static Result decode(long value) {
        int flags = NativeBridge.lastFlags();
        if (value >= 0L) {
            return Result.ok(value, flags);
        }
        String message;
        if (value == -2L) {
            message = "Engine bridge schema is incompatible with this manager.";
        } else if (value == -3L) {
            message = "The engine rejected an invalid coordinate state.";
        } else if (value == -4L) {
            message = "The engine rejected an older state generation; retry the action.";
        } else if (value == -5L) {
            message = "Emergency pass-through is active. GeoVeil will not install hooks.";
        } else if (value == -7L) {
            message = "The location engine is not ready; genuine location remains active.";
        } else {
            message = "The root companion connection is unavailable; genuine location remains active.";
        }
        return Result.error(message, flags);
    }

    static final class Result {
        final boolean success;
        final long generation;
        final int flags;
        final String message;

        private Result(boolean success, long generation, int flags, String message) {
            this.success = success;
            this.generation = generation;
            this.flags = flags;
            this.message = message;
        }

        boolean engineReady() {
            return (flags & NativeBridge.FLAG_ENGINE_READY) != 0;
        }

        boolean emergencyDisabled() {
            return (flags & NativeBridge.FLAG_EMERGENCY_DISABLE) != 0;
        }

        static Result ok(long generation, int flags) {
            return new Result(true, generation, flags, "State accepted by the root companion.");
        }

        static Result error(String message, int flags) {
            return new Result(false, -1L, flags, message);
        }
    }
}
