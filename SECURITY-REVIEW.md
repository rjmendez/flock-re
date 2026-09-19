# SECURITY REVIEW

Date: 2026-09-19  
Scope: Wave 9 attack-surface fan-out (protocol, runtime, model-artifact surfaces)

## Findings

### 1) TLS endpoint verification gap and SSL context misuse
- **Severity:** HIGH
- **Confidence:** 9/10
- **Surface:** Protocol / transport
- **Evidence:** `ConnectionClient.java` socket connect path lacks endpoint identification/hostname verification; `SSLUtil.java` initializes a configured context but returns default context.
- **Risk:** On-path attacker can impersonate backend endpoints and intercept credentials/media with a CA-valid certificate.
- **Recommended remediation:** Return configured SSL context and enforce hostname verification on client connections.

### 2) Exported settings provider exposes credential-bearing values
- **Severity:** HIGH
- **Confidence:** 9/10
- **Surface:** Runtime access control
- **Evidence:** Exported `SettingsContentProvider` protected by weak normal-permission model; provider data includes identity-bearing fields (`serialNumber`, `authToken`, `uploadUrl`).
- **Risk:** Untrusted local app can read identity material and replay/impersonate upload client identity.
- **Recommended remediation:** Make provider non-exported by default; otherwise require `signature` permission and strict caller identity checks.

### 3) Exported database export receiver allows unauthenticated trigger
- **Severity:** HIGH
- **Confidence:** 8/10
- **Surface:** Runtime access control
- **Evidence:** `DatabaseExportReceiver` export path is callable without privileged caller validation.
- **Risk:** Untrusted local app can trigger export of sensitive metadata outside app-private boundary.
- **Recommended remediation:** Restrict receiver to trusted callers (`signature` permission + caller validation) and disable export in production where possible.

### 4) World-writable root daemon control socket
- **Severity:** MEDIUM
- **Confidence:** 8/10
- **Surface:** Protocol / local privilege boundary
- **Evidence:** `reaperd` socket exposed with permissive mode and unauthenticated command framing.
- **Risk:** Local untrusted processes can inject control/heartbeat traffic into root service boundary.
- **Recommended remediation:** Restrict socket permissions and enforce peer credential/domain checks; require authenticated message framing.

### 5) Plaintext auth token logging
- **Severity:** MEDIUM
- **Confidence:** 9/10
- **Surface:** Protocol / operational secrecy
- **Evidence:** Upload client logs include auth token value directly.
- **Risk:** Log readers can replay credentials and impersonate device/session identity.
- **Recommended remediation:** Remove token logging and use redacted/irreversible identifiers.

### 6) Model-artifact review outcome
- **Severity:** LOW
- **Confidence:** 9/10
- **Surface:** Model ingestion/inference
- **Evidence:** Current review found no confirmed exploit primitive in examined model-artifact paths.
- **Risk:** No concrete issue confirmed in this pass.
- **Recommended remediation:** Keep this surface in targeted fuzzing backlog; prioritize runtime/protocol fixes first.

## Priority order
1. Fix transport authentication (TLS verification + SSL context handling)
2. Close credential disclosure sources (settings provider + token logging)
3. Close unauthenticated local export/control surfaces (export receiver + reaperd socket)

## Chaining summary
Top chain is: local-app credential disclosure -> upload identity replay -> transport impersonation/MITM.  
Secondary amplifiers: unauthenticated database export and local root-service control-message injection.
