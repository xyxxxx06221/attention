import json
import unittest
from unittest.mock import Mock, patch

import app
from deepseek_search import DeepSeekResearch, ENDPOINT, extract_sources


SETTINGS = {'base_url': 'https://api.deepseek.com/v1', 'model': 'deepseek-flash', 'api_key': 'test-key'}
URL = 'https://www.tongji.edu.cn/biography.htm'


def response():
    return {'model': 'deepseek-flash', 'usage': {'input_tokens': 120, 'output_tokens': 30}, 'content': [
        {'type': 'thinking', 'thinking': 'PRIVATE-THINKING'},
        {'type': 'web_search_tool_result', 'content': [
            {'type': 'web_search_result', 'title': '人物介绍', 'url': URL, 'encrypted_content': 'OPAQUE'},
            {'type': 'web_search_result', 'title': '重复来源', 'url': URL},
            {'type': 'web_search_result', 'title': '无摘录', 'url': 'https://www.cas.cn/other.htm'}]},
        {'type': 'text', 'text': '未经证实的模型自由回答', 'citations': [
            {'url': URL, 'cited_text': '来源中的履历。'},
            {'url': URL, 'cited_text': '来源中的履历。'},
            {'url': URL, 'cited_text': '来源中的任职年份。'},
            {'url': 'https://unknown.example.com/', 'cited_text': '不在搜索结果中的来源。'}]}]}


