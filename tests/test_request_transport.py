import json
from pathlib import Path
import shutil
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app


@unittest.skipUnless(shutil.which('curl'), 'System curl is required')
class RequestTransportTests(unittest.TestCase):
    def test_unicode_json_reaches_server_as_utf8(self):
        received = {}

        class Fixture(BaseHTTPRequestHandler):
            def do_POST(self):
                raw = self.rfile.read(int(self.headers['Content-Length']))
                try:
                    received['payload'] = json.loads(raw.decode('utf-8'))
                    received['authorization'] = self.headers.get('Authorization')
                    status = 200
                except (UnicodeDecodeError, ValueError):
                    status = 400
                body = json.dumps({'reply': '\u4e2d\u6587\u6b63\u5e38'}, ensure_ascii=False).encode('utf-8')
                self.send_response(status)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(('127.0.0.1', 0), Fixture)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        payload = {'messages': [{'role': 'user', 'content': '\u8bf7\u56de\u590d \U0001f600 "quoted"\nnext line'}]}
        url = f'http://127.0.0.1:{server.server_port}/chat/completions'
        try:
            raw, final_url = app.request_url(url, payload, {'Authorization': 'Bearer dummy-test-only'}, ai=True)
            self.assertEqual(received['payload'], payload)
            self.assertEqual(received['authorization'], 'Bearer dummy-test-only')
            self.assertEqual(json.loads(raw)['reply'], '\u4e2d\u6587\u6b63\u5e38')
            self.assertEqual(final_url, url)
        finally:
            server.shutdown()
            server.server_close()
            worker.join()
