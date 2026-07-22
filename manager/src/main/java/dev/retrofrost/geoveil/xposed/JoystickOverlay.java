package dev.retrofrost.geoveil.xposed;

import android.app.Activity;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.LinearLayout;

import java.util.Collections;
import java.util.Map;
import java.util.WeakHashMap;

import dev.retrofrost.geoveil.manager.RemoteState;

/** A small in-app overlay; it exists only inside LSPosed-scoped activities. */
final class JoystickOverlay {
    private static final Map<Activity, View> INSTALLED = Collections.synchronizedMap(new WeakHashMap<>());

    static void install(Activity activity, SharedPreferences prefs) {
        if (activity == null || activity.isFinishing() || INSTALLED.containsKey(activity)) return;
        View root = activity.getWindow().getDecorView().findViewById(android.R.id.content);
        if (!(root instanceof ViewGroup)) return;
        LinearLayout pad = new LinearLayout(activity);
        pad.setOrientation(LinearLayout.VERTICAL);
        pad.setPadding(dp(activity, 6), dp(activity, 6), dp(activity, 6), dp(activity, 6));
        GradientDrawable bg = new GradientDrawable(); bg.setColor(0xdd202124); bg.setCornerRadius(dp(activity, 16));
        pad.setBackground(bg);
        LinearLayout row1 = row(activity), row2 = row(activity), row3 = row(activity);
        row1.addView(button(activity, "▲", v -> move(prefs, 1, 0)));
        row2.addView(button(activity, "◀", v -> move(prefs, 0, -1)));
        Button mode = button(activity, "WALK", v -> {
            boolean jog = v.getTag() == Boolean.TRUE;
            v.setTag(!jog); ((Button) v).setText(jog ? "WALK" : "JOG");
            prefs.edit().putInt(RemoteState.MOVEMENT_MODE, jog ? 1 : 2).commit();
        });
        mode.setTag(Boolean.FALSE); row2.addView(mode);
        row2.addView(button(activity, "▶", v -> move(prefs, 0, 1)));
        row3.addView(button(activity, "▼", v -> move(prefs, -1, 0)));
        pad.addView(row1); pad.addView(row2); pad.addView(row3);
        FrameLayout.LayoutParams lp = new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT,
                Gravity.BOTTOM | Gravity.END);
        lp.setMargins(0, 0, dp(activity, 22), dp(activity, 94));
        ((ViewGroup) root).addView(pad, lp);
        INSTALLED.put(activity, pad);
    }

    private static LinearLayout row(Activity a) { LinearLayout r = new LinearLayout(a); r.setGravity(Gravity.CENTER); return r; }
    private static Button button(Activity a, String text, View.OnClickListener l) {
        Button b = new Button(a); b.setText(text); b.setTextColor(Color.WHITE); b.setTextSize(11); b.setMinWidth(dp(a, 46));
        b.setOnClickListener(l); return b;
    }
    private static void move(SharedPreferences p, int north, int east) {
        if (!p.getBoolean(RemoteState.ENABLED, false)) return;
        double lat = Double.longBitsToDouble(p.getLong(RemoteState.LATITUDE, 0L));
        double lon = Double.longBitsToDouble(p.getLong(RemoteState.LONGITUDE, 0L));
        int mode = p.getInt(RemoteState.MOVEMENT_MODE, 1);
        double step = mode == 2 ? 0.00018d : 0.00006d;
        p.edit().putLong(RemoteState.LATITUDE, Double.doubleToRawLongBits(lat + north * step))
                .putLong(RemoteState.LONGITUDE, Double.doubleToRawLongBits(lon + east * step)).commit();
    }
    private static int dp(Activity a, int n) { return Math.round(n * a.getResources().getDisplayMetrics().density); }
}
