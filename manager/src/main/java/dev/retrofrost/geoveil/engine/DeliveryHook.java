package dev.retrofrost.geoveil.engine;

import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;

/**
 * LSPlant callback used only inside system_server. The native payload supplies the
 * backup method and rewrites the first LocationResult argument before delivery.
 */
public final class DeliveryHook {
    private final Method backup;

    public DeliveryHook(Method backup) {
        this.backup = backup;
        this.backup.setAccessible(true);
    }

    public Object callback(Object[] arguments) throws Throwable {
        if (arguments == null || arguments.length < 2) {
            throw new IllegalArgumentException("GeoVeil received an invalid delivery callback");
        }

        Object receiver = arguments[0];
        Object[] originalArguments = new Object[arguments.length - 1];
        System.arraycopy(arguments, 1, originalArguments, 0, originalArguments.length);
        if (originalArguments.length > 0 && originalArguments[0] != null) {
            Object rewritten = rewriteLocationResult(originalArguments[0]);
            if (rewritten != null) {
                originalArguments[0] = rewritten;
            }
        }

        try {
            return backup.invoke(receiver, originalArguments);
        } catch (InvocationTargetException exception) {
            Throwable cause = exception.getCause();
            throw cause != null ? cause : exception;
        }
    }

    private static native Object rewriteLocationResult(Object locationResult);
}
