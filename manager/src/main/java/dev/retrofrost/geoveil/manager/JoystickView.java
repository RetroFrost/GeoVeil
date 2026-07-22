package dev.retrofrost.geoveil.manager;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Typeface;
import android.os.SystemClock;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewGroup;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

/** Compact in-activity joystick. The header drags the control; the lower disc moves location. */
final class JoystickView extends View {
    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private final AtomicBoolean publishPending = new AtomicBoolean();

    private boolean draggingOverlay;
    private boolean moving;
    private float downRawX;
    private float downRawY;
    private float startTranslationX;
    private float startTranslationY;
    private float knobX;
    private float knobY;
    private volatile float latestX;
    private volatile float latestY;
    private volatile boolean latestActive;
    private long lastQueuedAt;

    JoystickView(Context context) {
        super(context);
        setClickable(true);
        setFocusable(false);
        setLayerType(View.LAYER_TYPE_SOFTWARE, null);
    }

    int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    @Override
    protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        float width = getWidth();
        float height = getHeight();
        float headerHeight = dp(30);
        float centerX = width / 2f;
        float centerY = headerHeight + (height - headerHeight) / 2f;
        float radius = Math.min(width, height - headerHeight) * 0.42f;

        paint.setStyle(Paint.Style.FILL);
        paint.setColor(Color.argb(222, 32, 30, 38));
        canvas.drawRoundRect(0, 0, width, height, dp(24), dp(24), paint);

        paint.setColor(Color.argb(255, 208, 188, 255));
        canvas.drawRoundRect(dp(12), dp(8), width - dp(12), headerHeight - dp(4), dp(10), dp(10), paint);
        paint.setColor(Color.rgb(56, 30, 114));
        paint.setTextAlign(Paint.Align.CENTER);
        paint.setTypeface(Typeface.DEFAULT_BOLD);
        paint.setTextSize(dp(11));
        canvas.drawText("DRAG", centerX, dp(22), paint);

        paint.setColor(Color.argb(150, 208, 188, 255));
        canvas.drawCircle(centerX, centerY, radius, paint);
        paint.setStyle(Paint.Style.STROKE);
        paint.setStrokeWidth(dp(2));
        paint.setColor(Color.argb(230, 231, 225, 229));
        canvas.drawCircle(centerX, centerY, radius * 0.5f, paint);
        canvas.drawCircle(centerX, centerY, radius, paint);

        float x = moving ? knobX : centerX;
        float y = moving ? knobY : centerY;
        paint.setStyle(Paint.Style.FILL);
        paint.setColor(Color.rgb(208, 188, 255));
        canvas.drawCircle(x, y, radius * 0.28f, paint);
    }

    @Override
    public boolean onTouchEvent(MotionEvent event) {
        float headerHeight = dp(30);
        switch (event.getActionMasked()) {
            case MotionEvent.ACTION_DOWN:
                downRawX = event.getRawX();
                downRawY = event.getRawY();
                startTranslationX = getTranslationX();
                startTranslationY = getTranslationY();
                draggingOverlay = event.getY() <= headerHeight;
                moving = !draggingOverlay;
                if (moving) updateJoystick(event.getX(), event.getY(), true);
                return true;
            case MotionEvent.ACTION_MOVE:
                if (draggingOverlay) {
                    moveOverlay(event.getRawX() - downRawX, event.getRawY() - downRawY);
                } else {
                    updateJoystick(event.getX(), event.getY(), true);
                }
                return true;
            case MotionEvent.ACTION_UP:
            case MotionEvent.ACTION_CANCEL:
                if (moving) updateJoystick(event.getX(), event.getY(), false);
                draggingOverlay = false;
                moving = false;
                invalidate();
                performClick();
                return true;
            default:
                return super.onTouchEvent(event);
        }
    }

    @Override
    public boolean performClick() {
        super.performClick();
        return true;
    }

    private void moveOverlay(float deltaX, float deltaY) {
        ViewGroup parent = (ViewGroup) getParent();
        if (parent == null) return;
        float nextX = startTranslationX + deltaX;
        float nextY = startTranslationY + deltaY;
        float minX = -getLeft();
        float maxX = parent.getWidth() - getRight();
        float minY = -getTop();
        float maxY = parent.getHeight() - getBottom();
        setTranslationX(Math.max(minX, Math.min(maxX, nextX)));
        setTranslationY(Math.max(minY, Math.min(maxY, nextY)));
    }

    private void updateJoystick(float touchX, float touchY, boolean active) {
        float headerHeight = dp(30);
        float centerX = getWidth() / 2f;
        float centerY = headerHeight + (getHeight() - headerHeight) / 2f;
        float radius = Math.min(getWidth(), getHeight() - headerHeight) * 0.42f;
        float dx = touchX - centerX;
        float dy = touchY - centerY;
        float distance = (float) Math.hypot(dx, dy);
        if (distance > radius && distance > 0f) {
            dx = dx / distance * radius;
            dy = dy / distance * radius;
        }
        knobX = centerX + dx;
        knobY = centerY + dy;
        latestX = radius > 0f ? dx / radius : 0f;
        latestY = radius > 0f ? dy / radius : 0f;
        latestActive = active;
        invalidate();
        queuePublish(active);
    }

    private void queuePublish(boolean force) {
        long now = SystemClock.uptimeMillis();
        if (!force && now - lastQueuedAt < 80L) return;
        if (force || now - lastQueuedAt >= 80L) lastQueuedAt = now;
        if (!publishPending.compareAndSet(false, true)) return;
        worker.execute(() -> {
            try {
                int mode = NativeBridge.lastMovementMode();
                if (mode != NativeBridge.MOVEMENT_JOGGING) mode = NativeBridge.MOVEMENT_WALKING;
                new BridgeClient().move(latestX, latestY, mode, latestActive);
            } finally {
                publishPending.set(false);
                if (latestActive) postDelayed(() -> queuePublish(false), 80L);
            }
        });
    }

    void stopMovement() {
        latestX = 0f;
        latestY = 0f;
        latestActive = false;
        worker.execute(() -> {
            int mode = NativeBridge.lastMovementMode();
            if (mode == NativeBridge.MOVEMENT_NONE) mode = NativeBridge.MOVEMENT_WALKING;
            new BridgeClient().move(0f, 0f, mode, false);
        });
    }
}
