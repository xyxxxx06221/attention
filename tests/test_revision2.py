import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import app
import editions
from research import Research,query_plan,relevant

class RevisionTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.old=app.DATA;app.DATA=Path(self.temp.name);app.init()
 def tearDown(self):app.DATA=self.old;self.temp.cleanup()
 def article(self,i=0,region='national'):
  aid=app.store_article('https://www.gov.cn/zhengce/test'+str(i)+'.htm',{'title':'公共服务政策 '+str(i),'body':'第一段强调共同发展。'*12+'\n\n'+'第二段讨论民生保障。'*12,'published':'2026-09-22T12:00:00+08:00','precision':'minute'},app.SOURCES[0])
  with app.db() as c:c.execute('UPDATE articles SET region=?,score=? WHERE id=?',(region,100-i%40,aid))
  return aid
 def messages(self,aid,day='2026-09-23',suffix='a'):
  app.work.ensure_conversation(aid,'议事',aid if aid!='general' else None)
  with app.db() as c:
   c.execute('INSERT INTO messages VALUES(?,?,?,?,?,?,?)',('u'+suffix,'user','请分析这项公共服务政策','[]','[]',day+'T10:00:00+08:00',aid));c.execute('INSERT INTO messages VALUES(?,?,?,?,?,?,?)',('a'+suffix,'assistant','## 一、建议\n\n保持独立判断。','[]','[]',day+'T10:00:00+08:00',aid))
  app.work.response_saved('a'+suffix,'consultation','政策研究','办公室')
 def test_finite_edition_no_refill_after_read(self):
  ids=[self.article(i,'national' if i<25 else 'guangdong') for i in range(40)];start,end=app.window('2026-09-23')
  with app.db() as c:
   c.execute('INSERT INTO editions VALUES(?,?,?,?,?,?,?,?)',('2026-09-23',start.isoformat(),end.isoformat(),app.stamp(),'ready','[]','','规则筛选'))
   for aid in ids:c.execute('INSERT INTO edition_items(day,article_id,parent_id) VALUES(?,?,NULL)',('2026-09-23',aid))
   editions.select_edition(c,'2026-09-23')
  d=app.dashboard('2026-09-23');self.assertEqual(len(d['articles']),30);self.assertEqual(d['edition_stats']['national']['total'],20);self.assertEqual(d['edition_stats']['guangdong']['total'],10)
  aid=d['articles'][0]['id'];app.article_detail(aid);app.update_article({'id':aid,'action':'read'});later=app.dashboard('2026-09-23');self.assertEqual(len(later['articles']),29);self.assertEqual(later['total'],30);self.assertNotIn(aid,[a['id'] for a in later['articles']]);self.assertIn(aid,[a['id'] for a in app.search_records()])
 def test_cross_paragraph_marks_are_atomic_and_anchored(self):
  aid=self.article();anchors=[{'paragraph':0,'quote':'第一段','anchor_start':0,'anchor_end':3},{'paragraph':1,'quote':'第二段','anchor_start':0,'anchor_end':3}]
  app.add_note({'article_id':aid,'quote':'第一段\n\n第二段','anchors':anchors,'style':'underline','color':'green'})
  a=app.article_detail(aid);self.assertEqual(json.loads(a['notes'][0]['anchors']),anchors)
  with self.assertRaises(ValueError):app.add_note({'article_id':aid,'quote':'第一段','anchors':anchors+[{'paragraph':99}]})
  self.assertEqual(len(app.article_detail(aid)['notes']),1)
 def test_daily_archive_is_two_files_not_per_turn(self):
  aid=self.article();self.messages(aid,suffix='1');self.messages('general',suffix='2');self.messages(aid,suffix='3')
  r=app.work.library();self.assertEqual(r['counts']['minutes'],1);self.assertEqual(r['counts']['document'],1);self.assertEqual(r['counts']['conversation'],0)
  self.assertEqual(app.work.document('minutes','2026-09-23')['message_count'],6);self.assertEqual(app.work.document('document','daily:2026-09-23')['content'].count('保持独立判断'),3)
 def test_personal_edit_preserves_original_and_detects_conflicts(self):
  aid=self.article();original=app.article_detail(aid)['body'];app.work.edit_document('article',aid,'个人标题','个人修订正文',0)
  self.assertEqual(app.article_detail(aid)['body'],original);self.assertEqual(app.work.document('article',aid)['content'],'个人修订正文')
  with self.assertRaisesRegex(ValueError,'更新'):app.work.edit_document('article',aid,'旧窗口','不能覆盖',0)
  with app.db() as c:self.assertEqual(c.execute('SELECT content FROM document_versions WHERE revision=0').fetchone()[0],original)
 def test_automatic_reports_do_not_overwrite_personal_edit(self):
  self.messages('general',suffix='1');app.work.edit_document('document','daily:2026-09-23','我的研判','我暂时不同意。',0);self.messages('general',suffix='2')
  r=app.work.document('document','daily:2026-09-23');self.assertEqual(r['content'],'我暂时不同意。');self.assertTrue(r['source_updated'])
 def test_bulk_trash_restore_preserves_notes_and_reports(self):
  aid=self.article();app.add_note({'article_id':aid,'text':'不能丢失的判断'});self.messages('general')
  items=[{'kind':'article','id':aid},{'kind':'document','id':'daily:2026-09-23'}];app.work.batch('trash',items)
  self.assertEqual(len(app.work.trash()),2);self.assertFalse(any(r['resource_id']==aid for r in app.work.library()['items']))
  app.work.batch('restore',items);self.assertEqual(app.work.trash(),[]);self.assertEqual(app.article_detail(aid)['notes'][0]['text'],'不能丢失的判断')
 def test_folder_deletion_does_not_delete_or_respawn_files(self):
  aid=self.article();app.update_article({'id':aid,'action':'archive'});f=app.work.library()['folders'][0];app.work.file_resource(f['id'],'article',aid);app.work.manage_folder('delete',f['id']);app.init()
  self.assertNotIn(f['id'],[r['id'] for r in app.work.library()['folders']]);self.assertTrue(app.article_detail(aid)['body'])
 def test_unchecked_web_overrides_search_words_and_keeps_conversation_isolated(self):
  room=app.work.create_conversation('独立议题')['id'];app.save_settings({'base_url':'https://example.com/v1','model':'test','api_key':'dummy-test-only'})
  with patch('app.external_search',return_value={'query':'韩正 简历','items':[],'attempts':[],'error':'测试无来源'}) as search,patch('app.llm',return_value='测试答复'):
   result=app.chat({'question':'请搜索韩正简历','conversation_id':room,'web':False})
  search.assert_not_called();self.assertEqual(result['conversation_id'],room)
  self.assertIn('仅查本地',result['answer'])
  with app.db() as c:self.assertEqual(c.execute('SELECT DISTINCT scope FROM messages').fetchone()[0],room)
 def test_permanent_delete_removes_personal_article_versions(self):
  aid=self.article();app.work.edit_document('article',aid,'个人标题','个人文字',0);app.update_article({'id':aid,'action':'delete','confirm':aid})
  with app.db() as c:
   for table in ('document_edits','document_versions'):
    self.assertEqual(c.execute(f'SELECT count(*) FROM {table} WHERE resource_id=?',(aid,)).fetchone()[0],0)
 def test_latest_analysis_is_object(self):
  aid=self.article();self.messages(aid)
  with app.db() as c:c.execute("UPDATE message_meta SET purpose='reading_summary'")
  self.assertIsInstance(app.article_detail(aid)['latest_analysis'],dict)

