Java.perform(function () {
    var CameraSettings = Java.use('com.flocksafety.android.common.lib.CameraSettings');
    CameraSettings.getCoreValuesFromContentProvider.implementation = function (context) {
        console.log('[HOOK] getCoreValuesFromContentProvider() called - bypassing missing ' +
            'ContentResolver.query(Uri,String[],Bundle,CancellationSignal) (API 26+, absent on ' +
            'this API 25 runtime) by returning the app\'s own static defaultCoreValues fallback.');
        var field = CameraSettings.class.getDeclaredField('defaultCoreValues');
        field.setAccessible(true);
        var val = field.get(null);
        console.log('[HOOK] defaultCoreValues = ' + val.toString());
        return val;
    };
    console.log('[HOOK] CameraSettings.getCoreValuesFromContentProvider hooked.');
});
