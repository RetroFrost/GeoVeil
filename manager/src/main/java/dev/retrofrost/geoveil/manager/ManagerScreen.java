package dev.retrofrost.geoveil.manager;

import android.app.Activity;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.res.ColorStateList;
import android.content.res.Configuration;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.text.Editable;
import android.text.InputType;
import android.text.TextWatcher;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Switch;
import android.widget.TextView;

import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Programmatic Material-3-inspired surface hosted by the standalone manager activity. */
final class ManagerScreen extends ScrollView {
    private static final Pattern COORDINATE_PAIR = Pattern.compile(
            "([+-]?(?:\\d+(?:\\.\\d+)?|\\.\\d+))(?:\\s*[,;]\\s*|\\s+)"
                    + "([+-]?(?:\\d+(?:\\.\\d+)?|\\.\\d+))");
    private final Activity activity;
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private final BridgeClient bridge = new BridgeClient(true);

    private final boolean dark;
    private final int surface;
    private final int surfaceContainer;
    private final int surfaceContainerHigh;
    private final int onSurface;
    private final int onSurfaceVariant;
    private final int primary;
    private final int onPrimary;
    private final int error;

    private TextView statusTitle;
    private TextView statusDetail;
    private Switch enabledSwitch;
    private FilledField latitudeField;
    private FilledField longitudeField;
    private Switch automaticAltitudeSwitch;
    private FilledField altitudeField;
    private FilledField speedField;
    private FilledField bearingField;
    private FilledField accuracyField;
    private Switch easySwitch;
    private Button applyButton;
    private boolean suppressEnabledListener;

    ManagerScreen(Activity activity) {
        super(activity);
        this.activity = activity;
        dark = (activity.getResources().getConfiguration().uiMode
                & Configuration.UI_MODE_NIGHT_MASK) == Configuration.UI_MODE_NIGHT_YES;
        surface = dark ? Color.rgb(28, 27, 31) : Color.rgb(255, 251, 254);
        surfaceContainer = resolveSystemColor(
                dark ? "system_neutral1_800" : "system_neutral1_50",
                dark ? Color.rgb(33, 31, 38) : Color.rgb(245, 239, 247));
        surfaceContainerHigh = resolveSystemColor(
                dark ? "system_neutral1_700" : "system_neutral1_100",
                dark ? Color.rgb(43, 41, 48) : Color.rgb(236, 230, 240));
        onSurface = dark ? Color.rgb(231, 225, 229) : Color.rgb(29, 27, 32);
        onSurfaceVariant = dark ? Color.rgb(202, 196, 208) : Color.rgb(73, 69, 79);
        primary = resolveSystemColor(
                dark ? "system_accent1_200" : "system_accent1_600",
                dark ? Color.rgb(208, 188, 255) : Color.rgb(103, 80, 164));
        onPrimary = dark ? Color.rgb(56, 30, 114) : Color.WHITE;
        error = dark ? Color.rgb(255, 180, 171) : Color.rgb(179, 38, 30);

        setFillViewport(true);
        setBackgroundColor(surface);
        buildUi();
        loadDraft();
        probeBridge();
    }

