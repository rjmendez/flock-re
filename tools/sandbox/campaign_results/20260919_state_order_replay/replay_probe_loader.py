import importlib.util, json, sys, types
spec = importlib.util.spec_from_file_location('upload_client_mod', r'\\wsl$\Ubuntu\home\rjmendez\development\flock-re\tools\sandbox\upload_client.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
port = int(sys.argv[1]) if len(sys.argv) > 1 else 18082
results = {'label': 'replay_rejection_probe', 'cases': []}
for idx in range(2):
    args = types.SimpleNamespace(host='127.0.0.1', port=port, token='SANDBOX-FAKE-TOKEN', size=4096, chunk=2800, plaintext=True)
    try:
        mod.normal_upload(args)
        results['cases'].append({'case': f'valid_upload_connection_{idx+1}', 'result': 'accepted'})
    except Exception as e:
        results['cases'].append({'case': f'valid_upload_connection_{idx+1}', 'result': 'failed', 'error': f'{type(e).__name__}: {e}'})
print(json.dumps(results, indent=2))
