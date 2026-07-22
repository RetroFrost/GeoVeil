package com.github.fakegps;

import android.content.Context;
import android.content.Intent;
import android.os.Build;

import androidx.annotation.NonNull;
import androidx.core.content.ContextCompat;

import android.widget.Toast;

import com.github.fakegps.model.LocPoint;
import com.github.fakegps.ui.BookmarkActivity;
import com.github.fakegps.ui.FlyToActivity;
import com.github.fakegps.ui.JoyStickView;
import com.github.fakegps.ui.MainActivity;

import tiger.radio.loggerlibrary.Logger;

/**
 * Created by tiger on 7/22/16.
 */
public class JoyStickManager implements IJoyStickPresenter {

    private static final String TAG = "JoyStickManager";

    public static double STEP_DEFAULT = 0.00002;

    private static JoyStickManager INSTANCE = new JoyStickManager();
    private static final String PREFS = "geoavil_preferences";
    private static final String PREF_AUTO_SHOW = "auto_show_analog";

    private Context mContext;
    private LocationThread mLocationThread;
    private boolean mIsStarted = false;
    private double mMoveStep = STEP_DEFAULT;
    private float mAnalogX;
    private float mAnalogY;

    private LocPoint mCurrentLocPoint;

    private LocPoint mTargetLocPoint;
    private int mFlyTime;
    private int mFlyTimeIndex;
    private boolean mIsFlyMode = false;

    private JoyStickView mJoyStickView;

    private JoyStickManager() {
    }


    public void init(Context context) {
        mContext = context;
    }

    public static JoyStickManager get() {
        return INSTANCE;
    }

    public void start(@NonNull LocPoint locPoint) {
        mCurrentLocPoint = locPoint;
        if (mLocationThread == null || !mLocationThread.isAlive()) {
            mLocationThread = new LocationThread(mContext.getApplicationContext(), this);
            mLocationThread.startThread();
        }

        // Start foreground service for Android 8.0+
        startForegroundService();

        if (isAutoShowEnabled()) {
            showJoyStick();
        }
        mIsStarted = true;
    }

    public void stop() {
        if (mLocationThread != null) {
            mLocationThread.stopThread();
            mLocationThread = null;
        }

        // Stop foreground service
        stopForegroundService();

        hideJoyStick();
        mIsStarted = false;
        mAnalogX = 0f;
        mAnalogY = 0f;
    }

    private void startForegroundService() {
        try {
            Intent serviceIntent = new Intent(mContext, FakeLocationService.class);
            ContextCompat.startForegroundService(mContext, serviceIntent);
        } catch (Exception e) {
            Logger.e(TAG, "Failed to start foreground service", e);
        }
    }

    private void stopForegroundService() {
        try {
            Intent serviceIntent = new Intent(mContext, FakeLocationService.class);
            mContext.stopService(serviceIntent);
        } catch (Exception e) {
            Logger.e(TAG, "Failed to stop foreground service", e);
        }
    }

    public boolean isStarted() {
        return mIsStarted;
    }

    public void showJoyStick() {
        if (mJoyStickView == null) {
            mJoyStickView = new JoyStickView(mContext);
            mJoyStickView.setJoyStickPresenter(this);
        }

        if (!mJoyStickView.isShowing()) {
            mJoyStickView.addToWindow();
        }
    }

    public void hideJoyStick() {
        if (mJoyStickView != null && mJoyStickView.isShowing()) {
            mJoyStickView.removeFromWindow();
        }
    }

    public void restoreJoyStick() {
        if (mIsStarted) showJoyStick();
    }

    public boolean isAutoShowEnabled() {
        return mContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .getBoolean(PREF_AUTO_SHOW, true);
    }

    public void setAutoShowEnabled(boolean enabled) {
        mContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .edit().putBoolean(PREF_AUTO_SHOW, enabled).apply();
    }

    public LocPoint getCurrentLocPoint() {
        return mCurrentLocPoint;
    }

