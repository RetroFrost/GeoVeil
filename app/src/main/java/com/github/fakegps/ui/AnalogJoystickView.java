package com.github.fakegps.ui;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.PointF;
import android.util.AttributeSet;
import android.view.MotionEvent;
import android.view.View;

/** A compact floating analog stick. Values are normalized to -1..1. */
public class AnalogJoystickView extends View {
    public interface Listener {
        void onMove(float x, float y);
        void onRelease();
    }

    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final PointF knob = new PointF();
    private Listener listener;
    private float radius;
    private float knobRadius;

    public AnalogJoystickView(Context context, AttributeSet attrs) {
        super(context, attrs);
        setFocusable(true);
        paint.setStyle(Paint.Style.FILL);
    }

    public void setListener(Listener listener) {
        this.listener = listener;
    }

    @Override
    protected void onSizeChanged(int width, int height, int oldWidth, int oldHeight) {
        radius = Math.min(width, height) * 0.42f;
        knobRadius = radius * 0.34f;
        centerKnob();
    }

    private void centerKnob() {
        knob.set(getWidth() / 2f, getHeight() / 2f);
    }

    @Override
    protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        float cx = getWidth() / 2f;
        float cy = getHeight() / 2f;
        paint.setColor(Color.argb(150, 25, 25, 30));
        canvas.drawCircle(cx, cy, radius, paint);
        paint.setColor(Color.argb(220, 80, 150, 255));
        canvas.drawCircle(knob.x, knob.y, knobRadius, paint);
    }

    @Override
    public boolean onTouchEvent(MotionEvent event) {
        if (event.getAction() == MotionEvent.ACTION_UP || event.getAction() == MotionEvent.ACTION_CANCEL) {
            centerKnob();
            invalidate();
            if (listener != null) listener.onRelease();
            return true;
        }
        if (event.getAction() == MotionEvent.ACTION_DOWN || event.getAction() == MotionEvent.ACTION_MOVE) {
            float cx = getWidth() / 2f;
            float cy = getHeight() / 2f;
            float dx = event.getX() - cx;
            float dy = event.getY() - cy;
            float distance = (float) Math.hypot(dx, dy);
            float max = Math.max(1f, radius - knobRadius);
            if (distance > max) {
                dx = dx / distance * max;
                dy = dy / distance * max;
            }
            knob.set(cx + dx, cy + dy);
            invalidate();
            if (listener != null) listener.onMove(dx / max, dy / max);
            return true;
        }
        return true;
    }
}
