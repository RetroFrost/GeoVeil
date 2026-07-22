package dev.retrofrost.geoveil.manager;

import android.app.Activity;
import android.app.Application;
import android.content.Intent;
import android.graphics.Color;
import android.os.Bundle;
import android.view.View;
import android.view.Window;
import android.widget.LinearLayout;

import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.Map;
import java.util.concurrent.atomic.AtomicBoolean;

/** Entry point called by the Zygisk shell-child bootstrap after specialization. */
public final class GeoVeilEntry {
    public static final String LAUNCH_CATEGORY = "dev.retrofrost.geoveil.LAUNCH_MANAGER";
    private static final String SHELL_PACKAGE = "com.android.shell";
    private static final AtomicBoolean INSTALLED = new AtomicBoolean(false);
    private static final Object DECOR_TAG = "geoveil-manager-attached-v2";

    private GeoVeilEntry() {}

    public static void install(Application application) {
        if (application == null || !INSTALLED.compareAndSet(false, true)) return;
        EasyLocationController.install(application);
        application.registerActivityLifecycleCallbacks(new Callbacks());
        attachExistingActivityBestEffort();
    }

    private static boolean shouldAttach(Activity activity) {
        if (activity == null || !SHELL_PACKAGE.equals(activity.getPackageName())) return false;
        Intent intent = activity.getIntent();
        return intent != null && intent.hasCategory(LAUNCH_CATEGORY);
    }

    private static void attach(Activity activity) {
        if (!shouldAttach(activity) || activity.isFinishing() || activity.isDestroyed()) return;
        View decor = activity.getWindow().getDecorView();
        if (DECOR_TAG.equals(decor.getTag())) return;
        decor.setTag(DECOR_TAG);

        Window window = activity.getWindow();
        window.setStatusBarColor(Color.TRANSPARENT);
        window.setNavigationBarColor(Color.TRANSPARENT);
        activity.setTitle("GeoVeil");

        LinearLayout container = new LinearLayout(activity);
        container.setOrientation(LinearLayout.VERTICAL);
        ManagerScreen screen = new ManagerScreen(activity);
        container.addView(screen, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f));
        container.addView(new MovementPanel(activity), new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT));
        activity.setContentView(container);
    }

    /** Covers the race where the Shell trampoline created before callbacks registered. */
    private static void attachExistingActivityBestEffort() {
        try {
            Class<?> activityThreadClass = Class.forName("android.app.ActivityThread");
            Method currentThread = activityThreadClass.getDeclaredMethod("currentActivityThread");
            currentThread.setAccessible(true);
            Object activityThread = currentThread.invoke(null);
            if (activityThread == null) return;

            Field activitiesField = activityThreadClass.getDeclaredField("mActivities");
            activitiesField.setAccessible(true);
            Object activities = activitiesField.get(activityThread);
            if (!(activities instanceof Map)) return;

            for (Object record : ((Map<?, ?>) activities).values()) {
                Activity activity = findActivity(record);
                if (activity != null && shouldAttach(activity)) {
                    activity.runOnUiThread(() -> attach(activity));
                }
            }
        } catch (Throwable ignored) {
            // The normal lifecycle callback path remains available. Reflection
            // failure must never destabilize the Android Shell process.
        }
    }

    private static Activity findActivity(Object record) {
        if (record == null) return null;
        Class<?> type = record.getClass();
        while (type != null) {
            try {
                Field activityField = type.getDeclaredField("activity");
                activityField.setAccessible(true);
                Object value = activityField.get(record);
                return value instanceof Activity ? (Activity) value : null;
            } catch (ReflectiveOperationException ignored) {
                type = type.getSuperclass();
            }
        }
        return null;
    }

    private static final class Callbacks implements Application.ActivityLifecycleCallbacks {
        @Override
        public void onActivityCreated(Activity activity, Bundle savedInstanceState) {
            if (shouldAttach(activity)) {
                activity.getWindow().getDecorView().post(() -> attach(activity));
            }
        }

        @Override
        public void onActivityPostCreated(Activity activity, Bundle savedInstanceState) {
            attach(activity);
        }

        @Override
        public void onActivityResumed(Activity activity) {
            attach(activity);
        }

        @Override public void onActivityStarted(Activity activity) {}
        @Override public void onActivityPaused(Activity activity) {}
        @Override public void onActivityStopped(Activity activity) {}
        @Override public void onActivitySaveInstanceState(Activity activity, Bundle outState) {}
        @Override public void onActivityDestroyed(Activity activity) {}
    }
}
