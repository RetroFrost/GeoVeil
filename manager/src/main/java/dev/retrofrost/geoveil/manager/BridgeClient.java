package dev.retrofrost.geoveil.manager;

import android.content.SharedPreferences;
import android.os.SystemClock;

import java.util.concurrent.atomic.AtomicLong;

/** LSPosed remote-preference client. No su shell, Magisk action, or native companion is used. */
final class BridgeClient {
    private static final AtomicLong GENERATION = new AtomicLong(SystemClock.elapsedRealtimeNanos());

    BridgeClient() {}
    BridgeClient(boolean ignoredLegacyArgument) {}

    Result probe() {
        try {
            SharedPreferences prefs = RemoteState.preferences();
            if (prefs == null) return Result.error("LSPosed is not connected. Enable GeoVeil in LSPosed, then reopen this app.", 0);
            int flags = prefs.getBoolean(RemoteState.ENABLED, false) ? NativeBridge.FLAG_ENABLED : 0;
            if (prefs.getBoolean(RemoteState.HAS_COORDINATES, false)) flags |= NativeBridge.FLAG_HAS_COORDINATES;
            flags |= NativeBridge.FLAG_ENGINE_READY;
            return Result.ok(prefs.getLong(RemoteState.GENERATION, 0L), flags);
        } catch (Throwable t) {
            return Result.error("LSPosed service is unavailable: " + safeMessage(t), 0);
        }
    }

    Result publish(GeoState state) {
        GeoState.Validation validation = state.validate();
        if (!validation.valid) return Result.error(validation.message, lastFlags());
        try {
            long generation = nextGeneration();
            RemoteState.write(state, generation);
            int flags = NativeBridge.FLAG_ENGINE_READY;
            if (state.enabled) flags |= NativeBridge.FLAG_ENABLED;
            if (state.hasCoordinates) flags |= NativeBridge.FLAG_HAS_COORDINATES;
            return Result.ok(generation, flags);
        } catch (Throwable t) {
            return Result.error("Could not write shared LSPosed state: " + safeMessage(t), 0);
        }
    }

    Result publishMovement(GeoState state, boolean enabled, int movementMode) {
        state.joystickEnabled = enabled;
        state.movementMode = movementMode == NativeBridge.MOVEMENT_JOGGING
                ? NativeBridge.MOVEMENT_JOGGING : NativeBridge.MOVEMENT_WALKING;
        return publish(state);
    }

    Result move(float normalizedX, float normalizedY, int movementMode, boolean active) {
        return Result.error("Use the in-app LSPosed joystick in a selected target app.", lastFlags());
    }

    Result clearEmergency() { return Result.ok(nextGeneration(), lastFlags()); }
    Result disableModule() { return Result.error("Disable GeoVeil from LSPosed Modules.", lastFlags()); }

    int lastFlags() {
        Result result = probe();
        return result.flags;
    }

    int lastMovementMode() {
        try {
            SharedPreferences prefs = RemoteState.preferences();
            return prefs == null ? NativeBridge.MOVEMENT_WALKING
                    : prefs.getInt(RemoteState.MOVEMENT_MODE, NativeBridge.MOVEMENT_WALKING);
        } catch (Throwable ignored) { return NativeBridge.MOVEMENT_WALKING; }
    }

    private static long nextGeneration() {
        for (;;) {
            long current = GENERATION.get();
            long next = Math.max(current + 1L, SystemClock.elapsedRealtimeNanos());
            if (GENERATION.compareAndSet(current, next)) return next;
        }
    }
    private static String safeMessage(Throwable t) {
        String message = t.getMessage(); return message == null ? t.getClass().getSimpleName() : message;
    }

    static final class Result {
        final boolean success; final long generation; final int flags; final String message;
        private Result(boolean success, long generation, int flags, String message) {
            this.success = success; this.generation = generation; this.flags = flags; this.message = message;
        }
        boolean engineReady() { return (flags & NativeBridge.FLAG_ENGINE_READY) != 0; }
        boolean emergencyDisabled() { return false; }
        static Result ok(long generation, int flags) {
            return new Result(true, generation, flags, "State saved to LSPosed remote preferences.");
        }
        static Result error(String message, int flags) { return new Result(false, -1L, flags, message); }
    }
}
