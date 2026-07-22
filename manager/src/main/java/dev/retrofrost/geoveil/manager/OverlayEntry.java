package dev.retrofrost.geoveil.manager;

import android.app.Activity;
import android.app.Application;
import android.os.Bundle;
import android.view.Gravity;
import android.view.ViewGroup;
import android.widget.FrameLayout;

import java.lang.ref.WeakReference;
import java.util.WeakHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Entry point loaded only into an explicitly retained top-application process. */
public final class OverlayEntry {
    private static boolean installed;

    private OverlayEntry() {}

    public static synchronized void install(Application application) {
        if (installed || application == null) {
            return;
        }
        installed = true;
        application.registerActivityLifecycleCallbacks(new OverlayLifecycle());
    }

    private static final class OverlayLifecycle implements Application.ActivityLifecycleCallbacks {
        private final WeakHashMap<Activity, WeakReference<JoystickView>> overlays = new WeakHashMap<>();
        private final ExecutorService worker = Executors.newSingleThreadExecutor();

        @Override
        public void onActivityResumed(Activity activity) {
            worker.execute(() -> {
                long probe = NativeBridge.probe();
                int flags = NativeBridge.lastFlags();
                boolean show = probe >= 0
                        && (flags & NativeBridge.FLAG_ENGINE_READY) != 0
                        && (flags & NativeBridge.FLAG_ENABLED) != 0
                        && (flags & NativeBridge.FLAG_JOYSTICK_ENABLED) != 0;
                activity.runOnUiThread(() -> updateOverlay(activity, show));
            });
        }

        @Override
        public void onActivityPaused(Activity activity) {
            removeOverlay(activity);
        }

        @Override
        public void onActivityDestroyed(Activity activity) {
            removeOverlay(activity);
            overlays.remove(activity);
        }

        private void updateOverlay(Activity activity, boolean show) {
            WeakReference<JoystickView> reference = overlays.get(activity);
            JoystickView existing = reference != null ? reference.get() : null;
            if (!show) {
                if (existing != null) {
                    existing.stopMovement();
                    ViewGroup parent = (ViewGroup) existing.getParent();
                    if (parent != null) parent.removeView(existing);
                }
                overlays.remove(activity);
                return;
            }
            if (existing != null && existing.getParent() != null) {
                return;
            }

            ViewGroup decor = (ViewGroup) activity.getWindow().getDecorView();
            JoystickView joystick = new JoystickView(activity);
            int size = joystick.dp(168);
            FrameLayout.LayoutParams params = new FrameLayout.LayoutParams(size, size, Gravity.END | Gravity.BOTTOM);
            params.setMargins(joystick.dp(12), joystick.dp(12), joystick.dp(18), joystick.dp(28));
            decor.addView(joystick, params);
            overlays.put(activity, new WeakReference<>(joystick));
        }

        private void removeOverlay(Activity activity) {
            WeakReference<JoystickView> reference = overlays.get(activity);
            JoystickView view = reference != null ? reference.get() : null;
            if (view == null) return;
            view.stopMovement();
            ViewGroup parent = (ViewGroup) view.getParent();
            if (parent != null) parent.removeView(view);
        }

        @Override public void onActivityCreated(Activity activity, Bundle state) {}
        @Override public void onActivityStarted(Activity activity) {}
        @Override public void onActivityStopped(Activity activity) {}
        @Override public void onActivitySaveInstanceState(Activity activity, Bundle state) {}
    }
}
