export const meta = {
  name: 'flock-firmware-peel',
  description: 'Reverse-engineer the Flock ALPR camera firmware dump: install tools, extract partitions, first-pass RE',
  phases: [
    { title: 'Recon & Setup', detail: 'device intel + install binwalk/ghidra/android tools to $HOME', model: 'sonnet' },
    { title: 'Extract', detail: 'unpack boot/system/vendor/oem, qualcomm blobs, secrets, data partitions', model: 'sonnet' },
    { title: 'Analyze', detail: 'first-pass RE of the ALPR application with radare2/ghidra', model: 'opus' },
  ],
}

const BASE = '/home/rjmendez/flock-alpr'
const PARTS = BASE + '/Flock ALPR camera/paritions'
const WORK = BASE + '/re'
const TOOLS = '/home/rjmendez/tools'

const RULES = [
  'Environment: Linux WSL2, user rjmendez, NO sudo/root (sudo needs a password you do not have).',
  'Install everything user-level: pip3 install --user, or download release binaries/zips into ' + TOOLS + '.',
  'The 54 partition images live in "' + PARTS + '" (note the dir is literally spelled "paritions").',
  'These images are a live BitTorrent seed: treat every *.img as strictly READ-ONLY. Never move, rename, delete, truncate or write to them. If a tool needs a mutable copy, copy it into your own output dir first.',
  'This is a Qualcomm Snapdragon Android device dump (Flock Safety ALPR camera) leaked via DDoSecrets. Legitimate security analysis.',
  'Report structured data only. For any secret/credential/PII values, WRITE the raw values to a file inside your own output dir and return only their TYPE + LOCATION (redacted), never the raw value in your return.',
].join('\n')

const SETUP_SCHEMA = {
  type: 'object',
  properties: {
    tools: { type: 'array', items: { type: 'object', properties: {
      name: { type: 'string' }, status: { type: 'string' }, path: { type: 'string' },
      version: { type: 'string' }, invoke: { type: 'string' }, notes: { type: 'string' } },
      required: ['name', 'status'] } },
    ready: { type: 'boolean' }, blockers: { type: 'array', items: { type: 'string' } },
  }, required: ['tools', 'ready'],
}
const RESEARCH_SCHEMA = {
  type: 'object',
  properties: {
    device: { type: 'string' }, soc: { type: 'string' }, os: { type: 'string' },
    summary: { type: 'string' },
    re_targets: { type: 'array', items: { type: 'string' } },
    known_intel: { type: 'array', items: { type: 'string' } },
    sources: { type: 'array', items: { type: 'string' } },
  }, required: ['summary', 're_targets'],
}
const EXTRACT_SCHEMA = {
  type: 'object',
  properties: {
    component: { type: 'string' }, outdir: { type: 'string' },
    formats: { type: 'array', items: { type: 'string' } },
    extracted_ok: { type: 'boolean' },
    key_findings: { type: 'array', items: { type: 'string' } },
    files_of_interest: { type: 'array', items: { type: 'object', properties: {
      path: { type: 'string' }, why: { type: 'string' } }, required: ['path', 'why'] } },
    re_targets: { type: 'array', items: { type: 'string' } },
    notes: { type: 'string' },
  }, required: ['component', 'extracted_ok', 'key_findings'],
}
const ANALYZE_SCHEMA = {
  type: 'object',
  properties: {
    targets_examined: { type: 'array', items: { type: 'string' } },
    arch: { type: 'string' },
    app_identity: { type: 'string' },
    endpoints: { type: 'array', items: { type: 'string' } },
    imports_of_interest: { type: 'array', items: { type: 'string' } },
    strings_of_interest: { type: 'array', items: { type: 'string' } },
    functions_of_interest: { type: 'array', items: { type: 'object', properties: {
      name: { type: 'string' }, why: { type: 'string' } }, required: ['name', 'why'] } },
    secrets_summary: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' },
    next_steps: { type: 'array', items: { type: 'string' } },
  }, required: ['summary', 'targets_examined'],
}

phase('Recon & Setup')
log('Installing toolchain to ' + TOOLS + ' and ~/.local; researching device in parallel')

