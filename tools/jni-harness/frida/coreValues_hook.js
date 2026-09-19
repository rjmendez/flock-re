Java.perform(function () {
    var CameraSettings = Java.use("com.flocksafety.android.common.lib.CameraSettings");
    var ApnHelper = Java.use("com.flocksafety.android.common.lib.ApnHelper");

    function getDefaultCoreValues() {
        var field = CameraSettings.class.getDeclaredField("defaultCoreValues");
        field.setAccessible(true);
        var val = field.get(null);
        console.log("[HOOK] defaultCoreValues = " + val.toString());
        return val;
    }

    function hookCameraWrapper() {
        var installed = false;

        CameraSettings.getCoreValues.overloads.forEach(function (ov) {
            var argTypes = ov.argumentTypes.map(function (t) { return t.className; });
            var sig = "getCoreValues(" + argTypes.join(", ") + ")";

            if (argTypes.length === 1 && argTypes[0] === "android.content.Context") {
                ov.implementation = function (context) {
                    console.log("[HOOK] " + sig + " called - short-circuiting CameraSettings wrapper before API26-only ContentResolver.query(Uri,String[],Bundle,CancellationSignal).");
                    return getDefaultCoreValues();
                };
                installed = true;
            }
        });

        if (!installed) {
            throw new Error("Unable to install CameraSettings wrapper hook: getCoreValues(Context) overload not found.");
        }

        console.log("[HOOK] CameraSettings.getCoreValues(Context) wrapper hook active.");
    }

    function hookApnWrapper() {
        var setApnInstalled = false;

        ApnHelper.setApn.overloads.forEach(function (ov) {
            var argTypes = ov.argumentTypes.map(function (t) { return t.className; });
            var sig = "setApn(" + argTypes.join(", ") + ")";

            if (argTypes.length === 1 && argTypes[0] === "java.lang.String") {
                ov.implementation = function (apnName) {
                    console.log("[HOOK] " + sig + " called - bypassing APN wrapper before API26-only ContentResolver.query(Uri,String[],Bundle,CancellationSignal). apnName=" + apnName);
                    return;
                };
                setApnInstalled = true;
            }
        });

        if (!setApnInstalled) {
            throw new Error("Unable to install ApnHelper wrapper hook: setApn(String) overload not found.");
        }

        var preferredMethodName = null;
        if ("setPreferredAPN" in ApnHelper) {
            preferredMethodName = "setPreferredAPN";
        } else if ("setPreferredApn" in ApnHelper) {
            preferredMethodName = "setPreferredApn";
        }

        if (preferredMethodName !== null) {
            ApnHelper[preferredMethodName].overloads.forEach(function (ov) {
                var argTypes = ov.argumentTypes.map(function (t) { return t.className; });
                if (argTypes.length === 1 && argTypes[0] === "int") {
                    ov.implementation = function (id) {
                        console.log("[HOOK] ApnHelper." + preferredMethodName + "(int) bypassed with id=" + id + ".");
                        return false;
                    };
                }
            });

            console.log("[HOOK] ApnHelper." + preferredMethodName + "(int) fallback hook active.");
        }

        console.log("[HOOK] ApnHelper.setApn(String) wrapper hook active.");
    }

    hookCameraWrapper();
    hookApnWrapper();
});
