package com.github.fakegps;

import android.app.Application;
import android.content.Context;

import com.litesuits.orm.LiteOrm;

import java.io.File;

import tiger.radio.loggerlibrary.Logger;

/**
 * Created by tiger on 7/23/16.
 */
public class FakeGpsApp extends Application {

    private static Context sAppContext;
    private volatile static LiteOrm sLiteOrm;

    @Override
    protected void attachBaseContext(Context base) {
        super.attachBaseContext(base);
        sAppContext = base;
    }

    @Override
    public void onCreate() {
        super.onCreate();
        initLogger();
        JoyStickManager.get().init(this);
    }

    public static Context get() {
        return sAppContext;
    }

    public static LiteOrm getLiteOrm() {
        if (sLiteOrm == null) {
            synchronized (FakeGpsApp.class) {
                if (sLiteOrm == null) {
                    sLiteOrm = LiteOrm.newSingleInstance(sAppContext, "fake_gps.db");
                    sLiteOrm.setDebugged(true);
                }
            }
        }
        return sLiteOrm;
    }

    private void initLogger() {
        // Use app-specific external files directory (Scoped Storage compatible)
        File externalDir = getExternalFilesDir(null);
        File outputDir;
        if (externalDir != null) {
            outputDir = new File(externalDir, "logs");
        } else {
            // Fallback to internal storage
            outputDir = new File(getFilesDir(), "logs");
        }
        if (!outputDir.exists()) {
            outputDir.mkdirs();
        }
        Logger.configure(outputDir, "logs");
    }

}
