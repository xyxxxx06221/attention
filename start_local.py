#!/usr/bin/env python3
"""Start Yuewen independently of a terminal/Codex, then open its local browser UI."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
import webbrowser
ROOT=Path(__file__).resolve().parent

def running(port):
    try:
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(f'http://127.0.0.1:{port}/api/runtime',timeout=1) as r:
            return json.load(r).get('application') == 'attention-local'
    except Exception:return False

def start(port=8765,open_browser=True):
    if not running(port):
        data=Path(os.environ.get('YUEWEN_DATA',ROOT/'data'));data.mkdir(exist_ok=True,parents=True)
        fd=os.open(data/'startup.log',os.O_CREAT|os.O_WRONLY|os.O_APPEND,0o600)
        with os.fdopen(fd,'ab') as log:
            kwargs={'cwd':str(ROOT),'stdin':subprocess.DEVNULL,'stdout':log,'stderr':log,'close_fds':True}
            if os.name=='nt':kwargs['creationflags']=subprocess.DETACHED_PROCESS|subprocess.CREATE_NEW_PROCESS_GROUP
            else:kwargs['start_new_session']=True
            subprocess.Popen([sys.executable,str(ROOT/'app.py'),'--port',str(port)],**kwargs)
        deadline=time.monotonic()+12
        while time.monotonic()<deadline:
            if running(port):break
            time.sleep(.25)
        else:raise RuntimeError('主一启动未完成，请查看 data/startup.log；端口也可能被其他程序占用。')
    if open_browser:webbrowser.open(f'http://127.0.0.1:{port}/')
    return f'http://127.0.0.1:{port}/'

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8765);parser.add_argument('--no-browser',action='store_true');args=parser.parse_args()
    try:print('主一后台已运行：'+start(args.port,not args.no_browser))
    except Exception as exc:print(str(exc),file=sys.stderr);sys.exit(1)
