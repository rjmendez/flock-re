// flock-simulated-red-team — layered adversarial assessment of an owned simulation.
//
// This workflow exercises a Flock-like simulated device from internet/control-plane, LAN,
// wireless/radio, optical, accessory/debug, physical/boot/storage, and on-device/IPC layers.
// Each pass uses the Loci swarm for adversarial hypothesis generation, then requires the outer
// agent to ground every retained finding in collected evidence. It never targets vendor systems.
//
// Run with the Claude Code Workflow tool. The caller must provide:
//   {
//     authorization: "I_OWN_THIS_SIMULATION",
//     simulationRoot: "/absolute/path/to/simulation",
//     targets: ["http://127.0.0.1:8787"],
//     artifactsDir: "/absolute/path/to/simulation/red-team-output" // optional
//   }
//
// Public targets are rejected unless allowPublicTargets=true and
// publicTargetAuthorization="I_OWN_EACH_PUBLIC_TARGET" are supplied. Radio work is
// passive/configuration-only: no jamming, rogue base stations, or transmission outside the
// simulation.
export const meta = {
  name: 'flock-simulated-red-team',
  description: 'Authorization-gated, layered red-team workflow for an owned Flock-like simulation using Loci swarm models',
  phases: [
    { title: 'Safety gate', detail: 'validate ownership, target allowlist, and artifact boundaries', model: 'sonnet' },
    { title: 'Layer exercises', detail: '8 parallel evidence-grounded red-team passes using Loci swarm reasoning', model: 'sonnet' },
    { title: 'Attack paths', detail: 'cross-layer chain validation and remediation plan', model: 'opus' },
  ],
}

const CFG = (typeof args === 'object' && args) ? args : {}
const AUTHORIZATION = 'I_OWN_THIS_SIMULATION'
const PUBLIC_AUTHORIZATION = 'I_OWN_EACH_PUBLIC_TARGET'
const SIM_ROOT = CFG.simulationRoot || ''
const TARGETS = Array.isArray(CFG.targets) ? CFG.targets : []
const ARTIFACTS = CFG.artifactsDir || (SIM_ROOT ? SIM_ROOT + '/red-team-artifacts' : '')
const ALLOW_PUBLIC = CFG.allowPublicTargets === true
const FAST_MODEL = CFG.fastModel || 'qwen2.5:3b'
const ESCALATE_MODEL = CFG.escalateModel || 'qwen3.8:latest'
const SYNTH_MODEL = CFG.synthesizeModel || ESCALATE_MODEL

function isPrivateOrLoopback(hostname) {
  const host = hostname.toLowerCase()
  if (host === 'localhost' || host === '::1' || host.endsWith('.localhost')) return true
  if (/^127\./.test(host) || /^10\./.test(host) || /^192\.168\./.test(host)) return true
  const match = host.match(/^172\.(\d{1,3})\./)
  return Boolean(match && Number(match[1]) >= 16 && Number(match[1]) <= 31)
}

function validateTarget(raw) {
  let target
  try {
    target = new URL(raw)
  } catch {
    throw new Error('Every target must be an absolute http(s) URL: ' + raw)
  }
  if (!['http:', 'https:'].includes(target.protocol)) {
    throw new Error('Only http(s) simulation targets are allowed: ' + raw)
  }
  if (/flocksafety|flock-safety|flock\.com/i.test(target.hostname)) {
    throw new Error('Vendor infrastructure is never an allowed target: ' + raw)
  }
  if (!ALLOW_PUBLIC && !isPrivateOrLoopback(target.hostname)) {
    throw new Error('Public target rejected. Use an owned private/loopback simulation or explicitly set allowPublicTargets=true: ' + raw)
  }
  return target.origin
}

phase('Safety gate')

