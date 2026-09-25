"""Check the bundled service, static assets, UTF-8 writes, persistence and shutdown."""
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request


def main():
    executable = Path(sys.argv[1]).resolve()
    with tempfile.TemporaryDirectory(prefix='zhuyi-package-test-') as tmp:
        data = Path(tmp) / 'archive'
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        base = f'http://127.0.0.1:{port}'
        def api(path, body=None):
            request = urllib.request.Request(base + path, data=None if body is None else json.dumps(body).encode(),
                                             headers={'Content-Type': 'application/json'})
            with opener.open(request, timeout=5) as response:
                return json.load(response)
        for attempt in range(2):
            options = {'creationflags': subprocess.CREATE_NO_WINDOW} if sys.platform == 'win32' else {}
            process = subprocess.Popen([str(executable), '--headless', '--no-scheduler', '--port', str(port), '--data-dir', str(data)], **options)
            try:
                for _ in range(120):
                    try:
                        runtime = api('/api/runtime')
                        break
                    except OSError:
                        if process.poll() is not None:
                            raise AssertionError(f'Packaged app exited: {process.returncode}')
                        time.sleep(.25)
                else:
                    raise AssertionError('Packaged app did not start')
                assert runtime['application'] == 'zhuyi-local-v1' and runtime['version'] == '1.0.0'
                assert Path(runtime['data_directory']).resolve() == data.resolve()
                for path in ('/', '/app.js', '/release.js', '/release.css', '/wordmark.png', '/icons.woff2', '/reading-font.woff'):
                    with opener.open(base + path, timeout=10) as response:
                        assert response.status == 200 and len(response.read()) > 0, path
                config = api('/api/source-config')
                assert len(config['sources']) == 6
                dashboard = api('/api/dashboard')
                assert dashboard['articles'] == [] and not dashboard['settings'].get('has_api_key')
                if attempt == 0:
                    api('/api/dossiers', {'name': '打包验证专题'})
                    api('/api/settings', {'secretary_name': '阅文秘书', 'user_title': '阅读者'})
                assert any(f['name'] == '打包验证专题' for f in api('/api/library')['folders'])
                saved = json.loads((data / 'settings.json').read_text(encoding='utf-8'))
                assert saved['secretary_name'] == '阅文秘书' and saved['user_title'] == '阅读者'
                assert api('/api/dashboard')['settings']['secretary_name'] == '阅文秘书'
            finally:
                try:
                    api('/api/shutdown', {})
                except OSError:
                    process.terminate()
                process.wait(timeout=15)
        print('Bundled application: assets, empty archive, UTF-8 writes, restart persistence and shutdown passed.')


if __name__ == '__main__':
    main()
