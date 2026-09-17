// flock-deeper-everything — reproducible deeper static RE + cross-link graph spec.
//
// Second-stage companion to flock-deep-static-re, for independent verification. Fans out 7
// read-only passes over the remaining structures (userdata/media crypto reality, remaining apps,
// kernel/drivers, OTA, camera/imaging, oem/dsp/splash) and emits cross-subsystem exposure chains
// plus a firmware-structure node/edge graph spec. STATIC, OFFLINE, and it never extracts or views
// captured media/personal records — the agent rules enforce structure/schema-only.
//
// Run with the Claude Code Workflow tool. Needs the extracted dump (BASE below), the listed tools,
// and a local model via `mcp__loci__llm_local`. Override paths/models via `args`.
export const meta = {
  name: 'flock-deeper-everything',
  description: 'Static RE of remaining Flock firmware structures + cross-link graph spec; offline, journalism-grade, no PII extraction',
  phases: [
    { title: 'Deeper dive', detail: '7 unexplored subsystems: static analysis, local-model review', model: 'sonnet' },
    { title: 'Cross-link', detail: 'exposure chains + firmware-structure graph spec for Loci', model: 'opus' },
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
  'SCOPE: purely STATIC, OFFLINE analysis of an already-public firmware leak, for PUBLIC-INTEREST JOURNALISM (the vendor is documented misrepresenting these devices; the goal is true, grounded, verifiable facts). HARD RULES: (a) never contact/probe/authenticate to/MITM any live host; never use any extracted credential against anything. (b) NEVER extract, view, decode, or reproduce captured media contents or personal records (plate images, vehicle/location/person data) — characterize encryption/structure/schemas/counts ONLY. (c) Do NOT write to the Loci graph/investigation store (loci ladybug); the main session builds that serially. You MAY use Loci READ tools and mcp__loci__llm_local.',
  'Target: Flock Safety Falcon ALPR camera, Qualcomm MSM8953 / Android 8.1.0, armeabi-v7a. Prior work to build on (read first, do not redo): ' + RE + '/all_findings.json, ' + RE + '/adversarial/full_pass.json, and ' + DEEP + '/*/findings.json (8 subsystems already done: apk-dex, native-ml, boot-secure-world, modem-baseband, persist-userdata-fs, tflite-models, ipc-fastrpc-adb, protocol-map). Decompiled app sources are at ' + DEEP + '/apk-dex/jadx-out/.',
  'Extracted trees (READ-ONLY): ' + RE + '/{boot,android-fs,qualcomm,secrets,data}. Raw images: "' + PARTS + '" (read-only seed, never modify/move).',
  'Tools: binwalk, r2, ghidra headless (' + GHIDRA + '), simg2img, sqlite3, jadx (on PATH or in your tools dir), strings, file.',
  'GRUNT WORK GOES TO LOCAL MODELS. You are a tool-runner and grounding filter, not the analyst. Extract with tools, then hand raw material to mcp__loci__llm_local for review reasoning: ' + H8 + ' for volume, escalate 2-3 top items to ' + H27 + '. keep_alive="30m". GROUND every model claim against evidence you extracted; discard hallucinations; record which model produced each verdict.',
  'Write artifacts to YOUR OWNED DIR: ' + DEEP + '/<your-dimension> (create it, write only there). Secrets: raw to your dir (chmod 600), return only type+location+redacted.',
].join('\n')

const DIM_SCHEMA = {
  type: 'object',
  properties: {
    dimension: { type: 'string' },
    structures_examined: { type: 'array', items: { type: 'string' } },
    findings: { type: 'array', items: { type: 'object', properties: {
      claim: { type: 'string' }, structure: { type: 'string' }, evidence: { type: 'string' },
      severity: { type: 'string', enum: ['info', 'low', 'medium', 'high', 'critical'] },
      category: { type: 'string' }, grounded: { type: 'boolean' }, model_used: { type: 'string' },
    }, required: ['claim', 'severity', 'grounded'] } },
    entities: { type: 'array', items: { type: 'string' }, description: 'named structures/components/endpoints/libs for the graph' },
    new_structures_found: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' }, notes: { type: 'string' },
  }, required: ['dimension', 'findings', 'summary'],
}

const SYNTH_SCHEMA = {
  type: 'object',
  properties: {
    exposure_chains: { type: 'array', items: { type: 'object', properties: {
      title: { type: 'string' }, severity: { type: 'string' }, steps: { type: 'array', items: { type: 'string' } },
      dimensions: { type: 'array', items: { type: 'string' } } }, required: ['title', 'steps'] } },
    graph_nodes: { type: 'array', items: { type: 'object', properties: {
      id: { type: 'string' }, type: { type: 'string' }, label: { type: 'string' } }, required: ['id', 'type'] } },
    graph_edges: { type: 'array', items: { type: 'object', properties: {
      src: { type: 'string' }, rel: { type: 'string' }, dst: { type: 'string' } }, required: ['src', 'rel', 'dst'] } },
    new_findings_for_wiki: { type: 'array', items: { type: 'string' } },
    coverage_gaps: { type: 'array', items: { type: 'string' } },
    executive_summary: { type: 'string' },
  }, required: ['graph_nodes', 'graph_edges', 'executive_summary'],
}

const DIMENSIONS = [
  { key: 'userdata-media-crypto', task:
    'Determine the ENCRYPTION REALITY of 53_media.img and 54_userdata.img — statically, without extracting any content. For each: identify the keying (Android FDE `encryptable=footer` for userdata; adoptable-storage/`android_expand` per-volume key for media) from fstab (' + RE + '/boot), vold, and any key material in persist/metadata/keystore. Given the prior finding that the media-encryption routine is a no-op on this device path, establish whether the media volume is effectively protected or is under a plaintext on-device key (i.e. readable by anyone holding the device). Report the STRUCTURE, key-storage location, and a clear yes/no/uncertain on "decryptable by a device holder" with evidence. DO NOT decrypt, mount-and-browse, extract, or view any captured images/records. Schemas/counts/structure only.' },
  { key: 'remaining-apps', task:
    'Decompile with jadx every Flock/OEM app NOT already covered (the prior pass did objects, phone-home, st-germain, updater, sambuca). Cover at least: flock-collins, flock-system-control, flock-peripheral, flock-settings, any flock-validator/starsan, RemoteSimLockService, and enumerate all other flock-*/oem apps in ' + RE + '/android-fs. For each: role, exported components (services/receivers/providers) and their permission gating, hardcoded secrets/keys, endpoints, and inter-app (AIDL/broadcast/provider) links. Hand decompiled manifests+key classes to the local model to flag exposure. Redact secret values.' },
  { key: 'kernel-drivers', task:
    'Static review of the Linux kernel and drivers from ' + RE + '/boot (unpacked boot/recovery) and modules under ' + RE + '/android-fs (/vendor/lib/modules, /system/lib/modules). Pin the kernel version/build date and config; enumerate loadable modules; identify Flock-custom or notable drivers (IR LED, heated battery, camera sensor, power/BQ24650, touch). Cross-reference the kernel era against publicly-documented kernel CVE classes (informational). Local model summarizes the driver attack-surface class. No exploitation.' },
  { key: 'ota-updater', task:
    'Document the OTA update mechanism statically: decompile the updater app (' + DEEP + '/apk-dex/jadx-out or re-jadx) and examine mota/misc/cache partitions and any recovery updater-script/ota_config in ' + RE + '. Determine the OTA package format, how packages are fetched (endpoint documented, never contacted), and CRUCIALLY how updates are VERIFIED (signature scheme) — and what the test-key signing chain (see boot-secure-world) implies for OTA integrity. Local model assesses the update-integrity posture.' },
  { key: 'camera-imaging', task:
    'Map the camera/imaging capture path statically: the QCamera HAL and libs (libmmcamera*, sensor drivers) in ' + RE + '/android-fs/vendor, the ISP/tuning config, and the IR-LED/exposure/night-capture control (GPIO/PWM). Explain HOW the device physically captures plates day and night, and where the capture handoff to the ALPR pipeline occurs. Local model reviews for capture-path issues. Structural documentation for the wiki.' },
  { key: 'oem-dsp-splash', task:
    'Examine the less-explored partitions: 31_oem.img (256 MiB — do a full extraction and inventory, prior passes only grepped it narrowly), 12_dsp.img (ADSP firmware — is the compute-vision/SCVE offload used by ALPR?), and 18_splash.img (branding). binwalk/simg2img/strings as needed. Report OEM provisioning/config/apps present in oem, the DSP role, and any Flock-specific data or config. Local model summarizes. Redact any secrets.' },
  { key: 'cross-links', task:
    'Build the CROSS-REFERENCE across ALL findings (read ' + RE + '/all_findings.json, ' + RE + '/adversarial/full_pass.json, and every ' + DEEP + '/*/findings.json). Produce: (a) a normalized entity list (partitions, apps, native libs, endpoints, keys/credentials, CVEs, findings) with stable ids; (b) relations between them (app USES lib, finding AFFECTS partition, endpoint AUTHED_BY credential, chain CVE ENABLES finding, etc.); (c) end-to-end EXPOSURE CHAINS that combine findings across subsystems (e.g. physical-access -> unlocked boot -> on-device key -> media readable). This feeds a Loci graph the main session will build. Output as structured nodes/edges/chains. No new tool runs needed beyond reading the finding files; use the local model to help cluster/relate.' },
]

phase('Deeper dive')
log('Dispatching ' + DIMENSIONS.length + ' STATIC deeper dives (journalism-grade, offline, no PII extraction). Loci writes reserved for the main session.')

const results = await parallel(DIMENSIONS.map(d => () => agent(
  RULES + '\n\n=== YOUR DIMENSION: ' + d.key + ' ===\n' + d.task +
  '\n\nReturn structured findings; grounded=true only for claims verified against extracted evidence. Populate entities for the graph.',
  { label: 'deep2:' + d.key, phase: 'Deeper dive', model: 'sonnet', effort: 'high', schema: DIM_SCHEMA })))

const ok = results.filter(Boolean)
const allFindings = ok.flatMap(r => (r.findings || []).map(f => ({ ...f, dimension: r.dimension })))
const grounded = allFindings.filter(f => f.grounded)
log('Deeper dive done: ' + ok.length + '/' + DIMENSIONS.length + ' dims, ' + grounded.length + ' grounded findings')

phase('Cross-link')
const synth = await agent(
  'You are the lead analyst producing (1) cross-subsystem exposure chains and (2) a firmware-structure GRAPH SPEC from a static, offline, journalism-grade RE of a public Flock ALPR firmware leak. Below are grounded findings + entities from the deeper dives.\n\n' +
  'GROUNDED FINDINGS (JSON):\n' + JSON.stringify(grounded, null, 1) + '\n\n' +
  'ENTITIES BY DIMENSION (JSON):\n' + JSON.stringify(ok.map(r => ({ dimension: r.dimension, entities: r.entities, summary: r.summary })), null, 1) + '\n\n' +
  'Produce: (1) exposure_chains combining findings across subsystems, each with ordered steps and the dimensions involved; (2) graph_nodes — a normalized node list (id, type in {partition,app,lib,endpoint,credential,cve,finding,subsystem}, label) covering both these findings and the prior 8 subsystems; (3) graph_edges — typed relations (rel in {uses,contains,authed_by,affects,enables,exposes,stores,talks_to}) linking the nodes into the firmware structure; (4) new_findings_for_wiki — one-line facts to fold into the wiki; (5) coverage_gaps; (6) executive_summary. Keep ids short and stable (e.g. app:phone-home, part:media, lib:nativeimageutils, ep:device-mgmt, cred:fleet-api-key, cve:nas-bypass). This graph is for public documentation — no secret values in labels.',
  { label: 'cross-link-graph', phase: 'Cross-link', model: 'opus', effort: 'high', schema: SYNTH_SCHEMA })

return { dimensions: ok, grounded_count: grounded.length, synthesis: synth }
