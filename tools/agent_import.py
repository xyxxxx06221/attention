#!/usr/bin/env python3
"""Import one verified article using the running local application's API."""
import argparse
import json
from pathlib import Path
import urllib.error
import urllib.request

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file', type=Path, help='UTF-8 JSON article file')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('端口必须在1—65535之间')
    try:
        data = json.loads(args.file.read_text(encoding='utf-8'))
        if not isinstance(data, dict) or not isinstance(data.get('url'), str):
            raise ValueError('JSON对象必须提供url')
        payload = json.dumps(data, ensure_ascii=False).encode('utf-8')
        if len(payload) > 1000000:
            raise ValueError('请求超过1 MB')
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        base = f'http://127.0.0.1:{args.port}'
        with opener.open(base + '/api/runtime', timeout=5) as response:
            if json.load(response).get('application') != 'attention-local':
                raise ValueError('该端口不是本地公开版主一')
        request = urllib.request.Request(base + '/api/import', data=payload,
                                         headers={'Content-Type':'application/json'})
        with opener.open(request, timeout=100) as response:
            print(json.dumps(json.load(response), ensure_ascii=False))
    except urllib.error.HTTPError as exc:
        parser.exit(1, f'导入失败（HTTP {exc.code}）：' + exc.read().decode('utf-8', 'replace') + '\n')
    except (OSError, ValueError) as exc:
        parser.exit(1, str(exc) + '\n')

if __name__ == '__main__':
    main()
