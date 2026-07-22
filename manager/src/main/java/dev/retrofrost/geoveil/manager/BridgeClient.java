package dev.retrofrost.geoveil.manager;

import android.net.LocalSocket;
import android.net.LocalSocketAddress;

import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.util.concurrent.atomic.AtomicLong;

/** Bounded manager client for the root companion's versioned local state bridge. */
final class BridgeClient {
    private static final String SOCKET_NAME = "geoveil.manager.v1";
    private static final int MAGIC = 0x47565354; // GVST
    private static final short VERSION = 1;
    private static final short OP_STATUS = 1;
    private static final short OP_PUBLISH = 2;

    private static final short STATUS_OK = 0;
    private static final short STATUS_INVALID = 1;
    private static final short STATUS_STALE = 2;
    private static final short STATUS_EMERGENCY = 3;

    private static final int FLAG_BRIDGE_READY = 1;
    private static final int FLAG_ENGINE_ACTIVE = 1 << 1;
    private static final int FLAG_EMERGENCY = 1 << 2;
    private static final int FLAG_ENABLED = 1 << 3;
    private static final int FLAG_HAS_COORDINATES = 1 << 4;

    private static final AtomicLong GENERATION = new AtomicLong(System.nanoTime());

    Result probe() {
        return transact(OP_STATUS, null);
    }

    Result publish(GeoState state) {
        GeoState.Validation validation = state.validate();
        if (!validation.valid) {
            return Result.error(validation.message);
        }
        return transact(OP_PUBLISH, state);
    }

    private Result transact(short operation, GeoState state) {
        LocalSocket socket = new LocalSocket();
        try {
            socket.setSoTimeout(750);
            socket.connect(new LocalSocketAddress(
                    SOCKET_NAME,
                    LocalSocketAddress.Namespace.ABSTRACT));

            DataOutputStream output = new DataOutputStream(socket.getOutputStream());
            long generation = GENERATION.incrementAndGet();
            output.writeInt(MAGIC);
            output.writeShort(VERSION);
            output.writeShort(operation);
            output.writeLong(generation);

            if (operation == OP_PUBLISH && state != null) {
                int flags = 0;
                if (state.enabled) flags |= 1;
                if (state.hasCoordinates) flags |= 1 << 1;
                if (state.automaticAltitude) flags |= 1 << 2;
                if (state.easyLocationSwitch) flags |= 1 << 3;
                output.writeInt(flags);
                output.writeDouble(state.latitude);
                output.writeDouble(state.longitude);
                output.writeDouble(state.altitude);
                output.writeFloat(state.speed);
                output.writeFloat(state.bearing);
                output.writeFloat(state.accuracy);
            }
            output.flush();

            DataInputStream input = new DataInputStream(socket.getInputStream());
            if (input.readInt() != MAGIC) {
                return Result.error("Engine bridge returned an invalid response.");
            }
            if (input.readShort() != VERSION) {
                return Result.error("Engine bridge schema is incompatible.");
            }
            short status = input.readShort();
            long acceptedGeneration = input.readLong();
            int flags = input.readInt();

            boolean bridgeReady = (flags & FLAG_BRIDGE_READY) != 0;
            boolean engineActive = (flags & FLAG_ENGINE_ACTIVE) != 0;
            boolean emergency = (flags & FLAG_EMERGENCY) != 0;
            boolean effectiveEnabled = (flags & FLAG_ENABLED) != 0;
            boolean hasCoordinates = (flags & FLAG_HAS_COORDINATES) != 0;

            if (status == STATUS_OK) {
                String message;
                if (emergency) {
                    message = "Emergency pass-through is active.";
                } else if (!engineActive) {
                    message = "State bridge connected; the location hook is not armed, so genuine location still passes through.";
                } else if (effectiveEnabled) {
                    message = "Virtual coordinate accepted by the active engine.";
                } else {
                    message = "Engine connected in genuine-location pass-through mode.";
                }
                return Result.ok(
                        acceptedGeneration,
                        message,
                        bridgeReady,
                        engineActive,
                        emergency,
                        effectiveEnabled,
                        hasCoordinates);
            }

            if (status == STATUS_INVALID) {
                return Result.error("Engine bridge rejected invalid coordinate state.");
            }
            if (status == STATUS_STALE) {
                return Result.error("Engine bridge rejected a stale state generation. Retry the action.");
            }
            if (status == STATUS_EMERGENCY) {
                return Result.error("Emergency pass-through is active; GeoVeil cannot be enabled.");
            }
            return Result.error("Engine bridge rejected the request protocol.");
        } catch (IOException ignored) {
            return Result.error("Engine bridge is unavailable; GeoVeil remains in pass-through mode.");
        } finally {
            try {
                socket.close();
            } catch (IOException ignored) {
            }
        }
    }

    static final class Result {
        final boolean success;
        final long generation;
        final String message;
        final boolean bridgeReady;
        final boolean engineActive;
        final boolean emergency;
        final boolean effectiveEnabled;
        final boolean hasCoordinates;

        private Result(
                boolean success,
                long generation,
                String message,
                boolean bridgeReady,
                boolean engineActive,
                boolean emergency,
                boolean effectiveEnabled,
                boolean hasCoordinates) {
            this.success = success;
            this.generation = generation;
            this.message = message;
            this.bridgeReady = bridgeReady;
            this.engineActive = engineActive;
            this.emergency = emergency;
            this.effectiveEnabled = effectiveEnabled;
            this.hasCoordinates = hasCoordinates;
        }

        static Result ok(
                long generation,
                String message,
                boolean bridgeReady,
                boolean engineActive,
                boolean emergency,
                boolean effectiveEnabled,
                boolean hasCoordinates) {
            return new Result(
                    true,
                    generation,
                    message,
                    bridgeReady,
                    engineActive,
                    emergency,
                    effectiveEnabled,
                    hasCoordinates);
        }

        static Result error(String message) {
            return new Result(false, -1L, message, false, false, false, false, false);
        }
    }
}