    private void buildUi() {
        LinearLayout root = new LinearLayout(activity);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(20), dp(18), dp(20), dp(40));
        addView(root, new LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT));

        TextView eyebrow = text("GEOVEIL RC2", 12, primary, Typeface.BOLD);
        eyebrow.setLetterSpacing(0.14f);
        root.addView(eyebrow);

        TextView title = text("Location control", 32, onSurface, Typeface.BOLD);
        title.setPadding(0, dp(6), 0, 0);
        root.addView(title);

        TextView subtitle = text(
                "Root manager for the GeoVeil Magisk module. Grant Magisk access, paste a Maps coordinate pair, and apply it to the engine.",
                15,
                onSurfaceVariant,
                Typeface.NORMAL);
        subtitle.setPadding(0, dp(8), 0, dp(18));
        root.addView(subtitle);

        LinearLayout statusCard = card();
        statusTitle = text("Checking engine", 16, onSurface, Typeface.BOLD);
        statusDetail = text("Waiting for Magisk root access…", 14, onSurfaceVariant, Typeface.NORMAL);
        statusDetail.setPadding(0, dp(4), 0, 0);
        statusCard.addView(statusTitle);
        statusCard.addView(statusDetail);
        root.addView(statusCard, spacedMatch());
        Button retryRoot = button("Retry root connection", false);
        retryRoot.setOnClickListener(view -> probeBridge());
        root.addView(retryRoot, spacedMatchSmall());

        LinearLayout enableCard = card();
        LinearLayout enableRow = new LinearLayout(activity);
        enableRow.setOrientation(LinearLayout.HORIZONTAL);
        enableRow.setGravity(Gravity.CENTER_VERTICAL);
        TextView enableLabel = text("Virtual location", 18, onSurface, Typeface.BOLD);
        enableRow.addView(enableLabel, new LinearLayout.LayoutParams(0, LayoutParams.WRAP_CONTENT, 1f));
        enabledSwitch = new Switch(activity);
        enabledSwitch.setShowText(false);
        enabledSwitch.setButtonTintList(null);
        enableRow.addView(enabledSwitch);
        enableCard.addView(enableRow);
        TextView enableHelp = text(
                "Fresh installs start disabled. A coordinate is required before the bridge can enable the engine.",
                13,
                onSurfaceVariant,
                Typeface.NORMAL);
        enableHelp.setPadding(0, dp(6), 0, 0);
        enableCard.addView(enableHelp);
        root.addView(enableCard, spacedMatch());

        TextView coordinateHeading = text("Coordinates", 20, onSurface, Typeface.BOLD);
        coordinateHeading.setPadding(0, dp(10), 0, dp(10));
        root.addView(coordinateHeading);

        Button pasteCoordinates = button("Paste Maps coordinates", false);
        pasteCoordinates.setOnClickListener(view -> pasteCoordinatePair());
        root.addView(pasteCoordinates, spacedMatchSmall());

        latitudeField = new FilledField("Latitude", "-90 to 90");
        longitudeField = new FilledField("Longitude", "-180 to 180");
        root.addView(latitudeField, spacedMatchSmall());
        root.addView(longitudeField, spacedMatchSmall());

        applyButton = button("Apply coordinate", true);
        Button disableButton = button("Return to genuine location", false);
        Button clearButton = button("Clear saved draft", false);
        root.addView(applyButton, spacedMatch());
        root.addView(disableButton, spacedMatchSmall());
        root.addView(clearButton, spacedMatchSmall());

        TextView advancedHeading = text("Advanced", 20, onSurface, Typeface.BOLD);
        advancedHeading.setPadding(0, dp(20), 0, dp(10));
        root.addView(advancedHeading);

        LinearLayout altitudeCard = card();
        LinearLayout altitudeRow = new LinearLayout(activity);
        altitudeRow.setOrientation(LinearLayout.HORIZONTAL);
        altitudeRow.setGravity(Gravity.CENTER_VERTICAL);
        TextView altitudeLabel = text("Automatic altitude", 16, onSurface, Typeface.BOLD);
        altitudeRow.addView(altitudeLabel, new LinearLayout.LayoutParams(0, LayoutParams.WRAP_CONTENT, 1f));
        automaticAltitudeSwitch = new Switch(activity);
        automaticAltitudeSwitch.setChecked(true);
        altitudeRow.addView(automaticAltitudeSwitch);
        altitudeCard.addView(altitudeRow);
        altitudeField = new FilledField("Manual altitude (m)", "-500 to 9000");
        altitudeField.setVisibility(GONE);
        LinearLayout.LayoutParams altitudeParams = new LinearLayout.LayoutParams(
                LayoutParams.MATCH_PARENT,
                LayoutParams.WRAP_CONTENT);
        altitudeParams.topMargin = dp(10);
        altitudeCard.addView(altitudeField, altitudeParams);
        root.addView(altitudeCard, spacedMatchSmall());

        speedField = new FilledField("Speed (m/s)", "0 to 150");
        bearingField = new FilledField("Bearing (°)", "0 to 359.999");
        accuracyField = new FilledField("Accuracy (m)", "0 to 1000");
        root.addView(speedField, spacedMatchSmall());
        root.addView(bearingField, spacedMatchSmall());
        root.addView(accuracyField, spacedMatchSmall());

        LinearLayout easyCard = card();
        LinearLayout easyRow = new LinearLayout(activity);
        easyRow.setOrientation(LinearLayout.HORIZONTAL);
        easyRow.setGravity(Gravity.CENTER_VERTICAL);
        LinearLayout easyText = new LinearLayout(activity);
        easyText.setOrientation(LinearLayout.VERTICAL);
        easyText.addView(text("Easy Location Switch", 16, onSurface, Typeface.BOLD));
        easyText.addView(text("Clipboard coordinate parsing; disabled by default.", 13, onSurfaceVariant, Typeface.NORMAL));
        easyRow.addView(easyText, new LinearLayout.LayoutParams(0, LayoutParams.WRAP_CONTENT, 1f));
        easySwitch = new Switch(activity);
        easyRow.addView(easySwitch);
        easyCard.addView(easyRow);
        root.addView(easyCard, spacedMatchSmall());

        TextView safety = text(
                "GeoVeil does not modify Android Watchdog, Rescue Party, telephony, IMEI, SIM, modem, EFS, partitions, or Developer Options mock-location settings.",
                12,
                onSurfaceVariant,
                Typeface.NORMAL);
        safety.setPadding(dp(4), dp(24), dp(4), 0);
        root.addView(safety);

        TextWatcher validator = new SimpleWatcher(this::validateFields);
        latitudeField.edit.addTextChangedListener(validator);
        longitudeField.edit.addTextChangedListener(validator);
        altitudeField.edit.addTextChangedListener(validator);
        speedField.edit.addTextChangedListener(validator);
        bearingField.edit.addTextChangedListener(validator);
        accuracyField.edit.addTextChangedListener(validator);

        automaticAltitudeSwitch.setOnCheckedChangeListener((buttonView, checked) -> {
            altitudeField.setVisibility(checked ? GONE : VISIBLE);
            validateFields();
        });

        enabledSwitch.setOnCheckedChangeListener((buttonView, checked) -> {
            if (suppressEnabledListener) {
                return;
            }
            publishState(checked, false);
        });
        applyButton.setOnClickListener(view -> publishState(enabledSwitch.isChecked(), true));
        disableButton.setOnClickListener(view -> publishState(false, true));
        clearButton.setOnClickListener(view -> clearDraft());
    }

    private void loadDraft() {
        GeoState draft = DraftStore.load(activity);
        if (draft.hasCoordinates) {
            latitudeField.edit.setText(String.format(Locale.US, "%.8f", draft.latitude));
            longitudeField.edit.setText(String.format(Locale.US, "%.8f", draft.longitude));
        }
        automaticAltitudeSwitch.setChecked(draft.automaticAltitude);
        if (!draft.automaticAltitude) {
            altitudeField.edit.setText(String.format(Locale.US, "%.2f", draft.altitude));
        }
        speedField.edit.setText(String.format(Locale.US, "%.2f", draft.speed));
        bearingField.edit.setText(String.format(Locale.US, "%.2f", draft.bearing));
        accuracyField.edit.setText(String.format(Locale.US, "%.2f", draft.accuracy));
        easySwitch.setChecked(draft.easyLocationSwitch);
        validateFields();
    }

    private void probeBridge() {
        setStatus("Manager ready", "Checking whether the RC2 engine bridge is available…", false);
        worker.execute(() -> {
            BridgeClient.Result result = bridge.probe();
            BridgeClient.Result finalResult = result;
            activity.runOnUiThread(() -> {
                if (finalResult.success) {
                    boolean active = finalResult.engineReady()
                            && (finalResult.flags & NativeBridge.FLAG_ENABLED) != 0;
                    setEnabledSwitch(active);
                    if (finalResult.emergencyDisabled()) {
                        setStatus("Emergency pass-through",
                                "Root is granted, but GeoVeil's safety latch is active.", false);
                    } else if (!finalResult.engineReady()) {
                        setStatus("Root granted; engine not ready",
                                "Wait for engine initialization before enabling a coordinate.", false);
                    } else {
                        setStatus(active ? "Virtual location enabled" : "Root module connected",
                                active ? "The engine accepted an enabled state."
                                        : "Engine ready; genuine location remains active.", true);
                    }
                } else {
                    setStatus("Pass-through mode", finalResult.message, false);
                    setEnabledSwitch(false);
                }
            });
        });
    }

    private void publishState(boolean requestedEnabled, boolean saveDraft) {
        ParseResult parsed = parseState(requestedEnabled);
        renderValidation(parsed);
        if (!parsed.validation.valid) {
            setEnabledSwitch(false);
            setStatus("Invalid coordinate state", parsed.validation.message, false);
            return;
        }

        if (saveDraft) {
            DraftStore.save(activity, parsed.state);
        }

        applyButton.setEnabled(false);
        setStatus("Applying state", "Waiting for the bounded local bridge response…", false);
        worker.execute(() -> {
            BridgeClient.Result result = bridge.publish(parsed.state);
            activity.runOnUiThread(() -> {
                applyButton.setEnabled(true);
                if (result.success) {
                    setEnabledSwitch(parsed.state.enabled);
                    String mode = parsed.state.enabled ? "Virtual location enabled" : "Genuine location restored";
                    setStatus(mode, parsed.state.coordinateSummary(), true);
                } else {
                    setEnabledSwitch(false);
                    setStatus("Pass-through mode", result.message, false);
                }
            });
        });
    }

    private void clearDraft() {
        DraftStore.clear(activity);
        latitudeField.edit.setText("");
        longitudeField.edit.setText("");
        automaticAltitudeSwitch.setChecked(true);
        altitudeField.edit.setText("");
        speedField.edit.setText("0.00");
        bearingField.edit.setText("0.00");
        accuracyField.edit.setText("5.00");
        easySwitch.setChecked(false);
        setEnabledSwitch(false);
        validateFields();
        setStatus("Draft cleared", "The engine was not enabled or restarted.", true);
    }

    private void pasteCoordinatePair() {
        ClipboardManager clipboard = (ClipboardManager) activity.getSystemService(
                Context.CLIPBOARD_SERVICE);
        ClipData data = clipboard != null ? clipboard.getPrimaryClip() : null;
        CharSequence clipboardText = data != null && data.getItemCount() > 0
                ? data.getItemAt(0).coerceToText(activity) : null;
        if (clipboardText == null) {
            setStatus("Nothing to paste", "Copy a Maps coordinate pair or URL first.", false);
            return;
        }

        String decoded = Uri.decode(clipboardText.toString());
        String preferred = decoded;
        int at = decoded.indexOf('@');
        if (at >= 0 && at + 1 < decoded.length()) preferred = decoded.substring(at + 1);
        double[] pair = findCoordinatePair(preferred);
        if (pair == null && !preferred.equals(decoded)) pair = findCoordinatePair(decoded);
        if (pair == null) {
            setStatus("Coordinates not found",
                    "Copy text containing latitude, longitude, or a Google Maps URL.", false);
            return;
        }

        latitudeField.edit.setText(String.format(Locale.US, "%.8f", pair[0]));
        longitudeField.edit.setText(String.format(Locale.US, "%.8f", pair[1]));
        validateFields();
        setStatus("Coordinates pasted",
                String.format(Locale.US, "%.8f, %.8f", pair[0], pair[1]), true);
    }

    private static double[] findCoordinatePair(String text) {
        Matcher matcher = COORDINATE_PAIR.matcher(text);
        while (matcher.find()) {
            Double latitude = GeoState.parseFiniteDouble(matcher.group(1));
            Double longitude = GeoState.parseFiniteDouble(matcher.group(2));
            if (latitude != null && longitude != null
                    && latitude >= -90.0 && latitude <= 90.0
                    && longitude >= -180.0 && longitude <= 180.0) {
                return new double[]{latitude, longitude};
            }
        }
        return null;
    }

    private void validateFields() {
        ParseResult parsed = parseState(enabledSwitch != null && enabledSwitch.isChecked());
        renderValidation(parsed);
        if (applyButton != null) {
            applyButton.setEnabled(parsed.validation.valid);
        }
    }

    private ParseResult parseState(boolean requestedEnabled) {
        latitudeField.clearError();
        longitudeField.clearError();
        altitudeField.clearError();
        speedField.clearError();
        bearingField.clearError();
        accuracyField.clearError();

        GeoState state = new GeoState();
        state.enabled = requestedEnabled;
        String latitudeText = latitudeField.value();
        String longitudeText = longitudeField.value();
        boolean latitudeEmpty = latitudeText.isEmpty();
        boolean longitudeEmpty = longitudeText.isEmpty();

        if (latitudeEmpty != longitudeEmpty) {
            return ParseResult.error(state, "Latitude and longitude must be entered together.");
        }
        if (!latitudeEmpty) {
            Double latitude = GeoState.parseFiniteDouble(latitudeText);
            Double longitude = GeoState.parseFiniteDouble(longitudeText);
            if (latitude == null) {
                latitudeField.setError("Enter a finite latitude.");
                return ParseResult.error(state, "Latitude is malformed or not finite.");
            }
            if (longitude == null) {
                longitudeField.setError("Enter a finite longitude.");
                return ParseResult.error(state, "Longitude is malformed or not finite.");
            }
            state.hasCoordinates = true;
            state.latitude = latitude;
            state.longitude = longitude;
        }

        state.automaticAltitude = automaticAltitudeSwitch.isChecked();
        if (!state.automaticAltitude) {
            Double altitude = GeoState.parseFiniteDouble(altitudeField.value());
            if (altitude == null) {
                altitudeField.setError("Enter a finite altitude.");
                return ParseResult.error(state, "Manual altitude is malformed or not finite.");
            }
            state.altitude = altitude;
        }

        Float speed = valueOrDefault(speedField, 0.0f);
        Float bearing = valueOrDefault(bearingField, 0.0f);
        Float accuracy = valueOrDefault(accuracyField, 5.0f);
        if (speed == null) {
            speedField.setError("Enter a finite speed.");
            return ParseResult.error(state, "Speed is malformed or not finite.");
        }
        if (bearing == null) {
            bearingField.setError("Enter a finite bearing.");
            return ParseResult.error(state, "Bearing is malformed or not finite.");
        }
        if (accuracy == null) {
            accuracyField.setError("Enter a finite accuracy.");
            return ParseResult.error(state, "Accuracy is malformed or not finite.");
        }
        state.speed = speed;
        state.bearing = bearing;
        state.accuracy = accuracy;
        state.easyLocationSwitch = easySwitch.isChecked();

        GeoState.Validation validation = state.validate();
        return new ParseResult(state, validation);
    }

    private Float valueOrDefault(FilledField field, float fallback) {
        String value = field.value();
        return value.isEmpty() ? fallback : GeoState.parseFiniteFloat(value);
    }

    private void renderValidation(ParseResult parsed) {
        if (parsed.validation.valid) {
            return;
        }
        String message = parsed.validation.message;
        if (message.startsWith("Latitude")) latitudeField.setError(message);
        if (message.startsWith("Longitude")) longitudeField.setError(message);
        if (message.startsWith("Manual altitude")) altitudeField.setError(message);
        if (message.startsWith("Speed")) speedField.setError(message);
        if (message.startsWith("Bearing")) bearingField.setError(message);
        if (message.startsWith("Accuracy")) accuracyField.setError(message);
    }

    private void setEnabledSwitch(boolean enabled) {
        suppressEnabledListener = true;
        enabledSwitch.setChecked(enabled);
        suppressEnabledListener = false;
    }

    private void setStatus(String title, String detail, boolean healthy) {
        statusTitle.setText(title);
        statusTitle.setTextColor(healthy ? primary : onSurface);
        statusDetail.setText(detail);
    }

    private LinearLayout card() {
        LinearLayout card = new LinearLayout(activity);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(dp(16), dp(15), dp(16), dp(15));
        card.setBackground(rounded(surfaceContainer, 22));
        return card;
    }

    private Button button(String label, boolean filled) {
        Button button = new Button(activity);
        button.setText(label);
        button.setTextSize(14);
        button.setAllCaps(false);
        button.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        button.setMinHeight(dp(52));
        button.setTextColor(filled ? onPrimary : primary);
        button.setBackgroundTintList(ColorStateList.valueOf(filled ? primary : surfaceContainerHigh));
        return button;
    }

    private TextView text(String value, int sp, int color, int style) {
        TextView view = new TextView(activity);
        view.setText(value);
        view.setTextSize(sp);
        view.setTextColor(color);
        view.setTypeface(Typeface.DEFAULT, style);
        view.setLineSpacing(0f, 1.12f);
        return view;
    }

    private GradientDrawable rounded(int color, int radiusDp) {
        GradientDrawable drawable = new GradientDrawable();
        drawable.setColor(color);
        drawable.setCornerRadius(dp(radiusDp));
        return drawable;
    }

    private LinearLayout.LayoutParams spacedMatch() {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                LayoutParams.MATCH_PARENT,
                LayoutParams.WRAP_CONTENT);
        params.topMargin = dp(12);
        return params;
    }

    private LinearLayout.LayoutParams spacedMatchSmall() {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                LayoutParams.MATCH_PARENT,
                LayoutParams.WRAP_CONTENT);
        params.topMargin = dp(8);
        return params;
    }

    private int resolveSystemColor(String name, int fallback) {
        int id = activity.getResources().getIdentifier(name, "color", "android");
        if (id == 0) {
            return fallback;
        }
        try {
            return activity.getColor(id);
        } catch (RuntimeException ignored) {
            return fallback;
        }
    }

    private int dp(int value) {
        return Math.round(value * activity.getResources().getDisplayMetrics().density);
    }

    @Override
    protected void onDetachedFromWindow() {
        worker.shutdownNow();
        super.onDetachedFromWindow();
    }

    private final class FilledField extends LinearLayout {
        final EditText edit;
        final TextView errorText;
        final View indicator;

        FilledField(String label, String hint) {
            super(activity);
            setOrientation(VERTICAL);
            setPadding(dp(14), dp(9), dp(14), 0);
            setBackground(rounded(surfaceContainerHigh, 14));

            TextView labelView = text(label, 12, primary, Typeface.BOLD);
            addView(labelView);

            edit = new EditText(activity);
            edit.setTextSize(17);
            edit.setTextColor(onSurface);
            edit.setHintTextColor(onSurfaceVariant);
            edit.setHint(hint);
            edit.setSingleLine(true);
            edit.setSelectAllOnFocus(false);
            edit.setPadding(0, dp(2), 0, dp(6));
            edit.setInputType(InputType.TYPE_CLASS_NUMBER
                    | InputType.TYPE_NUMBER_FLAG_DECIMAL
                    | InputType.TYPE_NUMBER_FLAG_SIGNED);
            edit.setBackgroundColor(Color.TRANSPARENT);
            addView(edit, new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    ViewGroup.LayoutParams.WRAP_CONTENT));

            indicator = new View(activity);
            indicator.setBackgroundColor(onSurfaceVariant);
            addView(indicator, new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    dp(1)));

            errorText = text("", 12, error, Typeface.NORMAL);
            errorText.setVisibility(GONE);
            errorText.setPadding(0, dp(4), 0, dp(7));
            addView(errorText);

            edit.setOnFocusChangeListener((view, focused) ->
                    indicator.setBackgroundColor(focused ? primary : onSurfaceVariant));
        }

        String value() {
            return edit.getText().toString().trim();
        }

        void setError(String message) {
            errorText.setText(message);
            errorText.setVisibility(VISIBLE);
            indicator.setBackgroundColor(error);
        }

        void clearError() {
            errorText.setText("");
            errorText.setVisibility(GONE);
            indicator.setBackgroundColor(edit.hasFocus() ? primary : onSurfaceVariant);
        }
    }

    private static final class ParseResult {
        final GeoState state;
        final GeoState.Validation validation;

        ParseResult(GeoState state, GeoState.Validation validation) {
            this.state = state;
            this.validation = validation;
        }

        static ParseResult error(GeoState state, String message) {
            return new ParseResult(state, GeoState.Validation.error(message));
        }
    }

    private static final class SimpleWatcher implements TextWatcher {
        private final Runnable callback;

        SimpleWatcher(Runnable callback) {
            this.callback = callback;
        }

        @Override
        public void beforeTextChanged(CharSequence sequence, int start, int count, int after) {
        }

        @Override
        public void onTextChanged(CharSequence sequence, int start, int before, int count) {
            callback.run();
        }

        @Override
        public void afterTextChanged(Editable editable) {
        }
    }
}
