import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import app
from source_discovery import candidates, feed_entries


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.old=app.DATA
        app.DATA=Path(self.temp.name)
        app.init()
        self.registry=app.source_registry
        self.source=dict(name='浙江政策',url='https://zj.example.org/list',region='zhejiang',rank=0,format='html')

    def tearDown(self):
        app.DATA=self.old
        self.temp.cleanup()

    def verified(self, source=None):
        source=source or self.source
        result=self.registry.probe(source,lambda s:dict(ok=True,message='fixture',candidates=1,samples=[]))
        return source|{'test_token':result['test_token']}

    def article(self, region='guangdong', day='2026-09-22'):
        aid=app.store_article('https://www.gov.cn/test/'+region+'/'+day+'.htm',dict(title='关于完善公共服务政策的通知',body='公共服务政策材料。'*40,published=day+'T12:00:00+08:00',precision='minute'),app.SOURCES[0])
        with app.db() as c:c.execute('UPDATE articles SET region=?,archived=1 WHERE id=?',(region,aid))
        return aid

    def test_province_requires_matching_fresh_single_use_probe(self):
        with self.assertRaises(ValueError):self.registry.save(self.source,True)
        self.assertNotIn('zhejiang',app.region_limits())
        verified=self.verified()
        with self.assertRaises(ValueError):self.registry.save(verified|{'url':'https://evil.example.org/'},True)
        self.registry.save(verified,True)
        self.assertEqual(app.region_limits()['zhejiang'],10)
        with self.assertRaises(ValueError):self.registry.save(verified)
        self.assertEqual(sum(s['region']=='zhejiang' for s in self.registry.sources()),1)

    def test_expired_and_failed_probes_do_not_enable_save(self):
        verified=self.verified()
        with app.db() as c:c.execute('UPDATE source_probes SET expires=?',(time.time()-1,))
        with self.assertRaises(ValueError):self.registry.save(verified,True)
        report=self.registry.probe(self.source,lambda s:dict(ok=False,message='missing body'))
        self.assertNotIn('test_token',report)
        self.assertNotIn('zhejiang',app.region_limits())

    def test_duplicate_source_rolls_back_province_and_preserves_token(self):
        verified=self.verified(self.source|{'url':app.SOURCES[0]['url']})
        with self.assertRaises(ValueError):self.registry.save(verified,True)
        self.assertNotIn('zhejiang',app.region_limits())
        with app.db() as c:self.assertEqual(c.execute('SELECT count(*) FROM source_probes').fetchone()[0],1)

    def test_remove_province_preserves_archive_and_never_reseeds(self):
        aid=self.article()
        app.add_note(dict(article_id=aid,text='保留批注'))
        self.registry.delete_region('guangdong')
        app.init()
        self.assertNotIn('guangdong',app.region_limits())
        self.assertFalse(any(s['region']=='guangdong' for s in self.registry.sources()))
        self.assertEqual(app.article_detail(aid)['notes'][0]['text'],'保留批注')
        self.assertIn(aid,[r['id'] for r in app.work.library(region='guangdong')['items']])
        self.assertNotIn(aid,[r['id'] for r in app.search_records(mode='tasks')])

    def test_national_fixed_and_last_province_source_guard(self):
        with self.assertRaises(ValueError):self.registry.delete_region('national')
        with self.assertRaises(ValueError):self.registry.delete_source(app.SOURCES[0]['id'])
        created=self.registry.save(self.verified(),True)
        with self.assertRaises(ValueError):self.registry.delete_source(created['id'])

    def test_archive_inclusive_dates_and_historical_region(self):
        first=self.article(day='2026-09-22')
        second=self.article('national',day='2026-09-23')
        self.assertEqual([r['id'] for r in app.work.library(date_from='2026-09-22',date_to='2026-09-22')['items']],[first])
        self.assertEqual([r['id'] for r in app.work.library(region='national')['items']],[second])
        with self.assertRaises(ValueError):app.work.library(date_from='2026-09-23',date_to='2026-09-22')
        with self.assertRaises(ValueError):app.work.library(date_from='invalid')

    def test_generic_sources_filter_navigation_and_external_links(self):
        raw='<a href="/p1">关于完善公共服务的通知</a><a href="https://other.example/a">其他站点的新闻标题</a><a href="/p.pdf">关于公开服务的文件</a><a href="/login">政府网站用户登录</a>'
        self.assertEqual(candidates(self.source,raw),[('https://zj.example.org/p1','关于完善公共服务的通知')])
        rss='<rss><channel><item><title>关于完善公共服务的通知</title><link>https://zj.example.org/article</link><pubDate>Tue, 22 Sep 2026 12:00:00 +0800</pubDate></item></channel></rss>'
        self.assertEqual(feed_entries(rss,self.source['url'])[0]['published'],'2026-09-22T12:00:00+08:00')
        self.assertEqual(len(candidates(self.source,rss)),1)

    def test_real_probe_requires_body_and_date(self):
        listing='<a href="/p1">关于完善公共服务的通知</a>'
        article='<html><head><meta name="PubDate" content="2026-09-22 12:00:00"></head><body><h1>关于完善公共服务的通知</h1><p>'+'公共服务政策材料。'*40+'</p></body></html>'
        def request(url,**kw):return (listing if url.endswith('/list') else article),url
        with patch('app.request_url',side_effect=request):report=app.probe_source(self.source|{'builtin':0,'id':'custom-probe'})
        self.assertTrue(report['ok'],report)
        with patch('app.request_url',return_value=('<a href="/p1">关于完善公共服务的通知</a>',self.source['url'])):report=app.probe_source(self.source|{'builtin':0,'id':'custom-probe'})
        self.assertFalse(report['ok'])

    def test_collection_only_crawler_and_weights_even_with_configured_ai(self):
        created=self.registry.save(self.verified(),True)
        app.save_settings(dict(base_url='https://example.org/v1',model='never-call',api_key='dummy-test-only'))
        source=next(s for s in self.registry.sources() if s['id']==created['id'])
        listing='<a href="/p1">关于完善公共服务政策的通知</a>'
        article='<html><head><meta name="PubDate" content="2026-09-22 12:00:00"></head><body><h1>关于完善公共服务政策的通知</h1><p>'+'公共服务政策材料。'*40+'</p></body></html>'
        def request(url,**kw):return (listing if url==source['url'] else article),url
        with patch('app.active_sources',return_value=[source]),patch('app.request_url',side_effect=request),patch('app.llm',side_effect=AssertionError('model called')) as model:
            app.collect('2026-09-23')
        model.assert_not_called()
        self.assertIsNone(app.JOB['error'])
        data=app.dashboard('2026-09-23')
        self.assertEqual(data['edition']['method'],'爬虫与权重筛选')
        self.assertEqual(data['edition_stats']['zhejiang']['total'],1)
        self.assertEqual(data['articles'][0]['editor'],'规则筛选')

    def test_readded_province_reconnects_old_articles_without_losing_notes(self):
        first=self.registry.save(self.verified(),True)
        source=next(s for s in self.registry.sources() if s['id']==first['id'])
        aid=app.store_article('https://zj.example.org/p1',dict(title='关于完善公共服务政策的通知',body='公共服务材料。'*40,published='2026-09-22T12:00:00+08:00',precision='minute'),source)
        app.add_note(dict(article_id=aid,text='此前笔记'))
        start,end=app.window('2026-09-23')
        with app.db() as c:
            c.execute('INSERT INTO editions VALUES(?,?,?,?,?,?,?,?)',('2026-09-23',start.isoformat(),end.isoformat(),app.stamp(),'ready','[]','','规则筛选'))
            c.execute('INSERT INTO edition_items(day,article_id,parent_id) VALUES(?,?,NULL)',('2026-09-23',aid))
        self.registry.delete_region('zhejiang')
        second=self.registry.save(self.verified(),True)
        with patch('app.request_url',return_value=('',source['url'])),patch('app.llm') as model:app.collect('2026-09-23')
        self.assertIsNone(app.JOB['error'])
        self.assertIn(aid,[a['id'] for a in app.dashboard('2026-09-23')['articles']])
        detail=app.article_detail(aid)
        self.assertEqual(detail['source_id'],second['id'])
        self.assertEqual(detail['notes'][0]['text'],'此前笔记')
        model.assert_not_called()

    def test_collection_start_returns_job_and_rejects_config_lock(self):
        app.JOB['running']=False
        app.COLLECT_LOCK.acquire()
        try:
            with self.assertRaises(ValueError):app.start_collect('2026-09-23')
        finally:app.COLLECT_LOCK.release()
        class InlineThread:
            def __init__(self,target,args,kwargs,**unused):self.run=lambda:target(*args,**kwargs)
            def start(self):self.run()
        with patch('app.threading.Thread',InlineThread),patch('app.active_sources',return_value=[]),patch('app.llm') as model:
            result=app.start_collect('2026-09-23')
        self.assertIsInstance(result,dict)
        self.assertFalse(result['running'])
        self.assertIsNone(result['error'])
        model.assert_not_called()


if __name__=='__main__':unittest.main()