    public LocPoint getUpdateLocPoint() {
        if (!mIsFlyMode || mFlyTimeIndex > mFlyTime) {
            return mCurrentLocPoint;
        } else {
            float factor = (float) mFlyTimeIndex / (float) mFlyTime;
            double lat = mCurrentLocPoint.getLatitude() + (factor * (mTargetLocPoint.getLatitude() - mCurrentLocPoint.getLatitude()));
            double lon = mCurrentLocPoint.getLongitude() + (factor * (mTargetLocPoint.getLongitude() - mCurrentLocPoint.getLongitude()));
            mCurrentLocPoint.setLatitude(lat);
            mCurrentLocPoint.setLongitude(lon);
            mFlyTimeIndex++;
            return mCurrentLocPoint;
        }
    }

    public void jumpToLocation(@NonNull LocPoint location) {
        mIsFlyMode = false;
        mCurrentLocPoint = location;
    }

    public void flyToLocation(@NonNull LocPoint location, int flyTime) {
        mTargetLocPoint = location;
        mFlyTime = flyTime;
        mFlyTimeIndex = 0;
        mIsFlyMode = true;
    }

    public boolean isFlyMode() {
        return mIsFlyMode;
    }

    public void stopFlyMode() {
        mIsFlyMode = false;
    }

    public void setMoveStep(double moveStep) {
        mMoveStep = moveStep;
    }

    @Override
    public void onAnalogMove(float x, float y) {
        // Screen Y points down; geographic latitude points up.
        mAnalogX = Math.max(-1f, Math.min(1f, x));
        mAnalogY = Math.max(-1f, Math.min(1f, y));
    }

    /** Applies one movement tick; called by the location publisher once per update. */
    public void applyAnalogMovement() {
        if (mCurrentLocPoint != null && mIsStarted) {
            mCurrentLocPoint.setLongitude(mCurrentLocPoint.getLongitude() + (mAnalogX * mMoveStep));
            mCurrentLocPoint.setLatitude(mCurrentLocPoint.getLatitude() - (mAnalogY * mMoveStep));
        }
    }

    public double getMoveStep() {
        return mMoveStep;
    }


    @Override
    public void onSetLocationClick() {
        Logger.d(TAG, "onSetLocationClick");
        MainActivity.startPage(mContext);
    }

    @Override
    public void onFlyClick() {
        Logger.d(TAG, "onFlyClick");
        if (mIsFlyMode) {
            stopFlyMode();
            Toast.makeText(mContext, "Stop Fly", Toast.LENGTH_SHORT).show();
        } else {
            FlyToActivity.startPage(mContext);
        }

    }

    @Override
    public void onBookmarkLocationClick() {
        Logger.d(TAG, "onBookmarkLocationClick");
        if (mCurrentLocPoint != null) {
            LocPoint locPoint = new LocPoint(mCurrentLocPoint);
            BookmarkActivity.startPage(mContext, "Bookmark", locPoint);
            Toast.makeText(mContext, "Current location is copied!" + "\n" + locPoint, Toast.LENGTH_LONG).show();
        } else {
            Toast.makeText(mContext, "Service is not start!", Toast.LENGTH_SHORT).show();
        }
    }

    @Override
    public void onCopyLocationClick() {
        Logger.d(TAG, "onCopyLocationClick");
        if (mCurrentLocPoint != null) {
            FakeGpsUtils.copyToClipboard(mContext, mCurrentLocPoint.toString());
            Toast.makeText(mContext, "Current location is copied!" + "\n" + mCurrentLocPoint, Toast.LENGTH_LONG).show();
        }
    }


    @Override
    public void onArrowUpClick() {
        Logger.d(TAG, "onArrowUpClick");
        mCurrentLocPoint.setLatitude(mCurrentLocPoint.getLatitude() + mMoveStep);
    }

    @Override
    public void onArrowDownClick() {
        Logger.d(TAG, "onArrowDownClick");
        mCurrentLocPoint.setLatitude(mCurrentLocPoint.getLatitude() - mMoveStep);
    }

    @Override
    public void onArrowLeftClick() {
        Logger.d(TAG, "onArrowLeftClick");
        mCurrentLocPoint.setLongitude(mCurrentLocPoint.getLongitude() - mMoveStep);
    }

    @Override
    public void onArrowRightClick() {
        Logger.d(TAG, "onArrowRightClick");
        mCurrentLocPoint.setLongitude(mCurrentLocPoint.getLongitude() + mMoveStep);
    }

}
