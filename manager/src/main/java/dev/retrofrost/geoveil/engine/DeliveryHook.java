package dev.retrofrost.geoveil.engine;

import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;

/**
 * LSPlant callback used only inside system_server. The native payload supplies the
 * backup method after a target hook succeeds and before the hook set is committed.
 */
public final class DeliveryHook {
    private Method backup;

    public DeliveryHook() {}

    public void setBackup(Method backup) {
        if (backup == null) {
            throw new IllegalArgumentException("backup method is required");
        }
        backup.setAccessible(true);
        this.backup = backup;
    }

    public Object callback(Object[] arguments) throws Throwable {
        Method callable = backup;
        if (callable == null) {
            throw new IllegalStateException("GeoVeil hook was invoked before backup commit");
        }
        if (arguments == null || arguments.length < 2) {
            throw new IllegalArgumentException("GeoVeil received an invalid delivery callback");
        }

        Object receiver = arguments[0];
        Object[] originalArguments = new Object[arguments.length - 1];
        System.arraycopy(arguments, 1, originalArguments, 0, originalArguments.length);
        if (originalArguments.length > 0 && originalArguments[0] != null) {
            Object rewritten = rewriteLocationResult(originalArguments[0]);
            if (rewritten != null) originalArguments[0] = rewritten;
        }

        try {
            return callable.invoke(receiver, originalArguments);
        } catch (InvocationTargetException exception) {
            Throwable cause = exception.getCause();
            throw cause != null ? cause : exception;
        }
    }

    private static native Object rewriteLocationResult(Object locationResult);
}
