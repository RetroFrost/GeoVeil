package dev.retrofrost.geoveil.manager;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.util.Locale;
import java.util.concurrent.TimeUnit;

/** Root transport to the module-owned geoveilctl executable. */
final class RootBridge {
    private static final String CONTROL = "/data/adb/modules/geoveil/bin/geoveilctl";
    private static final Object ROOT_LOCK = new Object();
    private volatile int lastFlags;
    private volatile int lastMovementMode;

    long probe() {
        return execute("probe");
    }

    long publish(
            long generation,
            int flags,
            int movementMode,
            double latitude,
            double longitude,
            double altitude,
            float speed,
            float bearing,
            float accuracy) {
        String arguments = String.format(Locale.US,
                "publish %d %d %d %.10f %.10f %.4f %.4f %.4f %.4f",
                generation, flags, movementMode, latitude, longitude, altitude,
                speed, bearing, accuracy);
        return execute(arguments);
    }

    long clearEmergency() {
        return execute("clear-emergency");
    }

    long disableModule() {
        return execute("disable-module");
    }

    int lastFlags() {
        return lastFlags;
    }

    int lastMovementMode() {
        return lastMovementMode;
    }

    private long execute(String arguments) {
        synchronized (ROOT_LOCK) {
            return executeLocked(arguments);
        }
    }

    private long executeLocked(String arguments) {
        Process process = null;
        try {
            process = new ProcessBuilder("su", "-c", CONTROL + " " + arguments)
                    .redirectErrorStream(true)
                    .start();
            if (!process.waitFor(60L, TimeUnit.SECONDS)) {
                process.destroyForcibly();
                return -6L;
            }
            String response = null;
            try (BufferedReader reader = new BufferedReader(
                    new InputStreamReader(process.getInputStream()))) {
                String line;
                while ((line = reader.readLine()) != null) {
                    if (line.startsWith("OK ") || line.startsWith("ERR ")) response = line;
                }
            }
            if (response == null) return -6L;
            String[] fields = response.trim().split("\\s+");
            if (fields.length != 4 && fields.length != 5) return -6L;
            if ("OK".equals(fields[0]) && fields.length == 4) {
                long generation = Long.parseLong(fields[1]);
                lastFlags = Integer.parseUnsignedInt(fields[2]);
                lastMovementMode = Integer.parseUnsignedInt(fields[3]);
                return generation;
            }
            if ("ERR".equals(fields[0]) && fields.length == 5) {
                long status = Long.parseLong(fields[1]);
                lastFlags = Integer.parseUnsignedInt(fields[3]);
                lastMovementMode = Integer.parseUnsignedInt(fields[4]);
                return status;
            }
            return -6L;
        } catch (Throwable ignored) {
            if (process != null) process.destroy();
            return -6L;
        }
    }
}
