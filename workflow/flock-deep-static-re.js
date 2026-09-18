// flock-deep-static-re — reproducible deep static RE of the Flock ALPR firmware.
//
// For independent verification: anyone with the public dump can re-run this and check the
// findings. It fans out 8 read-only subsystem passes (apk-dex, native-ml, boot/secure-world,
// modem, persist/userdata, tflite, ipc/fastrpc, protocol), runs tools locally, and routes the
// review reasoning to a local model. STATIC and OFFLINE by construction: the agent rules forbid
// contacting any live host or using any extracted credential.
//
// Run with the Claude Code Workflow tool. Needs: the extracted dump (see BASE below), the listed
// tools installed, and a local model backend reachable via the `mcp__loci__llm_local` MCP tool.
// Override paths/models via `args`, e.g. {base:"~/flock-alpr", ghidra:".../analyzeHeadless"}.
export const meta = {
  name: 'flock-deep-static-re',
  description: 'Parallel static RE of Flock ALPR firmware structures with local-model adversarial code review; offline only',
  phases: [
    { title: 'Deep dive', detail: '8 subsystems: static analysis of the dump, local-model code review', model: 'sonnet' },
    { title: 'Synthesize', detail: 'rank at-rest exposures and code defects, flag disclosure decisions', model: 'opus' },
  ],
}

// ===== CONFIG — edit for your setup, or pass via the Workflow tool's `args` =====
// BASE holds the extracted dump in this layout:
//   <BASE>/Flock ALPR camera/paritions/   raw partition images (from the public torrent)
//   <BASE>/re/                             extraction output (from flock-firmware-peel.js)
const CFG = (typeof args === 'object' && args) ? args : {}
const BASE = CFG.base || '/PATH/TO/flock-alpr'
const RE = BASE + '/re'
const PARTS = BASE + '/Flock ALPR camera/paritions'
const DEEP = RE + '/deep'
// Ghidra headless launcher (any recent Ghidra; JDK 17+).
const GHIDRA = CFG.ghidra || '/PATH/TO/ghidra/support/analyzeHeadless'
// Local Ollama model tags used for the adversarial review reasoning. Any capable local model
// works; abliterated/uncensored builds (e.g. "Heretic" variants) give franker security critique.
// The published findings were produced with abliterated models — set your own tags here.
const H8 = CFG.fastModel || 'llama3.1:8b'
const H27 = CFG.deepModel || 'qwen2.5:32b'

const RULES = [
  'SCOPE: purely STATIC analysis of an already-public firmware leak (DDoSecrets "Flock ALPR camera"), for defensive security research and disclosure. The ANALYSIS is offline: it reads on-disk artifacts and makes no network calls. HARD RULE: never contact, probe, authenticate to, MITM, or send anything to ANY live Flock Safety infrastructure or any network host; never use extracted credentials/tokens against any endpoint. Reason about exposure as a THREAT MODEL from the artifact alone — do not execute or plan live attacks. (Open-source tools such as jadx or a tflite parser are installed ONCE beforehand; that setup is the only network step and is not part of the analysis run.)',
  'HARD RULE — no PII: never extract, view, decode, or reproduce captured media contents or personal records (plate images, faces, vehicle/person data, GPS coordinates). Characterize STRUCTURE, SCHEMA, and COUNTS only. Any secret value stays redacted.',
  'Target: Flock Safety Falcon ALPR camera, Qualcomm MSM8953 / Android 8.1.0 (security patch frozen 2018-06-05), armeabi-v7a 32-bit userland.',
  'Extracted trees on disk (READ-ONLY): ' + RE + '/{boot,android-fs,qualcomm,secrets,data}. Raw images: "' + PARTS + '" (read-only, live torrent seed — never modify/move).',
  'Prior work to build on (read first, do not redo): ' + RE + '/all_findings.json and ' + RE + '/adversarial/full_pass.json.',
  'Tools: binwalk, r2, ghidra headless (' + GHIDRA + '), simg2img, sqlite3, strings, file. jadx (JDK 17+) must already be installed on PATH or in your tools dir BEFORE this run; the analysis itself makes no network calls.',
  'GRUNT WORK GOES TO LOCAL MODELS. You are a tool-runner and grounding filter, not the analyst. Extract raw material with tools (decompiled code, disassembly, DB schemas, config, strings), then hand it to the LOCAL model via mcp__loci__llm_local for the review reasoning: ' + H8 + ' for volume, escalate your 2-3 highest-severity items to ' + H27 + '. keep_alive="30m", fmt="json" for structured verdicts.',
  'GROUND every model claim against evidence you actually extracted; discard hallucinations (small models invent features). Keep only findings with concrete evidence. Record which model produced each verdict.',
  'Write artifacts to YOUR OWNED DIR: ' + DEEP + '/<your-dimension> (create it, write only there). Secrets/PII: raw to your dir, return only type+location+redacted.',
].join('\n')

