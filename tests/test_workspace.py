import datetime as dt
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app

class WorkspaceTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.old=app.DATA;app.DATA=Path(self.tmp.name);app.init()
 def tearDown(self):app.DATA=self.old;self.tmp.cleanup()
 def article(self,body=None,precision='minute',day='2026-09-22',suffix='1'):
  return app.store_article('https://www.gov.cn/test'+suffix+'.htm',{'title':'关于完善公共服务的政策意见'+suffix,'body':body or '提高民生服务水平，完善公共服务体系。'*20,'published':day+'T08:00:00+08:00','precision':precision},app.SOURCES[0])
 def messages(self,aid='general',day='2026-09-23',content='**分析**仅为建议。'):
  with app.db() as c:
   for mid,role,text in [('u'+aid,'user','我尚不同意，需要进一步核实。'),('a'+aid,'assistant',content)]:c.execute('INSERT INTO messages VALUES(?,?,?,?,?,?,?)',(mid,role,text,json.dumps([] if aid=='general' else [aid]),'[]',day+'T09:00:00+08:00',aid))
  app.work.response_saved('a'+aid,'reading_summary','专题讨论','测试员')
 def test_legacy_schema_migrates_without_changing_notes(self):
  aid=self.article();app.add_note({'article_id':aid,'text':'原有判断'})
  app.init();app.init()
  with app.db() as c:
   self.assertEqual(c.execute('SELECT count(*) FROM notes').fetchone()[0],1)
   n=c.execute('SELECT * FROM notes').fetchone();self.assertEqual(n['text'],'原有判断');self.assertEqual(n['style'],'highlight')
 def test_note_styles_and_precise_repeated_quote(self):
  body='共同发展。共同发展。'+'政策正文。'*30;aid=self.article(body)
  for style,color in [('highlight','yellow'),('underline','blue'),('strike','purple')]:app.add_note({'article_id':aid,'quote':'共同发展','paragraph':0,'anchor_start':5,'anchor_end':9,'style':style,'color':color})
  notes=app.article_detail(aid)['notes'];self.assertEqual(len(notes),3);self.assertTrue(all(n['anchor_start']==5 for n in notes))
  with self.assertRaises(ValueError):app.add_note({'article_id':aid,'quote':'共同发展','paragraph':0,'anchor_start':1,'anchor_end':5})
  with self.assertRaises(ValueError):app.add_note({'article_id':aid,'text':'x','style':'script'})
 def test_daily_minutes_merge_article_and_office_and_preserve_raw(self):
  aid=self.article();self.messages(aid);self.messages()
  m=app.work.document('minutes','2026-09-23');self.assertEqual(m['message_count'],4);self.assertIn('我尚不同意',m['raw_content'])
  with patch.object(app.work,'llm',return_value='## 一、待核事项\n\n用户尚未认可建议。'):m=app.work.generate_minutes('2026-09-23')
  self.assertEqual(m['mode'],'AI纪要');self.assertIn('我尚不同意',m['raw_content'])
  with patch.object(app.work,'llm',side_effect=ValueError('offline')):
   with self.assertRaises(ValueError):app.work.generate_minutes('2026-09-23')
  self.assertIn('我尚不同意',app.work.document('minutes','2026-09-23')['raw_content'])
  lib=app.work.library();self.assertEqual(lib['counts']['document'],1);self.assertEqual(lib['counts']['conversation'],0)
 def test_late_discussion_does_not_get_overwritten_by_stale_summary(self):
  self.messages()
  def reply(_):
   with app.db() as c:c.execute('INSERT INTO messages VALUES(?,?,?,?,?,?,?)',('late','user','新增议题','[]','[]','2026-09-23T09:01:00+08:00','general'))
   app.work.rebuild_minutes('2026-09-23');return '旧纪要'
  with patch.object(app.work,'llm',side_effect=reply):
   with self.assertRaisesRegex(ValueError,'新增'):app.work.generate_minutes('2026-09-23')
  self.assertIn('新增议题',app.work.document('minutes','2026-09-23')['content'])
 def test_library_and_research_have_separate_search_content(self):
  aid=self.article();app.add_note({'article_id':aid,'text':'独有检索词'})
  self.assertEqual(app.work.library('独有检索词')['items'],[])
  self.assertEqual(len(app.search_records('独有检索词','notes')),1)
  lib=app.work.library('公共服务');self.assertEqual(lib['items'][0]['note_count'],1)
 def test_cancel_style_preserves_written_note_and_restores_mark_only_note(self):
  aid=self.article();app.add_note({'article_id':aid,'quote':'提高民生服务水平','text':'我的判断','style':'underline'})
  app.add_note({'article_id':aid,'quote':'完善公共服务体系','style':'strike'});notes=app.article_detail(aid)['notes'];written=next(n for n in notes if n['text']);mark=next(n for n in notes if not n['text'])
  app.manage_notes({'action':'clear-style','ids':[written['id'],mark['id']]})
  current=app.article_detail(aid)['notes'];self.assertEqual(len(current),1);self.assertEqual(current[0]['style'],'none');self.assertEqual(current[0]['text'],'我的判断')
  self.assertEqual(app.search_records('','notes-trash')[0]['id'],mark['id'])
  app.manage_notes({'action':'restore','ids':[mark['id']]});self.assertEqual(len(app.article_detail(aid)['notes']),2)
 def test_conversation_trash_rebuilds_daily_files_and_restores(self):
  room=app.work.create_conversation('民生议题')['id']
  with app.db() as c:
   c.execute('INSERT INTO messages VALUES(?,?,?,?,?,?,?)',('u-room','user','我的问题','[]','[]','2026-09-23T10:00:00+08:00',room))
   c.execute('INSERT INTO messages VALUES(?,?,?,?,?,?,?)',('a-room','assistant','一条建议','[]','[]','2026-09-23T10:00:01+08:00',room))
  app.work.response_saved('a-room','consultation','民生议题','秘书')
  self.assertEqual(app.work.document('minutes','2026-09-23')['message_count'],2)
  app.work.manage_conversation(room,'trash');self.assertEqual(app.work.conversations(),[])
  self.assertEqual(app.work.conversation_trash()[0]['id'],room)
  self.assertEqual(app.work._day_messages('2026-09-23'),[])
  self.assertFalse(any(r['resource_id']=='daily:2026-09-23' for r in app.work.library()['items']))
  app.work.manage_conversation(room,'restore');self.assertEqual(app.work.document('minutes','2026-09-23')['message_count'],2)
 def test_office_reads_archive_documents_and_research_notes_without_merging_authorship(self):
  aid=self.article();app.add_note({'article_id':aid,'text':'我对民生的判断','style':'none'})
  with app.db() as c:c.execute('INSERT INTO documents VALUES(?,?,?,?,?,?,?,?)',('manual-doc','调研报告','民生专题稿','客观材料：公共服务情况。',None,'2026-09-23','2026-09-23T09:00:00+08:00','[]'))
  app.save_settings({'base_url':'https://example.com/v1','model':'test','api_key':'dummy-test-only'})
  room=app.work.create_conversation('民生')['id'];seen={}
  def answer(messages):seen.update(json.loads(messages[-1]['content']));return '基于材料的答复'
  with patch('app.llm',side_effect=answer):app.chat({'question':'梳理民生相关材料和我的想法','conversation_id':room})
  self.assertTrue(any(n['text']=='我对民生的判断' for a in seen['archive_materials'] for n in a['user_notes']))
  self.assertTrue(any(d['title']=='民生专题稿' for d in seen['archive_documents']))
 def test_folders_are_two_levels_and_proposal_needs_acceptance(self):
  aid=self.article();app.update_article({'id':aid,'action':'archive'});root=app.work.create_folder('测试专题');child=app.work.create_folder('跟进材料',root['id'])
  with self.assertRaises(ValueError):app.work.create_folder('三级',child['id'])
  before=len(app.work.library()['folders'])
  answer=json.dumps({'groups':[{'name':'拟建民生专题','reason':'同一政策','article_ids':[aid,'invented']}]})
  with patch.object(app.work,'llm',return_value=answer):p=app.work.propose_organization()
  self.assertEqual(len(app.work.library()['folders']),before);self.assertEqual(p['groups'][0]['article_ids'],[aid])
  app.work.apply_organization(p['id']);app.work.apply_organization(p['id']);self.assertEqual(len(app.work.library()['folders']),before+1)
 def test_metrics_uses_actual_read_event_and_period_boundaries(self):
  aid=self.article();app.article_detail(aid)
  fixed=dt.datetime(2026,9,23,10,tzinfo=app.TZ)
  with patch.object(app.work,'now',return_value=fixed):app.update_article({'id':aid,'action':'read'});app.update_article({'id':aid,'action':'read'})
  self.assertEqual(app.work.metrics('day','2026-09-23')['reads'],1);self.assertEqual(app.work.metrics('day','2026-09-22')['reads'],0)
  a,b=app.work.period_bounds('quarter','2026-12-31');self.assertEqual(a.date().isoformat(),'2026-10-01');self.assertEqual(b.date().isoformat(),'2027-01-01')
  self.assertEqual(app.work.metrics('week','2026-09-23')['start'],'2026-09-21')
 def test_date_only_accepts_calendar_dates_without_future_minute(self):
  start,end=app.window('2026-09-23')
  self.assertTrue(app.in_edition('2026-09-22T00:00:00+08:00','day',start,end));self.assertTrue(app.in_edition('2026-09-23T00:00:00+08:00','day',start,end))
  self.assertFalse(app.in_edition('2026-09-23T08:00:00+08:00','minute',start,end));self.assertFalse(app.in_edition('2026-09-24T00:00:00+08:00','day',start,end))
 def test_footer_clean_keeps_original_indices_and_meaningful_copyright_text(self):
  body='第一段正文。\n\n人民日报社概况| 关于人民网| 联系我们\n\n会议提出保护版权所有人的合法权益。\n\n信息网络传播视听节目许可证0104065 | 京ICP证000006号'
  paragraphs=app.clean_paragraphs(body);self.assertEqual([p['index'] for p in paragraphs],[0,2]);self.assertIn('版权所有人',paragraphs[1]['text'])
 def test_content_container_excludes_recommendations(self):
  raw='<p>顶部新闻导航。</p><div class="article-content"><p>'+('实际政策正文。'*30)+'</p></div><p>下一篇推荐新闻。</p>'
  body=app.parse_article(raw,'https://www.gov.cn/test.htm')['body'];self.assertNotIn('导航',body);self.assertNotIn('推荐',body);self.assertIn('实际政策',body)
 def test_delete_removes_dependent_documents_and_refreshes_minutes(self):
  aid=self.article();self.messages(aid);self.messages();app.update_article({'id':aid,'action':'delete','confirm':aid})
  self.assertEqual(app.work.library()['counts']['document'],1);self.assertEqual(app.work.document('minutes','2026-09-23')['message_count'],2)
 def test_cached_date_only_reindexed_once(self):
  aid=self.article(precision='day');start,end=app.window('2026-09-23')
  with app.db() as c:
   c.execute('INSERT INTO editions VALUES(?,?,?,?,?,?,?,?)',('2026-09-23',start.isoformat(),end.isoformat(),app.stamp(),'ready','[]','','规则筛选'));c.execute("DELETE FROM metadata WHERE key='date_only_v2'")
  app.init();app.init()
  with app.db() as c:self.assertEqual(c.execute('SELECT count(*) FROM edition_items WHERE article_id=?',(aid,)).fetchone()[0],1)
if __name__=='__main__':unittest.main()
