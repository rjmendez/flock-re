/*
 * hooks.js.NOT_EXECUTED
 *
 * THIS SCRIPT WAS NEVER RUN AGAINST A LIVE PROCESS.
 *
 * It is a prepared Frida hook skeleton for the AVD/ART dynamic-analysis
 * leg of the flock-alpr JNI harness (Component B). That leg is blocked:
 * the flock-object.apk is armeabi-v7a-only and no currently-downloadable
 * Android emulator system image (checked: API 24/25/27/28, x86/x86_64/
 * arm64-v8a) can load armeabi-v7a native code (no libhoudini bundled in
 * any of them; the arm64-v8a images are 64-bit-only builds with no 32-bit
 * personality). `adb install` itself fails with
 * INSTALL_FAILED_NO_MATCHING_ABIS before the app process ever starts, so
 * there is no running flock-object process for Frida to attach to.
 * See ../README.md for the full evidence trail.
 *
 * This file is kept so that if a 32-bit-ARM-capable runtime (a real
 * armeabi-v7a/arm64-v8a-with-32-bit-personality device, or an older image
 * confirmed to still bundle libhoudini) becomes available, the hook logic
 * does not need to be re-derived from scratch. Attach with:
 *   frida -U -l hooks.js -f <package.name.of.flock-object>
 * (package name and the real network-egress method identified from
 * jadx-out were not filled in here because they were not validated
 * against a live process in the current harness run.)
 */

'use strict';

// --- Layer 1: crop -> cloud / phone-home interception -----------------
// TODO (untested): replace with the real class/method identified from
// jadx-out for the network-egress call outside NativeML (see
// re/deep/swarm/phonehome-payload-endpoint/FINDINGS.md for candidates
// already identified via static analysis).
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
// TODO (untested): the real NativeML class name/signatures were captured
// via static analysis in re/deep/native-ml/findings.json and the JNI
// symbol table, but never re-validated live because the class never
// loaded on any bootable image in the current harness run.
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
// Documented but not applied to a live AVD in this run because no AVD
// ever reached a state where the app process (and thus a real egress
// path) existed to isolate. If revisited:
//   adb shell "iptables -I OUTPUT -j DROP; iptables -I OUTPUT -o lo -j ACCEPT"
// (or disable emulator NAT entirely with `-net none` at boot) BEFORE
// installing/launching the app, so an unhooked code path still cannot
// reach a real endpoint even if a Frida hook is missed.