const DIM_SCHEMA = {
  type: 'object',
  properties: {
    dimension: { type: 'string' },
    structures_examined: { type: 'array', items: { type: 'string' } },
    findings: { type: 'array', items: { type: 'object', properties: {
      claim: { type: 'string' }, structure: { type: 'string' }, evidence: { type: 'string' },
      severity: { type: 'string', enum: ['low', 'medium', 'high', 'critical'] },
      category: { type: 'string' },
      grounded: { type: 'boolean' }, model_used: { type: 'string' },
    }, required: ['claim', 'severity', 'grounded', 'model_used'] } },
    new_structures_found: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' }, notes: { type: 'string' },
  }, required: ['dimension', 'findings', 'summary'],
}

const SYNTH_SCHEMA = {
  type: 'object',
  properties: {
    top_exposures: { type: 'array', items: { type: 'object', properties: {
      title: { type: 'string' }, severity: { type: 'string' }, dimension: { type: 'string' },
      threat_model: { type: 'string' }, evidence: { type: 'string' } },
      required: ['title', 'severity', 'threat_model'] } },
    code_defects: { type: 'array', items: { type: 'string' } },
    disclosure_items: { type: 'array', items: { type: 'string' } },
    human_decisions: { type: 'array', items: { type: 'string' } },
    coverage_gaps: { type: 'array', items: { type: 'string' } },
    next_probes: { type: 'array', items: { type: 'string' } },
    executive_summary: { type: 'string' },
  }, required: ['top_exposures', 'executive_summary'],
}

const DIMENSIONS = [
  { key: 'apk-dex', task:
    'Decompile the four Flock apps with jadx (install first): flock-object (com.flocksafety.android.objects), flock-phone-home, flock-st-germain, flock-updater (find under ' + RE + '/android-fs — try /oem, /system/app, /system/priv-app). From the DEX, DOCUMENT statically: the OAuth flow shape (grant_type/audience/scope, how the at-rest Auth0 clientSecret is consumed), the /v1/sax + /api/v4 endpoint set and auth-header scheme, and whether TLS certificate pinning is implemented (present/absent, and its config). Hand decompiled code to the local model to review auth/logic quality. This is code reading only — do not exercise any endpoint.' },
  { key: 'native-ml', task:
    'Static Ghidra + r2 on libnativeML.so and libnativeImageUtils.so under ' + RE + '/android-fs. Review the image-ingest path (YUV<->RGB, TFLite tensor fill, FastCV MSER fcvMser*/MSER_NN8 OCR) for MEMORY-SAFETY DEFECTS (bounds, integer overflow, unchecked sizes) an attacker-influenced camera frame could reach. Feed decompiled functions to the local model to identify defects; ground each against the actual disassembly. Static bug-finding in a binary you possess.' },
  { key: 'boot-secure-world', task:
    'Static review of boot integrity + secure world: ' + RE + '/boot (kernel/ramdisk/init/fstab/verity) and Qualcomm trust components in ' + PARTS + ' (19_aboot, 08_tz, 44_keymaster, 38_lksecapp, 29_keystore). Confirm the reported TEST-key signing chain (OEM_ID/DEBUG), AVB/dm-verity status, oem-unlock state in 23_devinfo. Have the local model assess: what does test-key boot + unlocked bootloader imply for someone holding THIS physical device (key-at-rest extraction, integrity gaps) as a threat model, not an attack run.' },
  { key: 'modem-baseband', task:
    'Static analysis of 01_modem.img, 37_mcfg.img, 16_fsg.img in ' + PARTS + ' (binwalk/strings). Pin the exact baseband version (MPSS.TA.2.3.c1) and cross-reference PUBLICLY DOCUMENTED MSM8953 baseband CVEs (informational). Characterize the GNSS diag and eSIM (flock.starsan.get_eid) interfaces and any carrier/APN config present at rest. Local model summarizes the baseband attack-surface class from public CVE knowledge — no live radio interaction.' },
  { key: 'persist-userdata-fs', task:
    'FULL filesystem parse (not strings) of 27_persist.img and 54_userdata.img (simg2img if sparse, then debugfs/7z, no root). Enumerate /persist/flock/auth0/, and hunt specifically for the MEDIA ENCRYPTION KEY public teardowns reported unencrypted at rest (persist, /data/vendor/flock, keystore). Dump every SQLite .db schema (sqlite3 .schema — schema only) and flag tables holding plate/vehicle/location/PII; list shared_prefs. Local model assesses the at-rest exposure blast radius (does the key decrypt stored media? is the secret device-unique or fleet-shared?) as a threat model. Redact raw secret values.' },
  { key: 'tflite-models', task:
    'Parse on-device TFLite models under ' + RE + '/android-fs (assets/flock_models/*.tflite, e.g. MLM-2857-large-fp16.tflite, MLM-2324-nano2) via a pre-installed flatbuffer/tflite parser (flatc or the tflite package, installed beforehand) or by parsing the header directly. Dump architecture/inputs/outputs/labels (confirm the licensePlate class). Local model discusses, DEFENSIVELY: model and IP-extraction exposure, and the robustness limits of the ALPR pipeline — what real-world plate conditions this detector and OCR would miss (understanding evasion to inform defenders and privacy), and data-poisoning risk.' },
  { key: 'ipc-fastrpc-adb', task:
    'Static map of the on-device local IPC/debug surface: FastRPC/UTF (adsprpc) libs in ' + RE + '/android-fs/vendor/lib vs public Snapdragon 6xx FastRPC privesc CVEs, the ADB-over-WiFi property gate, exposed sockets/binder services and their SELinux domains (init*.rc in ' + RE + '/boot, sepolicy in vendor). Local model identifies local privilege-escalation footholds present on the device; ground against the actual init.rc/sepolicy. On-device static analysis only.' },
  { key: 'protocol-map', task:
    'Statically DOCUMENT the backend protocol from flock-st-germain + flock-phone-home (strings + jadx) and the backend hosts referenced at rest (the control-plane and OAuth login hosts, as found in the firmware): the full /api/v4 + /v1/sax endpoint inventory, which token authenticates each, request framing, and TLS-pinning posture. Scope the Datadog EU telemetry — what device/plate/location metadata the code sends. Local model reviews the protocol design for data-minimization and privacy exposure. Documentation of the artifact only — never contact these hosts.' },
]

