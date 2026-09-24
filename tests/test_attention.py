import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
import app
import billing
from relevance import relevance_score, used_citations

class AttentionTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.old=app.DATA;app.DATA=Path(self.tmp.name);app.init()
 def tearDown(self):app.DATA=self.old;self.tmp.cleanup()
 def test_usage_is_account_scoped_and_marks_missing_measurements(self):
  s={'base_url':'https://api.deepseek.com','api_key':'test','model':'test'}
  billing.record(app.db,s,{'usage':{'prompt_tokens':100,'completion_tokens':30,'prompt_cache_hit_tokens':40}},'2026-09-23T10:00:00+08:00')
  billing.record(app.db,s,{},'2026-09-23T10:01:00+08:00')
  billing.record(app.db,{**s,'api_key':'other'},{'usage':{'total_tokens':9999}},'2026-09-23T10:00:00+08:00')
  d=billing.summary(app.db,s,dt.datetime(2026,9,23))['usage']['today'];self.assertEqual((d['calls'],d['measured_calls'],d['total_tokens'],d['cached_tokens']),(2,1,130,40))
 def test_balance_caches_and_failure_preserves_last_success(self):
  s={'base_url':'https://api.deepseek.com/v1','api_key':'test'};balance=billing.Balance()
  request=Mock(return_value=(json.dumps({'is_available':True,'balance_infos':[{'currency':'CNY','total_balance':'12.34','granted_balance':'0','topped_up_balance':'12.34'}]}),'unused'))
  first=balance.get(s,request,'now');self.assertEqual(first['status'],'ok');balance.get(s,request,'later',True);self.assertEqual(request.call_count,1)
  balance.checked=0;request.side_effect=ValueError('sensitive upstream text');failed=balance.get(s,request,'later');self.assertEqual(failed['status'],'error');self.assertEqual(failed['balances'],first['balances']);self.assertNotIn('sensitive',str(failed))
 def test_balance_never_sends_key_to_proxy_host(self):
  request=Mock();self.assertEqual(billing.Balance().get({'base_url':'https://api.deepseek.com.example.com','api_key':'test'},request,'now')['status'],'unsupported');request.assert_not_called()
 def test_single_message_delete_excludes_history_and_auto_documents_and_restore(self):
  room=app.work.create_conversation('测试')['id']
  with app.db() as c:
   c.execute('INSERT INTO messages VALUES(?,?,?,?,?,?,?)',('u','user','关于公共服务的问题','[]','[]','2026-09-23T10:00:00+08:00',room))
   c.execute('INSERT INTO messages VALUES(?,?,?,?,?,?,?)',('a','assistant','独特的答复内容','[]','[]','2026-09-23T10:00:01+08:00',room))
  app.work.response_saved('a','consultation','测试','秘书');app.work.manage_message('a','trash')
  self.assertEqual(len(app.work._day_messages('2026-09-23')),1)
  self.assertNotIn('独特的答复内容',str(app.work.library()))
  self.assertNotIn('独特的答复内容',app.work.document('minutes','2026-09-23')['raw_content'])
  self.assertEqual(app.work.message_trash(room)[0]['id'],'a')
  app.init();self.assertEqual(len(app.work._day_messages('2026-09-23')),1)
  app.work.manage_message('a','restore');self.assertEqual(len(app.work._day_messages('2026-09-23')),2)
  self.assertIn('独特的答复内容',app.work.document('minutes','2026-09-23')['raw_content'])
 def test_citations_only_include_evidence_actually_referenced(self):
  candidates=[{'ref':'1','kind':'article','id':'a','url':'https://gov.cn/a'}, {'ref':'2','kind':'document','id':'d','url':''}]
  self.assertEqual(used_citations('无须援引资料',candidates),[])
  self.assertEqual(used_citations('据原文[资料1]。',candidates),candidates[:1])
  self.assertEqual(used_citations('参考 https://gov.cn/a',candidates),candidates[:1])
  self.assertEqual(used_citations('不存在[资料99]',candidates),[])
 def test_relevance_rejects_shared_generic_words(self):
  self.assertEqual(relevance_score('韩正的个人简历是什么','推进公共服务工作','领导强调加强政策研究工作'),0)
  self.assertEqual(relevance_score('狗有哪些品种','新华社报道','相关部门研究相关材料'),0)
  self.assertGreater(relevance_score('宁夏养老金政策','宁夏养老金政策发布','城乡居民待遇'),0)
 def test_xuexi_removed_from_sources(self):
  self.assertFalse(any('xuexi' in s['url'] for s in app.SOURCES))
