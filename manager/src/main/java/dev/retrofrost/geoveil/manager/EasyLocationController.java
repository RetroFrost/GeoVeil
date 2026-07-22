package dev.retrofrost.geoveil.manager;

import android.app.Application;
import android.content.ClipData;
import android.content.ClipboardManager;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Optional clipboard coordinate input. The listener is inert unless the saved
 * Easy Location Switch toggle is enabled and the engine is already enabled.
 */
final class EasyLocationController implements ClipboardManager.OnPrimaryClipChangedListener {
    private static final Pattern PAIR = Pattern.compile(
            "(?:@|\\b)([-+]?(?:\\d+(?:\\.\\d*)?|\\.\\d+))\\s*[,;]\\s*"
                    + "([-+]?(?:\\d+(?:\\.\\d*)?|\\.\\d+))(?:\\b|$)");
    private static EasyLocationController instance;

    private final Application application;
    private final ClipboardManager clipboard;
    private final BridgeClient bridge = new BridgeClient(true);
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private String lastHandled = "";

    private EasyLocationController(Application application) {
        this.application = application;
        clipboard = application.getSystemService(ClipboardManager.class);
    }

    static synchronized void install(Application application) {
        if (instance != null || application == null) return;
        EasyLocationController controller = new EasyLocationController(application);
        if (controller.clipboard == null) return;
        instance = controller;
        controller.clipboard.addPrimaryClipChangedListener(controller);
    }

    @Override
    public void onPrimaryClipChanged() {
        GeoState draft = DraftStore.load(application);
        if (!draft.easyLocationSwitch) return;

        ClipData clip = clipboard.getPrimaryClip();
        if (clip == null || clip.getItemCount() == 0) return;
        CharSequence text = clip.getItemAt(0).coerceToText(application);
        if (text == null) return;
        String value = text.toString().trim();
        if (value.isEmpty() || value.equals(lastHandled)) return;
        Matcher matcher = PAIR.matcher(value);
        if (!matcher.find()) return;

        Double latitude = GeoState.parseFiniteDouble(matcher.group(1));
        Double longitude = GeoState.parseFiniteDouble(matcher.group(2));
        if (latitude == null || longitude == null) return;
        draft.enabled = true;
        draft.hasCoordinates = true;
        draft.latitude = latitude;
        draft.longitude = longitude;
        GeoState.Validation validation = draft.validate();
        if (!validation.valid) return;
        lastHandled = value;

        worker.execute(() -> {
            BridgeClient.Result probe = bridge.probe();
            if (!probe.success || !probe.engineReady()) {
                return;
            }
            BridgeClient.Result result = bridge.publish(draft);
            if (result.success) DraftStore.save(application, draft);
        });
    }
}
