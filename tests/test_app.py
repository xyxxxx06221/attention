import datetime as dt
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app

class ArchiveTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.old=app.DATA;app.DATA=Path(self.temp.name);app.init()
 def tearDown(self):app.DATA=self.old;self.temp.cleanup()
 def article(self):
  return app.store_article('https://www.gov.cn/zhengce/202609/content_test.htm',{'title':'民生政策测试文件','body':'提高公共服务水平，做好民生保障工作。'*20,'published':'2026-09-22T08:30:00+08:00','precision':'minute'},app.SOURCES[0])
 def test_window_before_and_after_seven(self):
  for hour,expected in [(6,'2026-09-22'),(7,'2026-09-23'),(23,'2026-09-23')]:
   with patch('app.now',return_value=dt.datetime(2026,9,23,hour,0,tzinfo=app.TZ)):
    start,end=app.window();self.assertEqual(end.date().isoformat(),expected);self.assertEqual(end-start,dt.timedelta(days=1));self.assertEqual(end.hour,7)
 def test_government_hyphen_timestamp(self):
  raw='<meta name="firstpublishedtime" content="2026-09-22-21:50:00"><h1>政策发布</h1><p>'+('正文。'*60)+'</p>'
  result=app.parse_article(raw,'https://www.gov.cn/a.htm');self.assertEqual(result['precision'],'minute');self.assertIn('21:50',result['published'])
 def test_visible_time_beats_date_only_metadata(self):
  raw='<meta name="publishdate" content="2026-09-21"><h1>同一标题</h1><span>2026-09-21 15:58:52</span><h1>同一标题</h1><p>'+('正文。'*60)+'</p>'
  result=app.parse_article(raw,'https://www.news.cn/20260921/c.html');self.assertEqual(result['precision'],'minute');self.assertEqual(result['title'],'同一标题');self.assertIn('15:58',result['published'])
 def test_short_original_paragraph_is_preserved(self):
  p=app.parse_article('<h1>测试标题</h1><p>会议还研究了其他事项。</p>','https://www.gov.cn/a.htm');self.assertIn('会议还研究了其他事项。',p['body'])
 def test_people_time_after_long_navigation(self):
  raw='<meta name="publishdate" content="2026-09-22">'+('<a>导航</a>'*250)+'<b id="newstime">2026年09月22日22:02</b>'
  p=app.parse_article(raw,'http://politics.people.com.cn/n1/2026/0922/test.html');self.assertEqual(p['precision'],'minute');self.assertIn('22:02',p['published'])
 def test_date_only_is_not_fabricated_exact_time(self):
  p=app.parse_article('<meta name="publishdate" content="2026-09-21">','https://www.news.cn/a.html');self.assertEqual(p['precision'],'day')
 def test_read_requires_open_then_archives(self):
  aid=self.article()
  with self.assertRaises(ValueError):app.update_article({'id':aid,'action':'read'})
  app.article_detail(aid);app.update_article({'id':aid,'action':'read'});a=app.article_detail(aid);self.assertEqual(a['state'],'read');self.assertEqual(a['archived'],1)
 def test_skip_preserves_notes(self):
  aid=self.article();app.add_note({'article_id':aid,'quote':'提高公共服务水平','text':'测试笔记','kind':'存疑'});app.update_article({'id':aid,'action':'skip'});a=app.article_detail(aid);self.assertEqual(a['state'],'skipped');self.assertEqual(a['notes'][0]['text'],'测试笔记')
 def test_invalid_quote_rejected(self):
  aid=self.article()
  with self.assertRaises(ValueError):app.add_note({'article_id':aid,'quote':'并非原文的一句','text':''})
 def test_hide_restore_and_search(self):
  aid=self.article();app.add_note({'article_id':aid,'text':'特别的记忆','kind':'批注'});self.assertEqual(len(app.search_records('特别的记忆','notes')),1);app.update_article({'id':aid,'action':'hide'});self.assertEqual(app.search_records('特别的记忆','notes'),[]);app.update_article({'id':aid,'action':'restore'});self.assertEqual(len(app.search_records('特别的记忆','notes')),1)
 def test_delete_erases_notes_and_dependent_advice(self):
  aid=self.article();app.add_note({'article_id':aid,'text':'私人的判断','kind':'批注'})
  with app.db() as c:c.execute('INSERT INTO messages VALUES(?,?,?,?,?,?,?)',('m','assistant','旧建议',json.dumps([aid]),'[]',app.stamp(),'general'))
  with self.assertRaises(ValueError):app.update_article({'id':aid,'action':'delete'})
  app.update_article({'id':aid,'action':'delete','confirm':aid})
  with app.db() as c:
   self.assertEqual(c.execute('SELECT count(*) FROM notes').fetchone()[0],0);self.assertEqual(c.execute('SELECT count(*) FROM messages').fetchone()[0],0);self.assertEqual(c.execute('SELECT body FROM articles').fetchone()[0],'')
  self.article()
  with app.db() as c:self.assertEqual(c.execute('SELECT deleted FROM articles').fetchone()[0],1)
 def test_settings_do_not_expose_key(self):
  result=app.save_settings({'base_url':'https://example.com/v1','model':'my-model','api_key':'dummy-test-only'});self.assertNotIn('api_key',result);self.assertTrue(result['has_key']);self.assertNotIn('dummy-test-only',json.dumps(app.dashboard()))
 def test_missing_api_fails_without_fake_answer(self):
  with self.assertRaisesRegex(ValueError,'API'):app.chat({'question':'请总结'})
 def test_private_url_is_blocked(self):
  with self.assertRaises(ValueError):app.valid_public_url('https://127.0.0.1/private')
  with self.assertRaises(ValueError):app.valid_public_url('file:///etc/passwd')
  with self.assertRaises(ValueError):app.valid_public_url('https://example.com/',True)
 def test_event_dedupe_respects_region(self):
  a={'title':'国务院印发关于完善公共服务体系建设的意见','region':'national'};self.assertTrue(app.same_event(a,a));self.assertFalse(app.same_event(a,a|{'region':'guangdong'}))
 def test_timestamp_repair_preserves_notes_and_body(self):
  aid=self.article()
  with app.db() as c:c.execute("UPDATE articles SET precision='day' WHERE id=?",(aid,))
  app.add_note({'article_id':aid,'text':'原有批注'});self.article();a=app.article_detail(aid);self.assertEqual(a['precision'],'minute');self.assertEqual(a['notes'][0]['text'],'原有批注')
 def test_ai_protocol_and_archive_advice(self):
  aid=self.article();app.article_detail(aid);app.update_article({'id':aid,'action':'read'});app.save_settings({'base_url':'https://example.com/v1','api_key':'dummy-test-only','model':'test-model'})
  seen={}
  def fake(url,payload,headers,ai=False):
   seen.update(url=url,payload=payload,headers=headers);return json.dumps({'choices':[{'message':{'content':'这是测试建议，不是用户结论。'}}]}),url
  with patch('app.request_url',side_effect=fake):r=app.chat({'question':'民生相关材料','article_id':aid})
  self.assertEqual(seen['url'],'https://example.com/v1/chat/completions');self.assertEqual(seen['payload']['model'],'test-model');self.assertIn('测试建议',r['answer'])
  with app.db() as c:self.assertEqual(c.execute('SELECT count(*) FROM messages').fetchone()[0],2)
if __name__=='__main__':unittest.main()
