package com.github.fakegps;

import java.util.Locale;
import java.util.concurrent.TimeUnit;

/** Small, opt-in root bridge. It only grants this app Android's mock-location AppOp. */
public final class RootBridge {
    private RootBridge() {}

    public static boolean setupProviders() {
        // Adding an already-existing provider can return an error; enabling it
        // is the reliable capability check for both fresh and repeated starts.
        runRoot("cmd location providers add-test-provider gps");
        runRoot("cmd location providers add-test-provider network");
        boolean gps = runRoot("cmd location providers set-test-provider-enabled gps true");
        boolean network = runRoot("cmd location providers set-test-provider-enabled network true");
        return gps && network;
    }

    public static void removeProviders() {
        runRoot("cmd location providers set-test-provider-enabled gps false");
        runRoot("cmd location providers set-test-provider-enabled network false");
        runRoot("cmd location providers remove-test-provider gps");
        runRoot("cmd location providers remove-test-provider network");
    }

    public static boolean publish(double latitude, double longitude, long time) {
        String location = String.format(Locale.US, "%f,%f", latitude, longitude);
        String command = "cmd location providers set-test-provider-location %s --location %s --time %d";
        return runRoot(String.format(Locale.US, command, "gps", location, time))
                && runRoot(String.format(Locale.US, command, "network", location, time));
    }

    private static boolean runRoot(String command) {
        Process process = null;
        try {
            process = new ProcessBuilder("su", "-c", command)
                    .redirectErrorStream(true)
                    .start();
            boolean finished = process.waitFor(5, TimeUnit.SECONDS);
            return finished && process.exitValue() == 0;
        } catch (Exception ignored) {
            return false;
        } finally {
            if (process != null) {
                try { process.destroy(); } catch (Exception ignored) { }
            }
        }
    }
}