if (CFG.authorization !== AUTHORIZATION) {
  throw new Error('Refusing to run without args.authorization="' + AUTHORIZATION + '"')
}
if (!SIM_ROOT || SIM_ROOT === '/' || !SIM_ROOT.startsWith('/')) {
  throw new Error('args.simulationRoot must be an absolute path to the owned simulation')
}
if (SIM_ROOT.split('/').includes('..')) {
  throw new Error('args.simulationRoot must not contain parent-directory traversal')
}
if (TARGETS.length === 0) {
  throw new Error('args.targets must contain at least one explicitly authorized simulation URL')
}
if (!ARTIFACTS.startsWith('/') || ARTIFACTS.split('/').includes('..')) {
  throw new Error('args.artifactsDir must be an absolute path without parent-directory traversal')
}
const simPrefix = SIM_ROOT.endsWith('/') ? SIM_ROOT : SIM_ROOT + '/'
if (!ARTIFACTS.startsWith(simPrefix)) {
  throw new Error('args.artifactsDir must be inside args.simulationRoot')
}
if (ALLOW_PUBLIC && CFG.publicTargetAuthorization !== PUBLIC_AUTHORIZATION) {
  throw new Error('Public targets require args.publicTargetAuthorization="' + PUBLIC_AUTHORIZATION + '"')
}

const ALLOWED_ORIGINS = [...new Set(TARGETS.map(validateTarget))]
log('Authorized simulation: ' + SIM_ROOT)
log('Allowlisted origins: ' + ALLOWED_ORIGINS.join(', '))
log('Artifacts: ' + ARTIFACTS)

const RULES = [
  'AUTHORIZATION: this run is limited to the caller-owned SIMULATION at ' + SIM_ROOT + '. Network requests may go ONLY to these exact origins: ' + ALLOWED_ORIGINS.join(', ') + '. Treat redirects, discovered hosts, DNS aliases, and third-party services as OUT OF SCOPE.',
  'Never contact Flock Safety or any other real vendor/customer infrastructure. Never use credentials, tokens, keys, hostnames, or personal data from leaked firmware. Use simulation-only credentials supplied inside the simulation.',
  'Do not create persistence, destructive payloads, ransomware, credential theft, denial of service, resource exhaustion, stealth/evasion tooling, or reusable weaponized exploit code. Prefer harmless proof conditions and stop once impact is demonstrated.',
  'RADIO SAFETY: no jamming, deauthentication, rogue base station, IMSI catcher, unauthorized transmission, or interference. Wireless/cellular/Bluetooth work is limited to passive inspection, configuration review, emulation, shielded-lab fixtures, or software simulation.',
  'PRIVACY: use synthetic/public test imagery and synthetic records only. Never inspect, decode, store, or reproduce captured plates, faces, locations, or other personal records.',
  'GROUNDING: Loci swarm output is hypothesis generation, not evidence. Retain a finding only after verifying it against a command result, log, packet capture from the simulation, source/config reference, or reproducible test. Label untested ideas hypothesis.',
  'STOP immediately on any target mismatch, redirect outside the allowlist, unexpected real data, unstable device behavior, loss of isolation, evidence of third-party traffic, or scope uncertainty.',
  'Write only to ' + ARTIFACTS + '/<layer>. Redact secrets from returned summaries. Do not modify firmware/source except disposable simulation fixtures specifically created for the test.',
  'For adversarial reasoning, invoke mcp__loci__swarm_reason with cheap_model="' + FAST_MODEL + '", escalate_model="' + ESCALATE_MODEL + '", synthesize_model="' + SYNTH_MODEL + '", fanout_count=12, and subtasks tailored to your layer. Include only sanitized evidence in the topic.',
].join('\n')

const FINDING_SCHEMA = {
  type: 'object',
  properties: {
    title: { type: 'string' },
    layer: { type: 'string' },
    severity: { type: 'string', enum: ['info', 'low', 'medium', 'high', 'critical'] },
    status: { type: 'string', enum: ['reproduced', 'static-evidence', 'hypothesis', 'not-reproduced'] },
    preconditions: { type: 'array', items: { type: 'string' } },
    evidence: { type: 'array', items: { type: 'string' } },
    impact: { type: 'string' },
    safe_reproduction: { type: 'array', items: { type: 'string' } },
    remediation: { type: 'array', items: { type: 'string' } },
    model_lineage: { type: 'array', items: { type: 'string' } },
  },
  required: ['title', 'layer', 'severity', 'status', 'evidence', 'impact', 'remediation'],
}

