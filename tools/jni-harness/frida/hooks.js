/*
 * hooks.js.NOT_EXECUTED
 *
 * This file is intentionally left without live binding targets. The repo's
 * currently validated workaround is `tools/jni-harness/frida/coreValues_hook.js`,
 * which wraps `CameraSettings.getCoreValues(Context)` and
 * `ApnHelper.setApn(String)` before the API-26-only `ContentResolver.query(...)`
 * calls that were demoted to app-level short-circuiting in the validated compatibility run.
 *
 * The earlier placeholder class names below (`NetworkClient`, `NativeML`, etc.)
 * are kept only as a template for a future live run. They were never validated
 * against a real process in this dump and are not current runtime names to treat
 * as fact.
 *
 * See `tools/jni-harness/README.md` for the full evidence trail. Attach with:
 *   frida -U -l hooks.js -f <package.name.of.flock-object>
 */

'use strict';

// --- Layer 1: crop -> cloud / phone-home interception -----------------
// Legacy template: if a live process is reached again, replace the placeholder class/method names with the real network-egress call outside NativeML; the dump already identified likely candidates via static analysis.
//
// Java.perform(function () {
//   var NetworkClient = Java.use('com.flock.<package>.<RealClassName>');
//   NetworkClient.<realUploadMethod>.implementation = function () {
//     var args = arguments;
//     console.log('[phone-home] intercepted call, payload logged, NOT sent:');
//     for (var i = 0; i < args.length; i++) {
//       console.log('  arg[' + i + '] = ' + args[i]);
//     }
//     // Return a canned success instead of touching the network.
//     return <canned success value matching the real return type>;
//   };
// });

// --- Layer 2: nativeAddImageAsset / nativeAddAsset / nativeProcessSession
//              / nativeWaitForAnyAsset boundary ------------------------
// Legacy template: if a live process is reached again, re-bind the NativeML signatures captured during static analysis in the dump; they were never re-validated live because the class never loaded on any bootable image in this run context.
//
// Java.perform(function () {
//   var NativeML = Java.use('com.flock.<package>.NativeML');
//   NativeML.nativeAddImageAsset.implementation = function () {
//     console.log('[nativeAddImageAsset] called with: ' + JSON.stringify(arguments));
//     var ret = this.nativeAddImageAsset.apply(this, arguments);
//     console.log('[nativeAddImageAsset] returned: ' + ret);
//     return ret;
//   };
//   NativeML.nativeProcessSession.implementation = function () {
//     var ret = this.nativeProcessSession.apply(this, arguments);
//     console.log('[nativeProcessSession] SessionResults: ' + JSON.stringify(ret));
//     return ret;
//   };
// });

// --- Defense-in-depth network isolation (independent of these hooks) --
// Documented but not applied to a live AVD in that run context because no AVD
// ever reached a state where the app process (and thus a real egress
// path) existed to isolate. If revisited:
//   adb shell "iptables -I OUTPUT -j DROP; iptables -I OUTPUT -o lo -j ACCEPT"
// (or disable emulator NAT entirely with `-net none` at boot) BEFORE
// installing/launching the app, so an unhooked code path still cannot
// reach a real endpoint even if a Frida hook is missed.
