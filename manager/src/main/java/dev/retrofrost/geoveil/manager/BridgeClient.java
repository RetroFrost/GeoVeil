package dev.retrofrost.geoveil.manager;

import android.os.SystemClock;

import java.util.concurrent.atomic.AtomicLong;

/** Bounded client using root control in the manager and JNI inside injected overlays. */
final class BridgeClient {
    private static final AtomicLong GENERATION = new AtomicLong(
            Math.max(1L, SystemClock.elapsedRealtimeNanos()));
    private final boolean rootTransport;
    private final RootBridge rootBridge;

    BridgeClient() {
        this(false);
    }

    BridgeClient(boolean rootTransport) {
        this.rootTransport = rootTransport;
        rootBridge = rootTransport ? new RootBridge() : null;
    }

    Result probe() {
        return decode(rootTransport ? rootBridge.probe() : NativeBridge.safeProbe());
    }

    Result publish(GeoState state) {
        int currentFlags = lastFlags();
        int currentMovement = lastMovementMode();
        if (state.movementMode == NativeBridge.MOVEMENT_NONE) {
            state.movementMode = currentMovement == NativeBridge.MOVEMENT_JOGGING
                    ? NativeBridge.MOVEMENT_JOGGING : NativeBridge.MOVEMENT_WALKING;
        }
        // The main coordinate form does not own the overlay controls. Preserve the
        // current companion state unless the movement panel explicitly changes it.
        if ((currentFlags & NativeBridge.FLAG_JOYSTICK_ENABLED) != 0) {
            state.joystickEnabled = true;
        }

        GeoState.Validation validation = state.validate();
        if (!validation.valid) {
            return Result.error(validation.message, currentFlags);
        }

        int flags = 0;
        if (state.enabled) flags |= NativeBridge.FLAG_ENABLED;
        if (state.hasCoordinates) flags |= NativeBridge.FLAG_HAS_COORDINATES;
        if (state.automaticAltitude) flags |= NativeBridge.FLAG_AUTOMATIC_ALTITUDE;
        if (state.easyLocationSwitch) flags |= NativeBridge.FLAG_EASY_LOCATION_SWITCH;
        if (state.joystickEnabled) flags |= NativeBridge.FLAG_JOYSTICK_ENABLED;

        long generation = nextGeneration();
        long result = publishRaw(
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

    Result publishMovement(GeoState state, boolean enabled, int movementMode) {
        state.enabled = (lastFlags() & NativeBridge.FLAG_ENABLED) != 0;
        state.joystickEnabled = enabled;
        state.movementMode = movementMode == NativeBridge.MOVEMENT_JOGGING
                ? NativeBridge.MOVEMENT_JOGGING : NativeBridge.MOVEMENT_WALKING;
        GeoState.Validation validation = state.validate();
        if (!validation.valid) {
            return Result.error(validation.message, lastFlags());
        }

        int flags = 0;
        if (state.enabled) flags |= NativeBridge.FLAG_ENABLED;
        if (state.hasCoordinates) flags |= NativeBridge.FLAG_HAS_COORDINATES;
        if (state.automaticAltitude) flags |= NativeBridge.FLAG_AUTOMATIC_ALTITUDE;
        if (state.easyLocationSwitch) flags |= NativeBridge.FLAG_EASY_LOCATION_SWITCH;
        if (state.joystickEnabled) flags |= NativeBridge.FLAG_JOYSTICK_ENABLED;
        long result = publishRaw(
                nextGeneration(), flags, state.movementMode,
                state.latitude, state.longitude, state.altitude,
                state.speed, state.bearing, state.accuracy);
        return decode(result);
    }

    Result move(float normalizedX, float normalizedY, int movementMode, boolean active) {
        long generation = nextGeneration();
        long result = rootTransport ? -6L : NativeBridge.safeMove(
                generation,
                normalizedX,
                normalizedY,
                movementMode,
                active,
                SystemClock.elapsedRealtimeNanos());
        return decode(result);
    }

    Result clearEmergency() {
        return decode(rootTransport
                ? rootBridge.clearEmergency() : NativeBridge.safeClearEmergency());
    }

    Result disableModule() {
        return decode(rootTransport
                ? rootBridge.disableModule() : NativeBridge.safeDisableModule());
    }

    int lastFlags() {
        return rootTransport ? rootBridge.lastFlags() : NativeBridge.safeLastFlags();
    }

    int lastMovementMode() {
        return rootTransport
                ? rootBridge.lastMovementMode() : NativeBridge.safeLastMovementMode();
    }

    private long publishRaw(
            long generation,
            int flags,
            int movementMode,
            double latitude,
            double longitude,
            double altitude,
            float speed,
            float bearing,
            float accuracy) {
        return rootTransport
                ? rootBridge.publish(generation, flags, movementMode, latitude, longitude,
                        altitude, speed, bearing, accuracy)
                : NativeBridge.safePublish(generation, flags, movementMode, latitude, longitude,
                        altitude, speed, bearing, accuracy);
    }

    private static long nextGeneration() {
        for (;;) {
            long current = GENERATION.get();
            long clock = Math.max(1L, SystemClock.elapsedRealtimeNanos());
            long next = Math.max(current + 1L, clock);
            if (GENERATION.compareAndSet(current, next)) return next;
        }
    }

    private Result decode(long value) {
        int flags = lastFlags();
        if (value >= 0L) return Result.ok(value, flags);
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
            message = rootTransport
                    ? "Root access or the GeoVeil module control helper is unavailable."
                    : "The overlay bridge is unavailable; genuine location remains active.";
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