class DeepSeekSearchTests(unittest.TestCase):
    def test_sources_require_structured_result_and_excerpt(self):
        items = extract_sources(response())
        self.assertEqual(items, [{'title': '人物介绍', 'url': URL, 'type': 'DeepSeek 联网摘录',
                                 'text': '来源中的履历。\n\n来源中的任职年份。'}])
        self.assertNotIn('OPAQUE', str(items))
        self.assertNotIn('PRIVATE-THINKING', str(items))

    def test_native_request_reuses_model_and_auth_and_records_usage(self):
        reply = response()
        request, record, event = Mock(return_value=(json.dumps(reply), ENDPOINT)), Mock(), Mock()
        result = DeepSeekResearch(request, SETTINGS, record, event, '2026-09-24').search('查人物履历', '参考文章')
        args, kwargs = request.call_args
        self.assertEqual(args[0], ENDPOINT)
        self.assertEqual(args[1]['model'], SETTINGS['model'])
        self.assertEqual(args[1]['tools'], [{'type': 'web_search_20250305', 'name': 'web_search', 'max_uses': 5}])
        self.assertIn('参考文章', args[1]['messages'][0]['content'][0]['text'])
        self.assertEqual(args[2]['x-api-key'], SETTINGS['api_key'])
        self.assertTrue(kwargs['ai'])
        record.assert_called_once_with(reply)
        self.assertEqual(result['provider'], 'deepseek')
        self.assertEqual(len(result['items']), 1)
        self.assertNotIn('test-key', str(event.call_args_list))

    def test_missing_excerpts_reads_only_structured_links_without_credentials(self):
        reply = {'content': response()['content'][1:2]}
        def request(url, *args, **kwargs):
            if url == ENDPOINT:
                return json.dumps(reply), ENDPOINT
            self.assertEqual(args, ())
            self.assertEqual(kwargs, {})
            self.assertIn(url, (URL, 'https://www.cas.cn/other.htm'))
            return '网页正文', url
        parse = Mock(return_value={'body': '读取到的网页履历内容。' * 20})
        result = DeepSeekResearch(request, SETTINGS, Mock(), Mock(), parse=parse).search('履历')
        self.assertEqual(len(result['items']), 2)
        self.assertTrue(all(row['type'] == '外部网页正文' for row in result['items']))
        self.assertTrue(all('读取到的' in row['text'] for row in result['items']))

    def test_unreadable_links_do_not_turn_model_prose_into_evidence(self):
        reply = {'content': response()['content'][1:2] + [{'type': 'text', 'text': '我已经找到了完整履历'}]}
        request = Mock(side_effect=lambda url, *args, **kwargs: (json.dumps(reply) if url == ENDPOINT else '无法访问', url))
        service = DeepSeekResearch(request, SETTINGS, Mock(), Mock(), parse=Mock(return_value={'body': '太短'}))
        with self.assertRaisesRegex(ValueError, '原网页暂时无法读取'):
            service.search('履历')

    def test_official_http_search_results_use_registered_source_reader(self):
        urls = ['http://cpc.people.com.cn/n1/2023/0311/bio.html',
                'http://www.news.cn/politics/leaders/bio.htm',
                'http://www.npc.gov.cn/npc/bio.htm',
                'https://www.gov.cn/bio.htm']
        reply = {'content': [{'type': 'web_search_tool_result', 'content': [
            {'type': 'web_search_result', 'title': '官方简历', 'url': url} for url in urls]}]}
        def request(url, *args, **kwargs):
            if url == ENDPOINT:
                return json.dumps(reply), ENDPOINT
            self.assertEqual(args, ())
            self.assertIn(url, urls)
            self.assertEqual(kwargs, {'official': True})
            return '<p>' + '官方履历正文。' * 30 + '</p>', url
        result = DeepSeekResearch(request, SETTINGS, Mock(), Mock(), parse=app.parse_article).search('履历')
        self.assertEqual({r['url'] for r in result['items']}, set(urls))
        self.assertTrue(all(r['type'] == '外部网页正文' for r in result['items']))

    def test_unregistered_http_and_private_official_hosts_still_rejected(self):
        request = Mock(wraps=app.request_url)
        service = DeepSeekResearch(request, SETTINGS, Mock(), Mock(), parse=app.parse_article)
        for url in ('http://people.com.cn.example.com/bio', 'http://unregistered.example.com/bio',
                    'https://127.0.0.1/bio'):
            with self.subTest(url=url):
                self.assertIsNone(service.read_source({'url': url}))
                request.assert_called_with(url)
        # Even a whitelisted hostname cannot resolve or redirect to the local network.
        with patch('app.socket.getaddrinfo', return_value=[(2, 1, 6, '', ('127.0.0.1', 80))]), \
                patch('app.subprocess.run') as transport:
            self.assertIsNone(service.read_source({'url': 'http://www.gov.cn/bio'}))
            request.assert_called_with('http://www.gov.cn/bio', official=True)
            transport.assert_not_called()

    def test_no_tool_or_no_excerpt_is_not_a_success(self):
        cases = [({}, '有效'), ({'content': [{'type': 'text', 'text': '我已经联网找到答案'}]}, '未执行'),
                 ({'content': response()['content'][1:2]}, '没有可引用'),
                 ({'content': [{'type': 'web_search_tool_result', 'content': []}]}, '未找到'),
                 ({'content': [{'type': 'web_search_tool_result', 'content':
                               {'type': 'web_search_tool_result_error', 'error_code': 'unavailable'}}]}, '暂时不可用')]
        for reply, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                extract_sources(reply)

    def test_unsafe_urls_are_not_citations(self):
        for url in ('javascript:alert(1)', 'http://127.0.0.1/a', 'http://10.0.0.1/a',
                    'http://localhost/a', 'https://user:pass@example.com/a'):
            reply = response()
            reply['content'][1]['content'][0]['url'] = url
            reply['content'][1]['content'] = reply['content'][1]['content'][:1]
            reply['content'][2]['citations'] = [{'url': url, 'cited_text': '摘录'}]
            with self.subTest(url=url), self.assertRaises(ValueError):
                extract_sources(reply)

    def test_partial_tool_error_keeps_real_evidence(self):
        reply = response()
        reply['content'].append({'type': 'web_search_tool_result', 'content':
                                 {'type': 'web_search_tool_result_error', 'error_code': 'max_uses_exceeded'}})
        self.assertEqual(len(extract_sources(reply)), 1)

    def test_request_errors_never_echo_key_or_upstream_content(self):
        event = Mock()
        service = DeepSeekResearch(Mock(side_effect=ValueError('test-key private upstream response')),
                                  SETTINGS, Mock(), event)
        with self.assertRaisesRegex(ValueError, '联网请求失败') as error:
            service.search('问题')
        self.assertNotIn('test-key', str(error.exception))
        self.assertNotIn('test-key', str(event.call_args_list))

    def test_usage_is_recorded_even_when_model_does_not_search(self):
        record = Mock()
        service = DeepSeekResearch(Mock(return_value=(json.dumps({'usage': {}, 'content': []}), ENDPOINT)),
                                  SETTINGS, record, Mock())
        with self.assertRaises(ValueError):
            service.search('问题')
        record.assert_called_once()

    def test_official_router_does_not_fall_back_on_native_error(self):
        with patch('app.settings', return_value=SETTINGS), patch('app.DeepSeekResearch') as native, patch('app.Research') as legacy:
            native.return_value.search.side_effect = ValueError('原生搜索失败')
            with self.assertRaisesRegex(ValueError, '原生搜索失败'):
                app.external_search('问题')
            legacy.assert_not_called()

    def test_proxy_credentials_are_not_forwarded_to_official_endpoint(self):
        for base in ('https://api.deepseek.com.example.com', 'https://proxy.example.com/v1',
                     'http://api.deepseek.com', 'https://api.deepseek.com:8443'):
            s = {**SETTINGS, 'base_url': base}
            with self.subTest(base=base), patch('app.settings', return_value=s), \
                    patch('app.DeepSeekResearch') as native, patch('app.Research') as legacy:
                app.external_search('问题')
                native.assert_not_called()
                legacy.return_value.search.assert_called_once()
            request = Mock()
            with self.assertRaises(ValueError):
                DeepSeekResearch(request, s, Mock(), Mock()).search('问题')
            request.assert_not_called()


if __name__ == '__main__':
    unittest.main()
