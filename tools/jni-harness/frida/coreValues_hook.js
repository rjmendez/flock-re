Java.perform(function () {
    var CameraSettings = Java.use("com.flocksafety.android.common.lib.CameraSettings");

    function getDefaultSettings() {
        var candidates = ["defaultSettings", "defaultCoreValues"];
        for (var i = 0; i < candidates.length; i++) {
            try {
                var field = CameraSettings.class.getDeclaredField(candidates[i]);
                field.setAccessible(true);
                var value = field.get(null);
                console.log("[HOOK] " + candidates[i] + " = " + value.toString());
                return value;
            } catch (err) {
                // expected on some builds; keep trying the supported fallback names
            }
        }
        throw new Error("Unable to resolve a default settings object on CameraSettings.");
    }

    function hookCallerWrapper() {
        var methodNames = [
            "getSettingsFromContentProvider",
            "getCoreValuesFromContentProvider",
            "getSettings",
            "getCoreValues"
        ];

        var hookedSignatures = [];
        for (var i = 0; i < methodNames.length; i++) {
            var methodName = methodNames[i];
            if (!CameraSettings[methodName]) {
                continue;
            }

            CameraSettings[methodName].overloads.forEach(function (ov) {
                var argTypes = ov.argumentTypes.map(function (t) { return t.className; });
                var returnType = ov.returnType.className;
                var sig = methodName + "(" + argTypes.join(", ") + ")";

                if (argTypes.length === 0) {
                    ov.implementation = function () {
                        console.log("[HOOK] " + sig + " called - narrow Wave 6 caller-side bypass before API26+ ContentResolver.query(Uri,String[],Bundle,CancellationSignal).");
                        if (returnType === "void") {
                            return;
                        }
                        return getDefaultSettings();
                    };
                    hookedSignatures.push(sig);
                    return;
                }

                if (argTypes.length === 1 && argTypes[0] === "android.content.Context") {
                    ov.implementation = function (context) {
                        console.log("[HOOK] " + sig + " called - narrow Wave 6 caller-side bypass before API26+ ContentResolver.query(Uri,String[],Bundle,CancellationSignal).");
                        if (returnType === "void") {
                            return;
                        }
                        return getDefaultSettings();
                    };
                    hookedSignatures.push(sig);
                }
            });
        }

        if (hookedSignatures.length === 0) {
            throw new Error("Unable to install CameraSettings wrapper hook for getSettingsFromContentProvider/getCoreValues variants.");
        }

        console.log("[HOOK] CameraSettings wrapper hook active for: " + hookedSignatures.join(", "));
    }

    function hookBootstrapperForegroundCompat() {
        var BootstrapperActivity = Java.use("com.flocksafety.android.common.lib.FlockBootstrapperActivity");
        var Intent = Java.use("android.content.Intent");
        var SessionFilterService = Java.use("com.flocksafety.android.objects.SessionFilterService");

        BootstrapperActivity.onStart.implementation = function () {
            console.log("[HOOK] FlockBootstrapperActivity.onStart compatibility hook active - replacing API26 startForegroundService() with startService().");
            this.$super.onStart();

            try {
                var svcIntent = Intent.$new(this, SessionFilterService.class);
                this.startService(svcIntent);
                console.log("[HOOK] startService(SessionFilterService) fallback invoked.");
            } catch (err) {
                console.log("[HOOK] startService fallback failed: " + err);
            }

            try {
                this.finish();
            } catch (err) {
                console.log("[HOOK] finish() call failed: " + err);
            }
        };
    }

    function hookForegroundServiceNotificationCompat() {
        var ForegroundService = Java.use("com.flocksafety.android.common.lib.FlockForegroundService");
        var hooked = false;

        if (ForegroundService.createNotificationChannel) {
            ForegroundService.createNotificationChannel.overloads.forEach(function (ov) {
                if (ov.argumentTypes.length === 0) {
                    ov.implementation = function () {
                        console.log("[HOOK] FlockForegroundService.createNotificationChannel() bypassed for API<26.");
                        return;
                    };
                    hooked = true;
                }
            });
        }

        if (ForegroundService.onCreate) {
            ForegroundService.onCreate.overloads.forEach(function (ov) {
                if (ov.argumentTypes.length === 0) {
                    ov.implementation = function () {
                        console.log("[HOOK] FlockForegroundService.onCreate() compatibility hook active - skipping API26 notification bootstrap.");
                        this.$super.onCreate();
                    };
                    hooked = true;
                }
            });
        }

        if (ForegroundService.onStartCommand) {
            ForegroundService.onStartCommand.overloads.forEach(function (ov) {
                if (ov.argumentTypes.length === 3) {
                    ov.implementation = function (intent, flags, startId) {
                        console.log("[HOOK] FlockForegroundService.onStartCommand(...) bypassed before scheduled-thread startup on API<26.");
                        return 2; // START_NOT_STICKY
                    };
                    hooked = true;
                }
            });
        }

        if (!hooked) {
            console.log("[HOOK] FlockForegroundService compatibility hooks not installed (method signatures unavailable).");
        }
    }

    function hookScheduledForegroundStartCompat() {
        var ScheduledService = Java.use("com.flocksafety.android.common.lib.FlockScheduledForegroundService");
        if (!ScheduledService.start) {
            return;
        }

        ScheduledService.start.overloads.forEach(function (ov) {
            if (ov.argumentTypes.length === 0) {
                ov.implementation = function () {
                    console.log("[HOOK] FlockScheduledForegroundService.start() bypassed to avoid uninitialized thread path on API<26.");
                    return;
                };
            }
        });
    }

    function hookSessionFilterStartCompat() {
        var SessionFilterService = Java.use("com.flocksafety.android.objects.SessionFilterService");
        if (!SessionFilterService.start) {
            return;
        }

        SessionFilterService.start.overloads.forEach(function (ov) {
            if (ov.argumentTypes.length === 0) {
                ov.implementation = function () {
                    console.log("[HOOK] SessionFilterService.start() bypassed to avoid scheduled foreground-thread dependency.");
                    return;
                };
            }
        });
    }

    function hookNativeMlSignals() {
        try {
            var NativeML = Java.use("com.flocksafety.android.nativeml.NativeML");
            ["nativeGetModel", "nativeGetModelVersion", "nativeGetLabelId"].forEach(function (methodName) {
                if (!NativeML[methodName]) {
                    return;
                }
                NativeML[methodName].overloads.forEach(function (ov) {
                    var sig = methodName + "(" + ov.argumentTypes.map(function (t) { return t.className; }).join(", ") + ")";
                    ov.implementation = function () {
                        var result = ov.apply(this, arguments);
                        console.log("[HOOK][NativeML] " + sig + " => " + result);
                        return result;
                    };
                });
            });
            console.log("[HOOK] NativeML signal hooks active.");
        } catch (err) {
            console.log("[HOOK] NativeML class unavailable in current process: " + err);
        }
    }

    hookCallerWrapper();
    hookBootstrapperForegroundCompat();
    hookForegroundServiceNotificationCompat();
    hookScheduledForegroundStartCompat();
    hookSessionFilterStartCompat();
    hookNativeMlSignals();
});
