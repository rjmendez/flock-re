// Frida hooks for the Flock camera apps (run against the emulator AVD; see README).
//   frida -U -f com.flocksafety.android.<app> -l frida_hooks.js
//
// Two goals:
//   1. Dump the upload token + per-capture metadata the device sends (ConnectionClient).
//   2. Observe the on-device ML surface to confirm detect/localize-only (no OCR text return).
// SANDBOX ONLY — against your own emulator, pointed at your own mock server.

Java.perform(function () {
  // ---- 1. Upload client: capture what leaves the device ----
  try {
    var CC = Java.use('com.flocksafety.android.common.lib.upload.ConnectionClient');
    // sendHello carries the auth token in its payload.
    CC.sendHello.overload(
      'java.io.DataInputStream', 'java.io.DataOutputStream',
      'com.flocksafety.android.common.lib.model.CoreValues'
    ).implementation = function (inp, out, cv) {
      try { console.log('[HELLO] authToken=', cv.getAuthToken()); } catch (e) {}
      return this.sendHello(inp, out, cv);
    };
    // sendMetadata(inp, out, metadataJson, mediaFilename)
    CC.sendMetadata.overload(
      'java.io.DataInputStream', 'java.io.DataOutputStream', 'java.lang.String', 'java.lang.String'
    ).implementation = function (inp, out, meta, name) {
      console.log('[METADATA]', name, '->', meta);
      return this.sendMetadata(inp, out, meta, name);
    };
    console.log('[+] ConnectionClient hooked');
  } catch (e) { console.log('[-] ConnectionClient not in this process:', e.message); }

  // ---- 2. NativeML: confirm detect/localize only (string returns are model name/version) ----
  try {
    var NM = Java.use('com.flocksafety.android.nativeml.NativeML');
    ['nativeGetModel', 'nativeGetModelVersion', 'nativeGetLabelId'].forEach(function (m) {
      if (NM[m]) {
        NM[m].overloads.forEach(function (ov) {
          ov.implementation = function () {
            var r = ov.apply(this, arguments);
            console.log('[NativeML]', m, '->', r, '(note: no method returns plate TEXT)');
            return r;
          };
        });
      }
    });
    console.log('[+] NativeML hooked');
  } catch (e) { console.log('[-] NativeML not in this process:', e.message); }
});