phase('Deep dive')
log('Dispatching ' + DIMENSIONS.length + ' parallel STATIC deep-dives; review reasoning on the local model tier. Offline only.')

const results = await parallel(DIMENSIONS.map(d => () => agent(
  RULES + '\n\n=== YOUR DIMENSION: ' + d.key + ' ===\n' + d.task +
  '\n\nReturn structured findings; grounded=true only for claims verified against extracted evidence.',
  { label: 'deep:' + d.key, phase: 'Deep dive', model: 'sonnet', effort: 'high', schema: DIM_SCHEMA })))

const ok = results.filter(Boolean)
const allFindings = ok.flatMap(r => (r.findings || []).map(f => ({ ...f, dimension: r.dimension })))
const grounded = allFindings.filter(f => f.grounded)
log('Deep dive done: ' + ok.length + '/' + DIMENSIONS.length + ' dimensions, ' +
    allFindings.length + ' findings, ' + grounded.length + ' grounded')

phase('Synthesize')
const synth = await agent(
  'You are the lead analyst synthesizing a STATIC, OFFLINE adversarial RE of a public Flock ALPR camera firmware leak (defensive research + disclosure). Below are grounded findings from 8 parallel subsystem deep-dives (each dug with tools, reviewed by a local model, then grounded by a Claude filter).\n\n' +
  'GROUNDED FINDINGS (JSON):\n' + JSON.stringify(grounded, null, 1) + '\n\n' +
  'DEEP-DIVE SUMMARIES:\n' + JSON.stringify(ok.map(r => ({ dimension: r.dimension, summary: r.summary, new_structures: r.new_structures_found })), null, 1) + '\n\n' +
  'Produce: (1) top_exposures ranked by severity, deduped, each with a THREAT MODEL (what the exposure means for a holder of the artifact or physical device, not an attack plan against live infra); (2) code_defects (concrete memory-safety or logic defects found in the binaries); (3) disclosure_items — what a responsible-disclosure report to Flock Safety should contain; (4) human_decisions needing a person (disclosure timing and scope, legal and ethical lines, what must NOT be tested on live systems); (5) coverage_gaps and next_probes (static only); (6) a tight executive_summary. Cite dimension and evidence.',
  { label: 'synthesize', phase: 'Synthesize', model: 'opus', effort: 'high', schema: SYNTH_SCHEMA })

return { dimensions: ok, grounded_count: grounded.length, total_findings: allFindings.length, synthesis: synth }