const [research, setup] = await parallel([
  () => agent(
    'Research the Flock Safety ALPR (automatic license plate reader) camera and this specific firmware leak.\n' +
    RULES + '\n\n' +
    'Establish: the exact device/model, the SoC (partition set includes modem/tz/rpm/aboot/sbl1 + Android system/vendor/oem/boot, so a Qualcomm Snapdragon), the Android/OS base, how the device operates (cellular modem present), and any prior public teardowns or the DDoSecrets "Flock ALPR camera" release context. ' +
    'You may inspect low-risk metadata locally too: run "strings -n 8 ' + PARTS + '/23_devinfo.img" and pull build props from 24_system.img via "strings ' + PARTS + '/24_system.img | grep -iE \'ro.(product|build|hardware).*=\'" to pin model/SoC/Android version. ' +
    'Return the prioritized RE targets among the partitions and concise device intel with sources.',
    { label: 'recon:device-intel', phase: 'Recon & Setup', model: 'sonnet', schema: RESEARCH_SCHEMA }),

  () => agent(
    'Install a firmware-RE toolchain, user-level (NO sudo), so the main agent can drive it afterward.\n' +
    RULES + '\n\n' +
    'Create ' + TOOLS + ' and install/verify each, then report the exact invocation for each:\n' +
    '1. binwalk -> "pip3 install --user binwalk"; verify it runs.\n' +
    '2. Android sparse converter simg2img + img2simg -> try "pip3 install --user simg2img" OR clone anestisb/android-simg2img and "make". Verify against "file ' + PARTS + '/24_system.img" (Android sparse images convert with simg2img).\n' +
    '3. A boot.img unpacker -> download AOSP unpack_bootimg.py from android.googlesource.com mkbootimg into ' + TOOLS + ', OR "pip3 install --user extract-dtb". Verify it parses "' + PARTS + '/21_boot.img".\n' +
    '4. Ghidra -> download the latest release zip from github.com/NationalSecurityAgency/ghidra/releases (JDK 21 is at /usr/bin/java) into ' + TOOLS + ' and unzip. Verify ' + TOOLS + '/ghidra_*/support/analyzeHeadless prints usage. ~400MB; use curl -L with retries.\n' +
    '5. Verify already-present tools: radare2 (~/.local/bin/r2), 7z/7za (else "pip3 install --user py7zr" or fetch static 7zzs), debugfs (e2fsprogs, for no-root read-only ext4 extraction), file, cpio, gzip, lz4.\n\n' +
    'Do installs SEQUENTIALLY to avoid clobbering ~/.local. Report name/status/path/version/invoke per tool. ready=true only if binwalk, an ext4 extractor (debugfs or 7z), a sparse converter, a boot unpacker, and ghidra analyzeHeadless all work. List blockers.',
    { label: 'setup:toolchain', phase: 'Recon & Setup', model: 'sonnet', effort: 'high', schema: SETUP_SCHEMA }),
])

log('Setup ready=' + (setup && setup.ready) + '; device=' + (research && research.device ? research.device : 'see report'))

phase('Extract')
const setupCtx = 'INSTALLED TOOLS (from setup phase):\n' + JSON.stringify(setup && setup.tools ? setup.tools : [], null, 1) +
  '\nDEVICE INTEL:\n' + JSON.stringify(research ? { device: research.device, soc: research.soc, os: research.os } : {}, null, 1)

const EX = (component, outsub, body) => agent(
  RULES + '\n\n' + setupCtx + '\n\n' +
  'YOUR OWNED OUTPUT DIR (create it, write ONLY here): ' + WORK + '/' + outsub + '\n\n' + body +
  '\n\nReturn structured extraction results. re_targets = specific extracted files worth deep RE next.',
  { label: 'extract:' + component, phase: 'Extract', model: 'sonnet', effort: 'high', schema: EXTRACT_SCHEMA })