const LAYER_SCHEMA = {
  type: 'object',
  properties: {
    layer: { type: 'string' },
    targets_exercised: { type: 'array', items: { type: 'string' } },
    tests_run: { type: 'array', items: { type: 'string' } },
    findings: { type: 'array', items: FINDING_SCHEMA },
    negative_results: { type: 'array', items: { type: 'string' } },
    artifacts: { type: 'array', items: { type: 'string' } },
    stopped_early: { type: 'boolean' },
    stop_reason: { type: 'string' },
    coverage_gaps: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' },
  },
  required: ['layer', 'tests_run', 'findings', 'negative_results', 'artifacts', 'stopped_early', 'coverage_gaps', 'summary'],
}

const SYNTH_SCHEMA = {
  type: 'object',
  properties: {
    attack_paths: { type: 'array', items: { type: 'object', properties: {
      title: { type: 'string' },
      status: { type: 'string', enum: ['demonstrated', 'partially-demonstrated', 'hypothetical'] },
      severity: { type: 'string', enum: ['info', 'low', 'medium', 'high', 'critical'] },
      layers: { type: 'array', items: { type: 'string' } },
      steps: { type: 'array', items: { type: 'string' } },
      evidence: { type: 'array', items: { type: 'string' } },
      broken_by: { type: 'array', items: { type: 'string' } },
    }, required: ['title', 'status', 'severity', 'layers', 'steps', 'evidence', 'broken_by'] } },
    prioritized_remediation: { type: 'array', items: { type: 'object', properties: {
      priority: { type: 'integer' },
      change: { type: 'string' },
      breaks_paths: { type: 'array', items: { type: 'string' } },
      verification: { type: 'string' },
    }, required: ['priority', 'change', 'verification'] } },
    coverage_matrix: { type: 'array', items: { type: 'object', properties: {
      layer: { type: 'string' },
      exercised: { type: 'boolean' },
      reproduced_findings: { type: 'integer' },
      gaps: { type: 'array', items: { type: 'string' } },
    }, required: ['layer', 'exercised', 'reproduced_findings', 'gaps'] } },
    safety_events: { type: 'array', items: { type: 'string' } },
    executive_summary: { type: 'string' },
  },
  required: ['attack_paths', 'prioritized_remediation', 'coverage_matrix', 'safety_events', 'executive_summary'],
}

const LAYERS = [
  { key: 'internet-control-plane', task:
    'Assess the simulated internet/control-plane boundary. Inventory only the allowlisted origins; inspect TLS and HTTP security configuration, authentication/session behavior, authorization boundaries, replay/idempotency, rate limiting with low-volume probes, update/config delivery trust, telemetry minimization, and redirect/SSRF containment. Use synthetic accounts and records. Do not follow redirects outside the allowlist. Prefer contract tests and malformed-but-bounded requests over exploit payloads.' },
  { key: 'lan-installer-wifi', task:
    'Assess the simulated LAN and installer-Wi-Fi boundary. Enumerate services only on allowlisted simulation targets; test service exposure, unauthenticated control routes, origin/host validation, pairing/bootstrap state, network segmentation assumptions, ADB-over-network gates, discovery protocols, and factory/installer defaults. Keep scanning low-rate and bounded. Do not probe neighboring hosts or the ambient LAN.' },
  { key: 'wireless-radio', task:
    'Assess wireless/radio exposure without transmitting outside the simulation. Review Wi-Fi, cellular/eSIM/APN, GNSS, and Bluetooth configuration or emulated interfaces that actually exist. Use passive captures, prerecorded traces, mocks, shielded fixtures, or software emulation to test trust-on-first-use, downgrade/failover, credential rotation, malformed-state handling, and privacy leakage. Explicitly report absent interfaces and prohibit interference techniques.' },
  { key: 'optical-camera-input', task:
    'Assess the optical/camera-input boundary using only synthetic or public-domain imagery presented to the simulation. Test robustness across glare, darkness, blur, occlusion, perspective, reflective materials, repeated frames, malformed image metadata, extreme but bounded dimensions, and adversarial-pattern hypotheses. Measure detector/OCR behavior, pipeline stability, confidence calibration, and safe failure. Do not optimize evasion against deployed systems or use real captured plates.' },
  { key: 'accessory-debug', task:
    'Assess simulated accessory/debug interfaces evidenced by the device design: USB modes, ADB, recovery/fastboot, serial/UART consoles, JTAG test configuration, removable storage, and peripheral update channels. Verify authentication, production disablement, data exposure, command restrictions, and firmware-update validation with read-only queries or disposable fixtures. Do not flash persistent payloads or bypass protections on real hardware.' },
  { key: 'physical-boot-storage', task:
    'Assess the physical, boot, and storage trust boundaries in the disposable simulation. Verify boot-chain policy, rollback controls, recovery trust, factory-reset semantics, secret persistence, media/data encryption key separation, tamper evidence, and offline data exposure using synthetic data. Demonstrate impact with harmless marker files or signature-validation fixtures only; never extract personal records or install persistence.' },
  { key: 'on-device-apps-ipc', task:
    'Assess on-device apps, IPC, local HTTP services, broadcasts, content providers, Binder/AIDL, permissions, SELinux boundaries, debug flags, logging, and privilege transitions in the simulation. Use synthetic unprivileged test apps/clients and bounded inputs. Confirm whether sensitive actions require authorization and whether secrets or records cross boundaries. Stop at proof of access; do not build durable privilege-escalation payloads.' },
  { key: 'supply-chain-operations', task:
    'Assess simulation build, provisioning, update, observability, and recovery operations. Inspect dependency provenance, signing-key separation, secret injection, debug artifacts, SBOM/patch age, log/crash-pack redaction, update rollback, backup/restore, fleet credential scope, and incident-response controls. Use repository/configuration evidence and simulation-only releases; do not query external vendor services.' },
]

