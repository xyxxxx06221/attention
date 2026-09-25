#!/usr/bin/env python3
"""Stop only an identified local ATTENTION process on the requested port."""
import argparse
from version import VERSION, APPLICATION, DEFAULT_PORT
import json
import os
from pathlib import Path
import urllib.request

def stop(port=DEFAULT_PORT):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    base = f'http://127.0.0.1:{port}'
    try:
        with opener.open(base + '/api/runtime', timeout=3) as response:
            runtime = json.load(response)
        expected=Path(os.environ.get('ZHUYI_V1_DATA',Path(__file__).resolve().parent/'data')).resolve()
        if runtime.get('application') != APPLICATION or Path(runtime.get('data_directory','')).resolve()!=expected:
            return '该端口不是本地公开版主一，未停止其他服务。'
        request = urllib.request.Request(base + '/api/shutdown', data=b'{}',
                                         headers={'Content-Type': 'application/json'})
        with opener.open(request, timeout=3) as response:
            return json.load(response).get('message', '主一已停止')
    except OSError:
        return '主一后台未运行，或无法连接。'

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=DEFAULT_PORT)
    print(stop(parser.parse_args().port))
