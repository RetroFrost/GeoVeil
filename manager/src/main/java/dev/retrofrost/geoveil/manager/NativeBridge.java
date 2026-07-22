package dev.retrofrost.geoveil.manager;

/** Compatibility constants retained for the manager model; there is no native bridge. */
final class NativeBridge {
    static final int FLAG_ENABLED = 1;
    static final int FLAG_HAS_COORDINATES = 1 << 1;
    static final int FLAG_ENGINE_READY = 1 << 5;
    static final int MOVEMENT_NONE = 0;
    static final int MOVEMENT_WALKING = 1;
    static final int MOVEMENT_JOGGING = 2;
    private NativeBridge() {}
}