phase('Layer exercises')
log('Dispatching ' + LAYERS.length + ' isolated layer exercises against the explicit simulation allowlist.')

const layerResults = await parallel(LAYERS.map(layer => () => agent(
  RULES + '\n\n=== LAYER: ' + layer.key + ' ===\n' + layer.task + '\n\n' +
  'Process: (1) establish what simulation evidence/interfaces exist; (2) collect a minimal sanitized evidence bundle; ' +
  '(3) ask the Loci swarm for competing attack hypotheses and defensive test cases; (4) run only bounded, non-destructive tests inside scope; ' +
  '(5) independently verify every retained claim; (6) record negative results and gaps. A model assertion alone must be status=hypothesis.',
  { label: 'sim-red-team:' + layer.key, phase: 'Layer exercises', model: 'sonnet', effort: 'high', schema: LAYER_SCHEMA })))

const completed = layerResults.filter(Boolean)
const findings = completed.flatMap(result => result.findings || [])
const grounded = findings.filter(finding => ['reproduced', 'static-evidence'].includes(finding.status))
const safetyEvents = completed
  .filter(result => result.stopped_early)
  .map(result => result.layer + ': ' + (result.stop_reason || 'stopped by safety gate'))

log('Layer exercises complete: ' + completed.length + '/' + LAYERS.length +
  ' layers, ' + grounded.length + ' grounded findings, ' + safetyEvents.length + ' safety stops.')

phase('Attack paths')

const synthesis = await agent(
  RULES + '\n\nYou are the lead defensive red-team analyst. Build cross-layer paths only from the sanitized layer results below.\n\n' +
  'LAYER RESULTS:\n' + JSON.stringify(completed, null, 1) + '\n\n' +
  'Requirements: distinguish demonstrated, partially-demonstrated, and hypothetical paths. A demonstrated path may contain only reproduced steps; ' +
  'never turn a hypothesis into fact. Rank remediation by how many severe paths it breaks, then give a focused verification check. Include every requested ' +
  'layer in the coverage matrix, preserve negative results and safety stops, and do not add exploit code or operational instructions against real devices.',
  { label: 'sim-red-team:cross-layer', phase: 'Attack paths', model: 'opus', effort: 'high', schema: SYNTH_SCHEMA })

return {
  authorization: 'validated',
  simulation_root: SIM_ROOT,
  allowed_origins: ALLOWED_ORIGINS,
  artifacts_dir: ARTIFACTS,
  layers: completed,
  grounded_findings: grounded.length,
  safety_events: safetyEvents,
  synthesis,
}
