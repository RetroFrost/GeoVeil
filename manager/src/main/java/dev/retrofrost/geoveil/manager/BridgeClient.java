package dev.retrofrost.geoveil.manager;

import android.net.LocalSocket;
import android.net.LocalSocketAddress;

import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Bounded manager-side client for the future root companion bridge.
 *
 * This class never runs on the UI thread. The current no-hook native scaffold does not yet
 * provide the server, so connection failure is reported as pass-through rather than guessed.
 */
final class BridgeClient {
    private static final String SOCKET_NAME = "geoveil.manager.v1";
    private static final int MAGIC = 0x47565354; // GVST
    private static final short VERSION = 1;
    private static final short OP_STATUS = 1;
    private static final short OP_PUBLISH = 2;
    private static final short STATUS_OK = 0;
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
            if (status != STATUS_OK) {
                return Result.error("Engine bridge rejected the requested state.");
            }
            return Result.ok(acceptedGeneration);
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

        private Result(boolean success, long generation, String message) {
            this.success = success;
            this.generation = generation;
            this.message = message;
        }

        static Result ok(long generation) {
            return new Result(true, generation, "State accepted by engine bridge.");
        }

        static Result error(String message) {
            return new Result(false, -1L, message);
        }
    }
}
