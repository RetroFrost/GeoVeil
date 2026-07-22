package com.github.fakegps;

import android.content.Context;
import android.location.Location;
import android.location.LocationManager;
import android.location.provider.ProviderProperties;
import android.os.Build;
import android.os.Handler;
import android.os.HandlerThread;
import android.os.SystemClock;

import com.github.fakegps.model.LocPoint;

import tiger.radio.loggerlibrary.Logger;

/**
 * LocationThread - uses standard Mock Location API (addTestProvider + setTestProviderLocation)
 * instead of hidden ILocationManager. No root required.
 * User must select this app as "Mock location app" in Developer Options.
 */
public class LocationThread extends HandlerThread {

    private static final String TAG = "LocationThread";
    private static final String[] PROVIDERS = {LocationManager.GPS_PROVIDER, LocationManager.NETWORK_PROVIDER};

    private Context mContext;
    private JoyStickManager mJoyStickManager;
    private LocationManager mLocationManager;

    private Handler mHandler;
    private LocPoint mLastLocPoint = new LocPoint(0, 0);
    private boolean mProvidersAdded = false;
    private boolean mRootBackend = false;

    public LocationThread(Context context, JoyStickManager joyStickManager) {
        super("LocationThread");
        mContext = context;
        mJoyStickManager = joyStickManager;
        mLocationManager = (LocationManager) context.getSystemService(Context.LOCATION_SERVICE);
    }

    @Override
    public synchronized void start() {
        super.start();
        mHandler = new Handler(getLooper());
        mHandler.post(mSetupAndRun);
    }

    public void startThread() {
        start();
    }

    public void stopThread() {
        if (mHandler != null) {
            mHandler.removeCallbacksAndMessages(null);
        }
        if (mRootBackend) {
            RootBridge.removeProviders();
            mRootBackend = false;
        } else {
            removeTestProviders();
        }
        try {
            quit();
            interrupt();
        } catch (Exception e) {
            Logger.e(TAG, "stopThread fail!", e);
        }
        mJoyStickManager = null;
    }

    private void addTestProviders() {
        if (mProvidersAdded) return;
        // Root users do not need to select GeoAvil in Developer Options.
        // This does not alter Location.isMock; Android still owns that metadata.
        mRootBackend = RootBridge.setupProviders();
        if (mRootBackend) {
            Logger.d(TAG, "Using root location command backend");
            return;
        }
        for (String provider : PROVIDERS) {
            try {
                // Remove existing test provider if any
                try {
                    mLocationManager.removeTestProvider(provider);
                } catch (Exception ignored) {
                }

                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                    // Android 12+ uses ProviderProperties
                    mLocationManager.addTestProvider(provider,
                            false, false, false, false, false,
                            true, true,
                            ProviderProperties.POWER_USAGE_LOW,
                            ProviderProperties.ACCURACY_FINE);
                } else {
                    mLocationManager.addTestProvider(provider,
                            false, false, false, false, false,
                            true, true,
                            android.location.Criteria.POWER_LOW,
                            android.location.Criteria.ACCURACY_FINE);
                }
                mLocationManager.setTestProviderEnabled(provider, true);
                Logger.d(TAG, "Test provider added: " + provider);
            } catch (SecurityException e) {
                Logger.e(TAG, "Cannot add test provider '" + provider + "'. " +
                        "Make sure this app is selected as mock location app in Developer Options.", e);
            } catch (Exception e) {
                Logger.e(TAG, "Error adding test provider: " + provider, e);
            }
        }
        mProvidersAdded = true;
    }

    private void removeTestProviders() {
        if (!mProvidersAdded) return;
        for (String provider : PROVIDERS) {
            try {
                mLocationManager.setTestProviderEnabled(provider, false);
                mLocationManager.removeTestProvider(provider);
                Logger.d(TAG, "Test provider removed: " + provider);
            } catch (Exception e) {
                Logger.e(TAG, "Error removing test provider: " + provider, e);
            }
        }
        mProvidersAdded = false;
    }

    private final Runnable mSetupAndRun = new Runnable() {
        @Override
        public void run() {
            addTestProviders();
            mHandler.post(mUpdateLocation);
        }
    };

    private final Runnable mUpdateLocation = new Runnable() {
        @Override
        public void run() {
            if (mJoyStickManager == null) return;

            mJoyStickManager.applyAnalogMovement();
            LocPoint locPoint = mJoyStickManager.getUpdateLocPoint();
            Logger.d(TAG, "UpdateLocation, " + locPoint);

            if (mRootBackend) {
                RootBridge.publish(locPoint.getLatitude(), locPoint.getLongitude(), System.currentTimeMillis());
            } else for (String provider : PROVIDERS) {
                try {
                    Location location = new Location(provider);
                    location.setLatitude(locPoint.getLatitude());
                    location.setLongitude(locPoint.getLongitude());
                    location.setAltitude(50);
                    location.setAccuracy(10);
                    location.setTime(System.currentTimeMillis());
                    location.setElapsedRealtimeNanos(SystemClock.elapsedRealtimeNanos());

                    if (mLastLocPoint.getLatitude() != locPoint.getLatitude()
                            || mLastLocPoint.getLongitude() != locPoint.getLongitude()) {
                        location.setSpeed(1);
                    } else {
                        location.setSpeed(0);
                    }

                    // Set bearing and speed accuracy for newer APIs
                    location.setBearing(0);
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                        location.setBearingAccuracyDegrees(0.1f);
                        location.setVerticalAccuracyMeters(1.0f);
                        location.setSpeedAccuracyMetersPerSecond(0.1f);
                    }

                    mLocationManager.setTestProviderLocation(provider, location);

                } catch (Exception e) {
                    Logger.e(TAG, "Failed to set location for provider: " + provider, e);
                }
            }

            mLastLocPoint.setLatitude(locPoint.getLatitude());
            mLastLocPoint.setLongitude(locPoint.getLongitude());

            mHandler.postDelayed(mUpdateLocation, 1000);
        }
    };

    public Handler getHandler() {
        return mHandler;
    }
}
