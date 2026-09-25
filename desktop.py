"""Self-contained desktop launcher. The browser retains full speech/accessibility support."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import urllib.request
import webbrowser
from runtime_paths import data_directory
from version import VERSION, APPLICATION, DEFAULT_PORT


def existing(port, data):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(f'http://127.0.0.1:{port}/api/runtime', timeout=.5) as response:
            runtime = json.load(response)
        return runtime.get('application') == APPLICATION and Path(runtime.get('data_directory', '')).resolve() == data.resolve()
    except (OSError, ValueError):
        return False


def create_server(port, data, auto_port=True):
    # Set the location before importing the business application; no user database
    # is opened from the application bundle or a temporary extraction directory.
    os.environ['ZHUYI_V1_DATA'] = str(data)
    import app
    app.DATA = data
    for candidate in range(port, port + (12 if auto_port else 1)):
        if existing(candidate, data):
            return app, None, candidate
        try:
            server = app.ThreadingHTTPServer(('127.0.0.1', candidate), app.Handler)
        except OSError:
            continue
        app.PORT = candidate
        try:
            app.init()
            app.setup_logging()
        except Exception:
            server.server_close()
            raise
        app.work.background = True
        return app, server, candidate
    raise RuntimeError('本机端口已被占用，请关闭旧实例后重试，或使用 --port 指定其他端口。')


def reveal_data(data):
    if sys.platform == 'win32':
        os.startfile(str(data))
    elif sys.platform == 'darwin':
        subprocess.Popen(['open', str(data)])
    else:
        subprocess.Popen(['xdg-open', str(data)])


def desktop_window(app, server, url, data):
    import tkinter as tk
    from tkinter import messagebox, ttk
    root = tk.Tk()
    root.title(f'主一 v{VERSION}')
    root.geometry('430x280')
    root.resizable(False, False)
    root.configure(background='#f4f6f9')
    try:
        logo = tk.PhotoImage(file=str(Path(__file__).resolve().parent / 'dist' / 'logo.png'))
        root.iconphoto(True, logo)
    except tk.TclError:
        pass
    frame = ttk.Frame(root, padding=28)
    frame.pack(fill='both', expand=True)
    ttk.Label(frame, text='主一 · ATTENTION', font=('Helvetica', 20, 'bold')).pack(anchor='w')
    ttk.Label(frame, text='每天读完一份有尽头的材料，\n再留下自己的判断。', padding=(0, 12)).pack(anchor='w')
    ttk.Button(frame, text='打开阅读工作台', command=lambda: webbrowser.open(url)).pack(fill='x', pady=4)
    ttk.Button(frame, text='打开数据文件夹', command=lambda: reveal_data(data)).pack(fill='x', pady=4)

    def close():
        if app.JOB['running'] and not messagebox.askokcancel('正在采集', '退出会中断本次采集，已保存的材料保留。仍要退出吗？', parent=root):
            return
        server.shutdown()
        root.destroy()

    ttk.Button(frame, text='退出主一', command=close).pack(fill='x', pady=4)
    root.protocol('WM_DELETE_WINDOW', close)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    root.after(200, lambda: webbrowser.open(url))
    def watch_server():
        if not worker.is_alive():
            root.destroy()
        else:
            root.after(500, watch_server)
    root.after(500, watch_server)
    root.mainloop()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--headless', action='store_true')
    parser.add_argument('--no-scheduler', action='store_true')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT)
    parser.add_argument('--data-dir', type=Path)
    args = parser.parse_args()
    if not 1 <= args.port <= 65524:
        parser.error('端口须为 1–65524')
    data = (args.data_dir or data_directory()).expanduser().resolve()
    app, server, port = create_server(args.port, data, auto_port=not args.headless)
    url = f'http://127.0.0.1:{port}/'
    if server is None:
        if not args.headless:
            webbrowser.open(url)
        return
    try:
        if not args.no_scheduler:
            threading.Thread(target=app.scheduler, daemon=True).start()
        app.event('desktop_started', port=port)
        if args.headless:
            server.serve_forever()
        else:
            desktop_window(app, server, url, data)
    finally:
        server.server_close()
        app.event('desktop_stopped')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        if '--headless' in sys.argv:
            raise
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror('主一启动失败', str(exc), parent=root)
        root.destroy()
        sys.exit(1)