class ResearchTests(unittest.TestCase):
 def test_question_normalization_and_irrelevant_results(self):
  p=query_plan('你去搜索一下韩正同志的履历，然后给我');self.assertEqual(p['query'],'韩正 简历');self.assertFalse(relevant(p,'Dog breeds','PDF converter'));self.assertTrue(relevant(p,'中华人民共和国副主席简历','韩正参加工作'))
 def test_context_resolves_generic_article_question(self):
  p=query_plan('请梳理这篇材料有哪些相关报道','关于公共服务改革的意见');self.assertEqual(p['query'],'关于公共服务改革的意见')
 def test_unrelated_results_never_reach_model_context(self):
  service=Research(lambda *a,**k:('',a[0]),app.parse_article,lambda *a,**k:None)
  with patch.object(service,'candidates',return_value=[{'title':'Dog breeds','snippet':'pizza delivery','url':'https://example.com/'}]):r=service.search('宁夏养老金政策')
  self.assertEqual(r['items'],[]);self.assertTrue(r['error'])
 def test_reader_fetches_verified_text_and_skips_private_links(self):
  def request(url,**kwargs):
   if '127.0.0.1' in url:raise ValueError('private address')
   return '<h1>宁夏养老金政策</h1><p>'+('宁夏养老金政策正文。'*20)+'</p>',url
  service=Research(request,app.parse_article,lambda *a,**k:None)
  with patch.object(service,'candidates',return_value=[{'title':'宁夏养老金政策','snippet':'养老金','url':'https://www.nx.gov.cn/a.htm'}]):r=service.search('宁夏养老金政策')
  self.assertEqual(len(r['items']),1);self.assertIn('政策正文',r['items'][0]['text']);self.assertEqual(r['items'][0]['type'],'官方原文')
if __name__=='__main__':unittest.main()
