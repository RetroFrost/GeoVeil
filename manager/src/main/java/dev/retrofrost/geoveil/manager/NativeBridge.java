package dev.retrofrost.geoveil.manager;

/**
 * JNI surface registered by the Zygisk payload after this archive is loaded into a
 * specialized process. No library is loaded from Java and no Android service is used.
 */
final class NativeBridge {
    static final int FLAG_ENABLED = 1;
    static final int FLAG_HAS_COORDINATES = 1 << 1;
    static final int FLAG_AUTOMATIC_ALTITUDE = 1 << 2;
    static final int FLAG_EASY_LOCATION_SWITCH = 1 << 3;
    static final int FLAG_EMERGENCY_DISABLE = 1 << 4;
    static final int FLAG_ENGINE_READY = 1 << 5;
    static final int FLAG_JOYSTICK_ENABLED = 1 << 6;

    static final int MOVEMENT_NONE = 0;
    static final int MOVEMENT_WALKING = 1;
    static final int MOVEMENT_JOGGING = 2;

    private NativeBridge() {}

    static native long probe();

    static native long publish(
            long generation,
            int flags,
            int movementMode,
            double latitude,
            double longitude,
            double altitude,
            float speed,
            float bearing,
            float accuracy);

    static native long move(
            long generation,
            float normalizedX,
            float normalizedY,
            int movementMode,
            boolean active,
            long eventMonotonicNanos);

    static native int lastFlags();

    static native int lastMovementMode();

    static native long clearEmergency();

    static native long disableModule();
}
