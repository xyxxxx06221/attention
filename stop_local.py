#!/usr/bin/env python3
"""Stop only an identified local ATTENTION process on the requested port."""
import argparse
import json
import urllib.request

def stop(port=8765):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    base = f'http://127.0.0.1:{port}'
    try:
        with opener.open(base + '/api/runtime', timeout=3) as response:
            runtime = json.load(response)
        if runtime.get('application') != 'attention-local':
            return '该端口不是本地公开版主一，未停止其他服务。'
        request = urllib.request.Request(base + '/api/shutdown', data=b'{}',
                                         headers={'Content-Type': 'application/json'})
        with opener.open(request, timeout=3) as response:
            return json.load(response).get('message', '主一已停止')
    except OSError:
        return '主一后台未运行，或无法连接。'

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765)
    print(stop(parser.parse_args().port))