const extraction = await parallel([
  () => EX('boot-kernel', 'boot',
    'Unpack the boot chain. For 21_boot.img, 22_recovery.img, 50_bootbk.img: split each into kernel + ramdisk + dtb with the boot unpacker. Decompress the ramdisk (gzip/lz4/cpio) and extract it. Save: init*.rc, fstab*, default.prop/prop.default, sepolicy, /sbin binaries. Identify kernel version ("strings kernel | grep -i \'Linux version\'"). Note dm-verity/AVB/secure-boot indicators. Report kernel version, ramdisk init story, mount/verity config.'),

  () => EX('android-fs', 'android-fs',
    'Extract Android userland: 24_system.img (1.5G), 25_vendor.img (384M), 31_oem.img (256M), 27_persist.img (32M). Each is Android sparse OR raw ext4. Per image: "file" it; if sparse run simg2img to raw .ext4 in your dir; then extract WITHOUT mount (no root) via "debugfs -R \'rdump / <dest>\' raw.ext4" or "7z x". ' +
    'Inventory: (a) /system/build.prop + /vendor/build.prop full ro.* props. (b) APKs in /system/app, /system/priv-app, /oem -> package names; FLAG the Flock ALPR app. (c) native libs /system/lib*, /vendor/lib* (ALPR/OCR/camera/net/crypto). (d) custom (non-AOSP) /system/bin + /vendor/bin binaries. (e) init.*.rc services and config/json/xml referencing servers/MQTT/HTTP/cloud/credentials. ' +
    'files_of_interest MUST include the primary ALPR APK path and top custom native binaries/libs. Locate and inventory only; no disassembly here.'),

  () => EX('qualcomm-blobs', 'qualcomm',
    'Triage Qualcomm low-level firmware with binwalk + strings: 01_modem.img (84M NON-HLOS), 08_tz.img (TrustZone/QSEE), 12_dsp.img (16M ADSP), 19_aboot.img (LK), 06_rpm.img, 35_mdtp.img, 37_mcfg.img, 38_lksecapp.img, 44_keymaster.img. ' +
    'Per image: "file", "binwalk" (embedded fs/compression/signatures), "strings -n 8 | grep -iE" for version banners, cert/PKI hints, carrier/APN config (modem/mcfg), URLs/hosts. Run "binwalk -e" to extract embedded filesystems into your dir where feasible. Report baseband/modem version, TZ/QSEE apps, aboot/LK version + secure-boot/unlock strings, and any network/carrier config in the modem partitions.'),

  () => EX('secrets-identity', 'secrets',
    'Hunt device identity, credentials, keys, cloud config. Sources: 27_persist.img (device certs/serials/wifi/DRM), 29_keystore.img, 23_devinfo.img, 30_config.img, 33_mota.img, plus strings-grep of 24_system.img/25_vendor.img/31_oem.img. ' +
    'Extract persist.img (ext4, debugfs/7z no-root) and walk it. Search for: X.509 certs / private keys (BEGIN CERTIFICATE / PRIVATE KEY), .p12/.jks/.keystore, API keys/tokens/bearer secrets, MQTT/AMQP/HTTP endpoints + hostnames, AWS/GCP/Azure IDs, device serial/IMEI/MAC/provisioning IDs, hardcoded passwords, Flock backend URLs. ' +
    'PII/secret handling: write raw values to ' + WORK + '/secrets/RAW_FINDINGS.txt (local only); in your return give ONLY type + file location + redacted token. Never return a full secret. Report counts and locations by category.'),

  () => EX('data-partitions', 'data',
    'Characterize DATA partitions WITHOUT exfiltrating personal content. 53_media.img (18G, COMPLETE) and 54_userdata.img (~29% downloaded, PARTIAL/live — best-effort, expect truncation, do NOT wait). ' +
    'Per image: "file"; if ext4, list top-level tree + directory sizes only (debugfs "ls -l" / 7z l). AGGREGATE stats: file counts by extension, media (jpg/png/h264/mp4) count+size, sqlite .db files and their table names (sqlite3 <db> ".schema" -- schema only), config/log files, app data dirs (/data/data/<flock package>). ' +
    'For userdata, locate the ALPR app data dir + its databases/config/shared_prefs. Do NOT copy out or embed actual captured plate images or personal records -- report structure, schemas, counts, paths only. Note userdata is incomplete.'),
])

const okEx = extraction.filter(Boolean)
log('Extraction complete: ' + okEx.length + '/5 components. Selecting RE targets for deep pass.')

const reTargets = okEx.flatMap(e => (e.re_targets || []).concat((e.files_of_interest || []).map(f => f.path)))

phase('Analyze')
const analysis = await agent(
  RULES + '\n\n' + setupCtx + '\n\n' +
  'Extraction outputs are under ' + WORK + '/ (subdirs: boot, android-fs, qualcomm, secrets, data). ' +
  'Candidate RE targets surfaced by extraction:\n' + JSON.stringify(reTargets, null, 1) + '\n\n' +
  'First-pass reverse-engineering of the core ALPR software:\n' +
  '1. Identify the primary Flock ALPR application: the APK under ' + WORK + '/android-fs (try apktool/apkid if installable, else unzip + read AndroidManifest via aapt/axmldec if present, else strings) AND its native libs (.so in lib/arm64-v8a or /system/lib64).\n' +
  '2. On the top 2-3 native binaries/libs (arm64 ELF doing ALPR/OCR/camera/networking): run radare2 headless -- "r2 -q -c \'aaa; ii; iz~..; afl~..\' <file>" for imports/strings/functions -- and Ghidra analyzeHeadless for a deeper decompile of the single most interesting one (temp project in your dir; import; auto-analyze; export notable decompiled functions). Arch via "file".\n' +
  '3. Extract: network endpoints/URLs, protocol hints (MQTT/gRPC/HTTP/TLS pinning), auth/credential handling, embedded ML model for plate OCR (tflite/onnx/caffe), update mechanism, functions worth deeper study.\n' +
  '4. Cross-reference the secrets phase (endpoints/certs) to sketch how the camera talks to the Flock backend.\n' +
  'Write long disassembly/decompile output to ' + WORK + '/analysis/ and keep the return concise. Give concrete next_steps for a deeper RE session.',
  { label: 'analyze:alpr-app', phase: 'Analyze', model: 'opus', effort: 'high', schema: ANALYZE_SCHEMA })

return {
  device: research,
  setup: setup,
  extraction: okEx,
  analysis: analysis,
  workdir: WORK,
  tools_dir: TOOLS,
}
