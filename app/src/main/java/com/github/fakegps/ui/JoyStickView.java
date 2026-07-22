package com.github.fakegps.ui;

import android.content.Context;
import android.graphics.PixelFormat;
import android.os.Build;
import android.view.Gravity;
import android.view.LayoutInflater;
import android.view.MotionEvent;
import android.view.View;
import android.view.WindowManager;
import android.widget.FrameLayout;

import com.github.fakegps.IJoyStickPresenter;
import com.github.fakegps.ScreenUtils;
import com.github.fakegps.JoyStickManager;
import com.tencent.fakegps.R;

/**
 * Created by tiger on 7/22/16.
 */
public class JoyStickView extends FrameLayout {

    private static int sStatusBarHeight;

    private int mViewWidth;
    private int mViewHeight;
    private WindowManager mWindowManager;
    private WindowManager.LayoutParams mWindowLayoutParams;
    // touch point x pos according to screen
    private float mXInScreen;
    // touch point y pos according to screen
    private float mYInScreen;
    // touch point x pos according to view
    private float mXInView;
    // touch point y pos according to view
    private float mYInView;

    private boolean isShowing = false;

    private IJoyStickPresenter mJoyStickPresenter;

    public JoyStickView(Context context) {
        super(context);
        mWindowManager = (WindowManager) context
                .getSystemService(Context.WINDOW_SERVICE);
        LayoutInflater.from(context).inflate(R.layout.joystick_layout, this);

        sStatusBarHeight = ScreenUtils.getStatusBarHeight(context);
        mViewWidth = context.getResources().getDimensionPixelSize(R.dimen.joystick_width);
        mViewHeight = context.getResources().getDimensionPixelSize(R.dimen.joystick_height);

        mWindowLayoutParams = new WindowManager.LayoutParams();
        // Use TYPE_APPLICATION_OVERLAY for Android O (26) and above
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            mWindowLayoutParams.type = WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY;
        } else {
            mWindowLayoutParams.type = WindowManager.LayoutParams.TYPE_PHONE;
        }
        mWindowLayoutParams.format = PixelFormat.RGBA_8888;
        mWindowLayoutParams.flags = WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL
                | WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE;
        mWindowLayoutParams.gravity = Gravity.LEFT | Gravity.TOP;

        //the real width and height is needed, or the view cannot be shown
        mWindowLayoutParams.width = mViewWidth;
        mWindowLayoutParams.height = mViewHeight;
        // Keep the default panel fully visible near the right edge.
        mWindowLayoutParams.x = Math.max(0, ScreenUtils.getScreenWidth(context) - mViewWidth - 16);
        mWindowLayoutParams.y = ScreenUtils.getScreenHeight(context) / 2;

        findViewById(R.id.btn_set_loc).setOnClickListener(mOnClickListener);
        findViewById(R.id.btn_fly_to).setOnClickListener(mOnClickListener);
        findViewById(R.id.btn_bookmark).setOnClickListener(mOnClickListener);
        findViewById(R.id.btn_bookmark).setOnLongClickListener(new OnLongClickListener() {
            @Override
            public boolean onLongClick(View v) {
                if (mJoyStickPresenter != null) {
                    mJoyStickPresenter.onCopyLocationClick();
                }
                return true;
            }
        });

        findViewById(R.id.btn_hide_joystick).setOnClickListener(v ->
                JoyStickManager.get().hideJoyStick());

        AnalogJoystickView analogJoystick = findViewById(R.id.analog_joystick);
        analogJoystick.setListener(new AnalogJoystickView.Listener() {
            @Override
            public void onMove(float x, float y) {
                if (mJoyStickPresenter != null) mJoyStickPresenter.onAnalogMove(x, y);
            }

            @Override
            public void onRelease() {
                if (mJoyStickPresenter != null) mJoyStickPresenter.onAnalogMove(0f, 0f);
            }
        });

    }

    @Override
    protected void onMeasure(int widthMeasureSpec, int heightMeasureSpec) {
        super.onMeasure(widthMeasureSpec, heightMeasureSpec);

    }

    public void addToWindow() {
        android.content.SharedPreferences prefs = getContext().getSharedPreferences("geoavil_preferences", Context.MODE_PRIVATE);
        mWindowLayoutParams.x = prefs.getInt("joystick_x", mWindowLayoutParams.x);
        mWindowLayoutParams.y = prefs.getInt("joystick_y", mWindowLayoutParams.y);
        mWindowManager.addView(this, mWindowLayoutParams);
        isShowing = true;
    }

    public void removeFromWindow() {
        mWindowManager.removeView(this);
        isShowing = false;
    }

    public boolean isShowing() {
        return isShowing;
    }

    private View.OnClickListener mOnClickListener = new OnClickListener() {
        @Override
        public void onClick(View v) {
            int id = v.getId();
            if (id == R.id.btn_up) {
                if (mJoyStickPresenter != null) mJoyStickPresenter.onArrowUpClick();
            } else if (id == R.id.btn_down) {
                if (mJoyStickPresenter != null) mJoyStickPresenter.onArrowDownClick();
            } else if (id == R.id.btn_left) {
                if (mJoyStickPresenter != null) mJoyStickPresenter.onArrowLeftClick();
            } else if (id == R.id.btn_right) {
                if (mJoyStickPresenter != null) mJoyStickPresenter.onArrowRightClick();
            } else if (id == R.id.btn_set_loc) {
                if (mJoyStickPresenter != null) mJoyStickPresenter.onSetLocationClick();
            } else if (id == R.id.btn_fly_to) {
                if (mJoyStickPresenter != null) mJoyStickPresenter.onFlyClick();
            } else if (id == R.id.btn_bookmark) {
                if (mJoyStickPresenter != null) mJoyStickPresenter.onBookmarkLocationClick();
            }
        }
    };

    public void setJoyStickPresenter(IJoyStickPresenter joyStickPresenter) {
        mJoyStickPresenter = joyStickPresenter;
    }

    @Override
    public boolean onTouchEvent(MotionEvent event) {
        switch (event.getAction()) {
            case MotionEvent.ACTION_DOWN:
                mXInView = event.getX();
                mYInView = event.getY();
                break;
            case MotionEvent.ACTION_MOVE:
                mXInScreen = event.getRawX();
                mYInScreen = event.getRawY() - sStatusBarHeight;
                updateViewPosition();
                break;
        }
        return true;
    }


    private void updateViewPosition() {
        mWindowLayoutParams.x = (int) (mXInScreen - mXInView);
        mWindowLayoutParams.y = (int) (mYInScreen - mYInView);
        mWindowManager.updateViewLayout(this, mWindowLayoutParams);
        getContext().getSharedPreferences("geoavil_preferences", Context.MODE_PRIVATE)
                .edit().putInt("joystick_x", mWindowLayoutParams.x)
                .putInt("joystick_y", mWindowLayoutParams.y).apply();
    }
}
