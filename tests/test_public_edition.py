import json
import http.client
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from http.server import ThreadingHTTPServer
import app


class PublicEditionTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.old_data, self.old_port = app.DATA, app.PORT
        app.DATA = Path(self.folder.name)
        app.init()

    def tearDown(self):
        app.DATA, app.PORT = self.old_data, self.old_port
        self.folder.cleanup()

    def test_new_install_has_no_data_credentials_or_automatic_calls(self):
        settings = app.settings()
        self.assertFalse(settings['auto_collect'])
        self.assertFalse(settings['api_key'])
        self.assertFalse(settings['base_url'])
        with app.db() as database:
            for table in ('articles', 'notes', 'messages'):
                self.assertEqual(database.execute('SELECT count(*) FROM ' + table).fetchone()[0], 0)

    def test_loopback_model_can_run_without_key_and_sends_no_bearer(self):
        app.save_settings({'base_url':'http://127.0.0.1:1234/v1', 'model':'local-model'})
        response = json.dumps({'choices':[{'message':{'content':'模拟本机模型响应'}}]})
        with patch('app.request_url', return_value=(response, 'unused')) as request:
            self.assertEqual(app.llm([{'role':'user','content':'测试'}]), '模拟本机模型响应')
        self.assertEqual(request.call_args.args[0], 'http://127.0.0.1:1234/v1/chat/completions')
        self.assertEqual(request.call_args.args[2], {})

    def test_remote_model_requires_key_even_on_lookalike_loopback_domain(self):
        for host in ('example.com', 'localhost.example.com', '127.0.0.1.example.com'):
            app.save_settings({'base_url':'https://' + host + '/v1', 'model':'remote-model'})
            with patch('app.request_url') as request:
                with self.assertRaises(ValueError):
                    app.llm([{'role':'user','content':'test'}])
                request.assert_not_called()

    def test_agent_import_is_idempotent_archived_and_preserves_notes(self):
        article = {'url':'https://www.gov.cn/verified-test.htm', 'title':'虚构测试材料',
                   'published':'2026-01-02T10:00:00+08:00', 'body':'本段仅用于自动化测试，不是真实新闻。'*12}
        with patch('app.valid_public_url', return_value=article['url']), patch('app.llm') as model:
            first = app.import_article(article)
            app.add_note({'article_id':first['id'], 'text':'保留的个人批注'})
            second = app.import_article(article | {'body':'不应覆盖旧正文。'*30})
            model.assert_not_called()
        self.assertEqual(first, second)
        with app.db() as database:
            row = database.execute('SELECT body,archived FROM articles').fetchone()
            self.assertEqual(row['body'], article['body'])
            self.assertEqual(row['archived'], 1)
            self.assertEqual(database.execute('SELECT count(*) FROM notes').fetchone()[0], 1)
            self.assertEqual(database.execute('SELECT count(*) FROM editions').fetchone()[0], 0)

    def test_http_origin_host_json_and_key_boundaries(self):
        app.save_settings({'base_url':'https://example.com/v1','model':'test','api_key':'dummy-test-only'})
        server = ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        app.PORT = server.server_port
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        def request(method, path, body=None, headers=None):
            connection = http.client.HTTPConnection('127.0.0.1', app.PORT, timeout=5)
            try:
                connection.request(method, path, body, headers or {})
                response = connection.getresponse()
                return response.status, json.loads(response.read())
            finally:
                connection.close()
        try:
            code, settings = request('GET', '/api/settings')
            self.assertEqual(code, 200)
            self.assertNotIn('api_key', settings)
            self.assertNotIn('dummy-test-only', json.dumps(settings))
            self.assertEqual(request('GET', '/api/runtime')[1]['application'], app.APPLICATION)
            self.assertEqual(request('GET', '/api/runtime', headers={'Host':'evil.example'})[0], 403)
            self.assertEqual(request('POST', '/api/settings', '{}', {'Content-Type':'application/json','Origin':'https://evil.example'})[0], 403)
            self.assertEqual(request('POST', '/api/settings', '{}', {'Content-Type':'text/plain'})[0], 415)
            self.assertEqual(request('POST', '/api/settings', '[]', {'Content-Type':'application/json'})[0], 400)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == '__main__':
    unittest.main()
