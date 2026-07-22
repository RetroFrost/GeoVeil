package dev.retrofrost.geoveil.manager;

import android.app.Activity;
import android.content.res.ColorStateList;
import android.content.res.Configuration;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.view.Gravity;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.Switch;
import android.widget.TextView;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Bottom control surface for overlay activation and fail-open recovery. */
final class MovementPanel extends LinearLayout {
    private final Activity activity;
    private final BridgeClient bridge = new BridgeClient();
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private final int primary;
    private final int onSurface;
    private final int onSurfaceVariant;
    private final int container;
    private final Switch joystickSwitch;
    private final TextView status;
    private boolean suppress;

    MovementPanel(Activity activity) {
        super(activity);
        this.activity = activity;
        boolean dark = (activity.getResources().getConfiguration().uiMode
                & Configuration.UI_MODE_NIGHT_MASK) == Configuration.UI_MODE_NIGHT_YES;
        primary = resolveSystemColor(
                dark ? "system_accent1_200" : "system_accent1_600",
                dark ? Color.rgb(208, 188, 255) : Color.rgb(103, 80, 164));
        onSurface = dark ? Color.rgb(231, 225, 229) : Color.rgb(29, 27, 32);
        onSurfaceVariant = dark ? Color.rgb(202, 196, 208) : Color.rgb(73, 69, 79);
        container = resolveSystemColor(
                dark ? "system_neutral1_800" : "system_neutral1_50",
                dark ? Color.rgb(43, 41, 48) : Color.rgb(245, 239, 247));

        setOrientation(VERTICAL);
        setPadding(dp(18), dp(12), dp(18), dp(14));
        GradientDrawable background = new GradientDrawable();
        background.setColor(container);
        background.setCornerRadii(new float[]{dp(26), dp(26), dp(26), dp(26), 0, 0, 0, 0});
        setBackground(background);
        setElevation(dp(8));

        LinearLayout row = new LinearLayout(activity);
        row.setOrientation(HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);
        LinearLayout labels = new LinearLayout(activity);
        labels.setOrientation(VERTICAL);
        TextView title = text("Foreground joystick", 16, onSurface, Typeface.BOLD);
        TextView detail = text("Movable in-app control; tap WALK/JOG on the overlay to change speed.",
                12, onSurfaceVariant, Typeface.NORMAL);
        labels.addView(title);
        labels.addView(detail);
        row.addView(labels, new LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        joystickSwitch = new Switch(activity);
        row.addView(joystickSwitch);
        addView(row, new LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT));

        status = text("Checking engine state…", 12, onSurfaceVariant, Typeface.NORMAL);
        status.setPadding(0, dp(6), 0, dp(8));
        addView(status);

        LinearLayout actions = new LinearLayout(activity);
        actions.setOrientation(HORIZONTAL);
        Button clearEmergency = button("Clear emergency latch");
        Button disableModule = button("Disable next reboot");
        actions.addView(clearEmergency, new LayoutParams(0, dp(46), 1f));
        LayoutParams second = new LayoutParams(0, dp(46), 1f);
        second.leftMargin = dp(8);
        actions.addView(disableModule, second);
        addView(actions);

        joystickSwitch.setOnCheckedChangeListener((view, checked) -> {
            if (!suppress) publishJoystick(checked);
        });
        clearEmergency.setOnClickListener(view -> runRecovery(false));
        disableModule.setOnClickListener(view -> runRecovery(true));
        refresh();
    }

    private void refresh() {
        worker.execute(() -> {
            BridgeClient.Result result = bridge.probe();
            activity.runOnUiThread(() -> {
                suppress = true;
                joystickSwitch.setChecked(result.success
                        && (result.flags & NativeBridge.FLAG_JOYSTICK_ENABLED) != 0);
                joystickSwitch.setEnabled(result.success && result.engineReady()
                        && !result.emergencyDisabled());
                suppress = false;
                if (result.emergencyDisabled()) {
                    status.setText("Emergency pass-through is active; hooks will not be retried.");
                } else if (result.engineReady()) {
                    status.setText("Engine ready. The overlay appears in newly started foreground apps.");
                } else {
                    status.setText(result.message);
                }
            });
        });
    }

    private void publishJoystick(boolean enabled) {
        GeoState draft = DraftStore.load(activity);
        int flags = NativeBridge.lastFlags();
        if ((flags & NativeBridge.FLAG_ENABLED) == 0) {
            suppress = true;
            joystickSwitch.setChecked(false);
            suppress = false;
            status.setText("Enable a valid virtual coordinate before enabling the joystick.");
            return;
        }
        draft.enabled = true;
        draft.joystickEnabled = enabled;
        if (draft.movementMode != NativeBridge.MOVEMENT_JOGGING) {
            draft.movementMode = NativeBridge.MOVEMENT_WALKING;
        }
        status.setText("Applying joystick state…");
        worker.execute(() -> {
            BridgeClient.Result result = bridge.publishMovement(
                    draft, enabled, draft.movementMode);
            if (result.success) DraftStore.save(activity, draft);
            activity.runOnUiThread(() -> {
                suppress = true;
                joystickSwitch.setChecked(result.success && enabled);
                suppress = false;
                status.setText(result.success
                        ? (enabled ? "Joystick enabled for foreground activities."
                                : "Joystick disabled; the static coordinate remains active.")
                        : result.message);
            });
        });
    }

    private void runRecovery(boolean disable) {
        status.setText(disable ? "Writing the Magisk disable marker…"
                : "Clearing the resolved emergency latch…");
        worker.execute(() -> {
            BridgeClient.Result result = disable
                    ? bridge.disableModule() : bridge.clearEmergency();
            activity.runOnUiThread(() -> {
                status.setText(result.success
                        ? (disable ? "GeoVeil will stay disabled after the next reboot."
                                : "Emergency latch cleared; activate only after checking logs.")
                        : result.message);
                refresh();
            });
        });
    }

    private Button button(String label) {
        Button button = new Button(activity);
        button.setText(label);
        button.setTextSize(12);
        button.setAllCaps(false);
        button.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        button.setTextColor(primary);
        button.setBackgroundTintList(ColorStateList.valueOf(container));
        return button;
    }

    private TextView text(String value, int sp, int color, int style) {
        TextView text = new TextView(activity);
        text.setText(value);
        text.setTextSize(sp);
        text.setTextColor(color);
        text.setTypeface(Typeface.DEFAULT, style);
        return text;
    }

    private int resolveSystemColor(String name, int fallback) {
        int id = getResources().getIdentifier(name, "color", "android");
        if (id == 0) return fallback;
        try {
            return getResources().getColor(id, activity.getTheme());
        } catch (RuntimeException ignored) {
            return fallback;
        }
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }
}
