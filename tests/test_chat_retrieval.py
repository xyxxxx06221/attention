import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app
from research import Research


class ChatRetrievalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old_data = app.DATA
        app.DATA = Path(self.temp.name)
        app.init()
        app.save_settings({'base_url': 'http://127.0.0.1:1234/v1', 'model': 'mock'})
        self.article = app.store_article('https://www.gov.cn/test.htm', {
            'title': '公共服务政策', 'body': '公共服务政策本地正文。' * 20,
            'published': '2026-09-23T10:00:00+08:00', 'precision': 'minute',
        }, app.SOURCES[0])
        self.source = {'title': '公共服务政策最新说明', 'url': 'https://www.gov.cn/latest.htm',
                       'text': '联网获取的政策原文。' * 20, 'type': '官方原文'}

    def tearDown(self):
        app.DATA = self.old_data
        self.temp.cleanup()

    def test_local_never_fetches_even_with_search_words_or_attached_url(self):
        for flag in ({}, {'web': False}):
            with self.subTest(flag=flag), patch('app.external_search') as search, \
                    patch('app.request_url') as request, patch('app.llm', return_value='本地政策[资料1]') as model:
                result = app.chat({'question': '请联网搜索公共服务政策', 'article_id': self.article,
                                   'url': self.source['url'], **flag})
                search.assert_not_called()
                request.assert_not_called()
                payload = json.loads(model.call_args.args[0][-1]['content'])
                self.assertEqual(payload['external_materials'], [])
                self.assertEqual(len(payload['archive_materials']), 1)
                self.assertIn('本轮仅查本地数据库', model.call_args.args[0][0]['content'])
                self.assertEqual(result['research']['mode'], 'local')

    def test_checked_web_reads_external_evidence_and_persists_status(self):
        with patch('app.external_search', return_value={
            'query': '公共服务政策', 'items': [self.source], 'attempts': [], 'error': '',
        }) as search, patch('app.llm', return_value='联网政策说明[资料2]') as model:
            result = app.chat({'question': '公共服务政策', 'article_id': self.article, 'web': True})
        search.assert_called_once()
        payload = json.loads(model.call_args.args[0][-1]['content'])
        self.assertEqual(payload['external_materials'][0]['text'], self.source['text'])
        self.assertEqual(result['citations'][0]['url'], self.source['url'])
        self.assertIn('已读取 1 个外部网页', result['answer'])
        with app.db() as c:
            self.assertEqual(c.execute("SELECT content FROM messages WHERE role='assistant'").fetchone()[0], result['answer'])

    def test_web_failure_does_not_silently_answer_from_local_materials(self):
        for outcome in ({'query': '公共服务政策', 'items': [], 'attempts': [], 'error': '搜索入口不可用'},
                        ValueError('搜索连接失败')):
            with self.subTest(outcome=outcome), patch('app.external_search') as search, patch('app.llm') as model:
                if isinstance(outcome, Exception):
                    search.side_effect = outcome
                else:
                    search.return_value = outcome
                result = app.chat({'question': '公共服务政策', 'article_id': self.article, 'web': True})
                model.assert_not_called()
                self.assertIn('联网检索未取得可用资料', result['answer'])
                self.assertEqual(result['citations'], [])
                self.assertEqual(result['research']['status'], 'unavailable')

    def test_native_evidence_is_presented_as_excerpt_with_source_link(self):
        source = {**self.source, 'type': 'DeepSeek 联网摘录'}
        with patch('app.external_search', return_value={
            'query': '公共服务政策', 'provider': 'deepseek', 'items': [source], 'attempts': [], 'error': '',
        }), patch('app.llm', return_value='政策说明[资料2]') as model:
            result = app.chat({'question': '公共服务政策', 'article_id': self.article, 'web': True})
        self.assertIn('DeepSeek 联网检索：取得 1 条来源资料', result['answer'])
        self.assertNotIn('已读取', result['answer'])
        self.assertEqual(result['citations'][0]['url'], source['url'])
        self.assertEqual(result['citations'][0]['type'], 'DeepSeek 联网摘录')
        self.assertIn('摘录不等于已读完整网页', model.call_args.args[0][0]['content'])

    def test_attached_page_can_supply_evidence_when_search_fails(self):
        with patch('app.external_search', side_effect=ValueError('搜索连接失败')), \
                patch('app.request_url', return_value=('<h1>参考政策</h1><p>'+'有效正文。'*30+'</p>', self.source['url'])) as request, \
                patch('app.llm', return_value='参考政策[资料1]'):
            result = app.chat({'question': '参考政策', 'web': True, 'url': self.source['url']})
        request.assert_called_once()
        self.assertEqual(result['external_error'], '')
        self.assertEqual(result['research']['source_count'], 1)

    def test_non_boolean_switch_is_rejected(self):
        for value in ('false', 'true', 1, None):
            with self.subTest(value=value), patch('app.external_search') as search:
                with self.assertRaisesRegex(ValueError, '布尔值'):
                    app.chat({'question': '搜索政策', 'web': value})
                search.assert_not_called()


class SearchFallbackTests(unittest.TestCase):
    def test_search_failure_explains_provider_block(self):
        service = Research(lambda *a, **k: ('', a[0]), app.parse_article, lambda *a, **k: None)
        with patch.object(service, 'candidates', side_effect=ValueError('搜索服务要求人工验证')):
            result = service.search('公共服务政策')
        self.assertIn('搜索服务要求人工验证', result['error'])
        self.assertEqual(result['items'], [])

    def test_academic_biography_accepts_university_and_research_institute(self):
        def request(url, **kwargs):
            return '<h1>汪品先简历</h1><p>'+'汪品先的研究履历。'*20+'</p>', url
        service = Research(request, app.parse_article, lambda *a, **k: None)
        with patch.object(service, 'candidates', return_value=[
            {'title': '汪品先简历', 'snippet': '汪品先履历', 'url': 'https://www.tongji.edu.cn/bio.htm'},
            {'title': '汪品先简历', 'snippet': '汪品先履历', 'url': 'https://www.cas.cn/bio.htm'},
            {'title': '汪品先简历', 'snippet': '汪品先履历', 'url': 'https://www.cas.cn.example.com/bio.htm'},
        ]):
            result = service.search('汪品先同志履历是什么')
        self.assertEqual(len(result['items']), 2)
        self.assertTrue(all(r['type'] == '机构原文' for r in result['items']))

    def test_unreadable_hits_do_not_prevent_bing_fallback(self):
        def request(url, **kwargs):
            if 'broken' in url:
                raise ValueError('模拟网页不可读')
            return '<h1>公共服务政策</h1><p>'+'公共服务政策正文。'*20+'</p>', url

        service = Research(request, app.parse_article, lambda *a, **k: None)
        def candidates(query, provider):
            if provider == 'duckduckgo':
                return [{'title': '公共服务政策', 'snippet': '公共服务政策',
                         'url': f'https://www.gov.cn/broken{i}.htm'} for i in range(3)]
            return [{'title': '公共服务政策', 'snippet': '公共服务政策', 'url': 'https://www.gov.cn/good.htm'}]
        with patch.object(service, 'candidates', side_effect=candidates) as search:
            result = service.search('公共服务政策')
        self.assertEqual(search.call_args_list[-1].args[1], 'bing')
        self.assertEqual(len(result['items']), 1)
        self.assertEqual(result['items'][0]['url'], 'https://www.gov.cn/good.htm')
        self.assertEqual(result['attempts'][0]['status'], 'no_readable_results')


if __name__ == '__main__':
    unittest.main()
