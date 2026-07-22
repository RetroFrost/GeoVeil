package dev.retrofrost.geoveil.manager;

import android.app.Application;

import io.github.libxposed.service.XposedService;
import io.github.libxposed.service.XposedServiceHelper;

/** Receives the LSPosed service binder used for shared, live module settings. */
public final class GeoVeilApplication extends Application
        implements XposedServiceHelper.OnServiceListener {
    private static volatile XposedService service;

    @Override public void onCreate() {
        super.onCreate();
        XposedServiceHelper.registerListener(this);
    }

    @Override public void onServiceBind(XposedService bound) {
        service = bound;
    }

    @Override public void onServiceDied(XposedService dead) {
        if (service == dead) service = null;
    }

    static XposedService service() {
        return service;
    }
}
