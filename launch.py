#!/usr/bin/env python3
"""Launch the local edition without any cloud credentials or connections."""
import argparse
from start_local import start

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    try:
        print('主一已启动：' + start(args.port, not args.no_browser))
    except Exception as exc:
        parser.exit(1, str(exc) + '\n')
