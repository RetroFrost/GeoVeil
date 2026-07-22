package dev.retrofrost.geoveil.manager;

import android.app.Activity;
import android.content.res.Configuration;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.view.Gravity;
import android.view.ViewGroup;
import android.widget.LinearLayout;
import android.widget.Switch;
import android.widget.TextView;

/** Enables the real in-app joystick injected into only LSPosed-scoped activities. */
final class MovementPanel extends LinearLayout {
    private final Activity activity;
    private final BridgeClient bridge = new BridgeClient();
    private final Switch joystick;
    private final TextView status;
    private boolean suppress;

    MovementPanel(Activity activity) {
        super(activity);
        this.activity = activity;
        boolean dark = (getResources().getConfiguration().uiMode & Configuration.UI_MODE_NIGHT_MASK)
                == Configuration.UI_MODE_NIGHT_YES;
        int onSurface = dark ? Color.rgb(231, 225, 229) : Color.rgb(29, 27, 32);
        int variant = dark ? Color.rgb(202, 196, 208) : Color.rgb(73, 69, 79);
        GradientDrawable background = new GradientDrawable();
        background.setColor(dark ? Color.rgb(43, 41, 48) : Color.rgb(245, 239, 247));
        background.setCornerRadii(new float[]{dp(26), dp(26), dp(26), dp(26), 0, 0, 0, 0});
        setBackground(background); setElevation(dp(8)); setOrientation(VERTICAL);
        setPadding(dp(18), dp(12), dp(18), dp(16));
        LinearLayout row = new LinearLayout(activity); row.setGravity(Gravity.CENTER_VERTICAL);
        LinearLayout labels = new LinearLayout(activity); labels.setOrientation(VERTICAL);
        labels.addView(text("Foreground joystick", 16, onSurface, Typeface.BOLD));
        labels.addView(text("D-pad is injected inside selected app activities; reopen the target app after enabling.", 12, variant, Typeface.NORMAL));
        row.addView(labels, new LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        joystick = new Switch(activity); row.addView(joystick); addView(row);
        status = text("Enable virtual location, then turn this on for selected target apps.", 12, variant, Typeface.NORMAL);
        status.setPadding(0, dp(6), 0, 0); addView(status);
        joystick.setOnCheckedChangeListener((v, checked) -> { if (!suppress) publish(checked); });
        refresh();
    }

    private void refresh() {
        GeoState state = DraftStore.load(activity); BridgeClient.Result result = bridge.probe();
        suppress = true; joystick.setChecked(state.joystickEnabled); joystick.setEnabled(result.success); suppress = false;
        if (!result.success) status.setText(result.message);
    }
    private void publish(boolean enabled) {
        GeoState state = DraftStore.load(activity);
        if (!state.hasCoordinates || !state.enabled) {
            suppress = true; joystick.setChecked(false); suppress = false;
            status.setText("Apply a valid, enabled coordinate before enabling the joystick."); return;
        }
        state.joystickEnabled = enabled;
        if (state.movementMode == NativeBridge.MOVEMENT_NONE) state.movementMode = NativeBridge.MOVEMENT_WALKING;
        BridgeClient.Result result = bridge.publish(state);
        if (result.success) { DraftStore.save(activity, state); status.setText(enabled
                ? "Joystick enabled. Close and reopen each selected target app to display it."
                : "Joystick disabled for future target activity resumes.");
        } else { suppress = true; joystick.setChecked(false); suppress = false; status.setText(result.message); }
    }
    private TextView text(String s, int size, int color, int style) { TextView v = new TextView(activity); v.setText(s); v.setTextSize(size); v.setTextColor(color); v.setTypeface(Typeface.DEFAULT, style); return v; }
    private int dp(int n) { return Math.round(n * getResources().getDisplayMetrics().density); }
}
