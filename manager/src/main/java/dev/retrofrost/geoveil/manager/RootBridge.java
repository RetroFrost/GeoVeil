package dev.retrofrost.geoveil.manager;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.util.Locale;
import java.util.concurrent.TimeUnit;

/** Root transport to the module-owned geoveilctl executable. */
final class RootBridge {
    private static final String CONTROL = "/data/adb/modules/geoveil/bin/geoveilctl";
    private static final Object ROOT_LOCK = new Object();
    private volatile int lastFlags;
    private volatile int lastMovementMode;
    private volatile String lastFailure = "Magisk root has not been requested yet.";

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

    String lastFailure() {
        return lastFailure;
    }

    private long execute(String arguments) {
        synchronized (ROOT_LOCK) {
            return executeLocked(arguments);
        }
    }

    private long executeLocked(String arguments) {
        try {
            return executeWithSu("/system/bin/su", arguments);
        } catch (IOException primaryMissing) {
            try {
                return executeWithSu("su", arguments);
            } catch (IOException fallbackMissing) {
                lastFailure = "Magisk su is unavailable: " + compact(fallbackMissing.getMessage());
                return -6L;
            }
        }
    }

    private long executeWithSu(String su, String arguments) throws IOException {
        Process process = null;
        try {
            // Do this separately from the helper invocation.  A granted Magisk policy
            // does not prove that the module helper is installed or that its Zygisk
            // companion has started; reporting those as a generic "root failure"
            // makes a broken installation impossible to diagnose.
            String identity = runRootCommand(su, "id -u");
            if (!"0".equals(identity.trim())) {
                lastFailure = "Magisk did not provide root (id -u returned: "
                        + compact(identity) + ").";
                return -6L;
            }

            process = new ProcessBuilder(su, "-c", CONTROL + " " + arguments)
                    .redirectErrorStream(true)
                    .start();
            if (!process.waitFor(60L, TimeUnit.SECONDS)) {
                process.destroyForcibly();
                lastFailure = "Timed out waiting for the Magisk root request.";
                return -6L;
            }
            String response = null;
            StringBuilder output = new StringBuilder();
            try (BufferedReader reader = new BufferedReader(
                    new InputStreamReader(process.getInputStream()))) {
                String line;
                while ((line = reader.readLine()) != null) {
                    if (line.startsWith("OK ") || line.startsWith("ERR ")) response = line;
                    if (output.length() < 768) {
                        if (output.length() > 0) output.append(' ');
                        output.append(line);
                    }
                }
            }
            if (response == null) {
                String detail = compact(output.toString());
                if (detail.contains("companion did not answer")) {
                    lastFailure = "Root works, but the Zygisk companion is not running. "
                            + "Reboot with GeoVeil enabled and Zygisk on.";
                } else if (detail.contains("not found") || detail.contains("No such file")) {
                    lastFailure = "Root works, but the GeoVeil module helper is missing. "
                            + "Reflash the matching module ZIP and reboot.";
                } else if (detail.contains("Permission denied")) {
                    lastFailure = "Root works, but Android blocked the module helper: " + detail;
                } else {
                    lastFailure = "Module helper failed (exit " + process.exitValue() + "): " + detail;
                }
                return -6L;
            }
            String[] fields = response.trim().split("\\s+");
            if (fields.length != 4 && fields.length != 5) {
                lastFailure = "Module control returned an invalid response.";
                return -6L;
            }
            if ("OK".equals(fields[0]) && fields.length == 4) {
                long generation = Long.parseLong(fields[1]);
                lastFlags = Integer.parseUnsignedInt(fields[2]);
                lastMovementMode = Integer.parseUnsignedInt(fields[3]);
                lastFailure = "";
                return generation;
            }
            if ("ERR".equals(fields[0]) && fields.length == 5) {
                long status = Long.parseLong(fields[1]);
                lastFlags = Integer.parseUnsignedInt(fields[3]);
                lastMovementMode = Integer.parseUnsignedInt(fields[4]);
                lastFailure = "Module control rejected the request (" + status + ").";
                return status;
            }
            lastFailure = "Module control returned an invalid response.";
            return -6L;
        } catch (IOException error) {
            throw error;
        } catch (Throwable error) {
            if (process != null) process.destroy();
            lastFailure = "Root command failed: " + compact(error.getMessage());
            return -6L;
        }
    }

    private static String runRootCommand(String su, String command) throws IOException {
        Process process = new ProcessBuilder(su, "-c", command)
                .redirectErrorStream(true)
                .start();
        try {
            if (!process.waitFor(20L, TimeUnit.SECONDS)) {
                process.destroyForcibly();
                return "timed out";
            }
            StringBuilder output = new StringBuilder();
            try (BufferedReader reader = new BufferedReader(
                    new InputStreamReader(process.getInputStream()))) {
                String line;
                while ((line = reader.readLine()) != null && output.length() < 256) {
                    if (output.length() > 0) output.append(' ');
                    output.append(line);
                }
            }
            return output.toString();
        } catch (InterruptedException error) {
            Thread.currentThread().interrupt();
            process.destroyForcibly();
            return "interrupted";
        }
    }

    private static String compact(String value) {
        if (value == null || value.trim().isEmpty()) return "no diagnostic output";
        String compact = value.trim().replaceAll("\\s+", " ");
        return compact.length() > 220 ? compact.substring(0, 220) : compact;
    }
}
