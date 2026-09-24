"""Editable personal copies, batch filing, recoverable trash and conversation rooms."""
import datetime as dt
import hashlib
import json
import sqlite3
import uuid


def digest(text):return hashlib.sha256(text.encode()).hexdigest()

def migrate_workspace(c):
    c.executescript('''
    CREATE TABLE IF NOT EXISTS conversations(id TEXT PRIMARY KEY,title TEXT,article_id TEXT,created TEXT,updated TEXT,deleted INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS daily_reports(day TEXT PRIMARY KEY,content TEXT,updated TEXT,fingerprint TEXT);
    CREATE TABLE IF NOT EXISTS document_edits(kind TEXT,resource_id TEXT,title TEXT,content TEXT,revision INTEGER,updated TEXT,base_fingerprint TEXT,PRIMARY KEY(kind,resource_id));
    CREATE TABLE IF NOT EXISTS document_versions(kind TEXT,resource_id TEXT,title TEXT,content TEXT,revision INTEGER,created TEXT,PRIMARY KEY(kind,resource_id,revision));
    CREATE TABLE IF NOT EXISTS resource_trash(kind TEXT,resource_id TEXT,title TEXT,metadata TEXT,created TEXT,PRIMARY KEY(kind,resource_id));
    CREATE TABLE IF NOT EXISTS message_trash(message_id TEXT PRIMARY KEY,created TEXT NOT NULL);
    CREATE VIEW IF NOT EXISTS active_messages AS SELECT m.rowid AS rowid,m.* FROM messages m
      WHERE NOT EXISTS(SELECT 1 FROM message_trash t WHERE t.message_id=m.id);
    ''')
    if 'deleted' not in {r[1] for r in c.execute('PRAGMA table_info(conversations)')}:
        c.execute('ALTER TABLE conversations ADD COLUMN deleted INTEGER NOT NULL DEFAULT 0')

class ArchiveOperations:
    def manage_message(self,mid,action):
        if action not in ('trash','restore'):raise ValueError('无效消息操作')
        with self.db() as c:
            row=c.execute('SELECT m.* FROM messages m JOIN conversations r ON r.id=m.scope WHERE m.id=? AND r.deleted=0',(mid,)).fetchone()
            if not row:raise ValueError('消息不存在，或所属议事已删除')
            if action=='trash':c.execute('INSERT OR IGNORE INTO message_trash VALUES(?,?)',(mid,self.stamp()))
            else:c.execute('DELETE FROM message_trash WHERE message_id=?',(mid,))
            c.execute('UPDATE conversations SET updated=? WHERE id=?',(self.stamp(),row['scope']))
            day=row['created'][:10]
        self.rebuild_report(day)
        self.rebuild_minutes(day)
        return {'ok':True}

    def message_trash(self,scope):
        with self.db() as c:
            return [dict(r) for r in c.execute('SELECT m.id,m.role,m.content,m.created,t.created AS deleted_at FROM messages m JOIN message_trash t ON t.message_id=m.id JOIN conversations r ON r.id=m.scope WHERE m.scope=? AND r.deleted=0 ORDER BY t.created DESC,m.rowid DESC',(scope,))]

    def ensure_conversation(self,scope,title,aid=None):
        with self.db() as c:
            c.execute('INSERT OR IGNORE INTO conversations(id,title,article_id,created,updated) VALUES(?,?,?,?,?)',(scope,title[:100],aid,self.stamp(),self.stamp()))
        return scope

    def conversations(self):
        with self.db() as c:
            return [dict(r) for r in c.execute('SELECT c.*,(SELECT count(*) FROM active_messages m WHERE m.scope=c.id) AS message_count FROM conversations c WHERE c.deleted=0 ORDER BY updated DESC,created DESC')]

    def conversation_trash(self):
        with self.db() as c:
            return [dict(r) for r in c.execute('SELECT c.*,(SELECT count(*) FROM active_messages m WHERE m.scope=c.id) AS message_count FROM conversations c WHERE c.deleted=1 ORDER BY updated DESC')]

    def manage_conversation(self,rid,action):
        if action not in ('trash','restore'):raise ValueError('无效议事操作')
        with self.db() as c:
            room=c.execute('SELECT id FROM conversations WHERE id=?',(rid,)).fetchone()
            if not room:raise ValueError('议事不存在')
            days={r[0] for r in c.execute('SELECT DISTINCT substr(created,1,10) FROM active_messages WHERE scope=?',(rid,))}
            c.execute('UPDATE conversations SET deleted=?,updated=? WHERE id=?',(int(action=='trash'),self.stamp(),rid))
        for day in days:
            self.rebuild_report(day)
            self.rebuild_minutes(day)
        return {'ok':True}

    def create_conversation(self,title='新议事',aid=None):
        rid=uuid.uuid4().hex;self.ensure_conversation(rid,str(title).strip() or '新议事',aid)
        return {'id':rid}

    def rename_conversation(self,rid,title):
        title=str(title).strip()[:100]
        if not title:raise ValueError('请输入议题名称')
        with self.db() as c:
            if not c.execute('SELECT 1 FROM conversations WHERE id=? AND deleted=0',(rid,)).fetchone():raise ValueError('议事不存在')
            c.execute('UPDATE conversations SET title=?,updated=? WHERE id=?',(title,self.stamp(),rid))
        return {'ok':True}

    def bootstrap_rooms(self):
        with self.db() as c:
            for r in c.execute('SELECT scope,min(created) first,max(created) last FROM active_messages GROUP BY scope').fetchall():
                a=c.execute('SELECT title FROM articles WHERE id=?',(r['scope'],)).fetchone()
                c.execute('INSERT OR IGNORE INTO conversations(id,title,article_id,created,updated) VALUES(?,?,?,?,?)',(r['scope'],a['title'] if a else '综合议事',r['scope'] if a else None,r['first'],r['last']))
        for d in {r['created'][:10] for r in self._all_messages()}:self.rebuild_report(d)
        with self.db() as c:
            for r in c.execute("SELECT d.dossier_id,m.created FROM dossier_items d JOIN active_messages m ON m.id=d.resource_id WHERE d.kind='document'").fetchall():
                c.execute('INSERT OR IGNORE INTO dossier_items VALUES(?,?,?)',(r['dossier_id'],'document','daily:'+r['created'][:10]))

    def _all_messages(self):
        with self.db() as c:return [dict(r) for r in c.execute('SELECT * FROM active_messages ORDER BY created,rowid')]

    def rebuild_report(self,day):
        rows=[r for r in self._day_messages(day) if r['role']=='assistant']
        with self.db() as c:
            if not rows:
                c.execute('DELETE FROM daily_reports WHERE day=?',(day,));return
            parts=[f'# {day} 研判文稿']
            for i,r in enumerate(rows,1):
                question=c.execute("SELECT content FROM active_messages WHERE scope=? AND role='user' AND created<=? ORDER BY created DESC,rowid DESC LIMIT 1",(r['scope'],r['created'])).fetchone()
                parts.extend([f'## {i}. {question[0][:100] if question else (r["article_title"] or "议事研判")}',r['content']])
            text='\n\n'.join(parts);fp=digest(text)
            old=c.execute('SELECT fingerprint FROM daily_reports WHERE day=?',(day,)).fetchone()
            if not old or old['fingerprint']!=fp:
                c.execute('INSERT INTO daily_reports VALUES(?,?,?,?) ON CONFLICT(day) DO UPDATE SET content=excluded.content,updated=excluded.updated,fingerprint=excluded.fingerprint',(day,text,self.stamp(),fp))

    def overlay(self,kind,rid,base):
        base=dict(base);base.setdefault('revision',0);base['original_content']=base.get('content','');base['original_title']=base.get('title','')
        with self.db() as c:r=c.execute('SELECT * FROM document_edits WHERE kind=? AND resource_id=?',(kind,rid)).fetchone()
        if r:
            base.update(title=r['title'],content=r['content'],revision=r['revision'],edited=r['updated'],source_updated=r['base_fingerprint']!=digest(base['original_content']))
        return base

    def edit_document(self,kind,rid,title,content,revision):
        if kind not in ('article','document','minutes'):raise ValueError('此类文件不能修订')
        title=str(title).strip()[:160];content=str(content)
        if not title or not content.strip():raise ValueError('标题和正文不能为空')
        if len(content)>500000:raise ValueError('文稿过长')
        base=self.document(kind,rid)
        with self.db() as c:
            current=c.execute('SELECT revision FROM document_edits WHERE kind=? AND resource_id=?',(kind,rid)).fetchone()
            actual=current[0] if current else 0
            if int(revision)!=actual:raise ValueError('文件已在别处更新，请重新打开后合并修改')
            c.execute('INSERT OR IGNORE INTO document_versions VALUES(?,?,?,?,?,?)',(kind,rid,base['title'],base['content'],actual,self.stamp()))
            c.execute('INSERT INTO document_edits VALUES(?,?,?,?,?,?,?) ON CONFLICT(kind,resource_id) DO UPDATE SET title=excluded.title,content=excluded.content,revision=excluded.revision,updated=excluded.updated,base_fingerprint=excluded.base_fingerprint',(kind,rid,title,content,actual+1,self.stamp(),digest(base['original_content'])))
            if kind=='article':
                c.execute('UPDATE articles SET archived=1 WHERE id=? AND hidden=0',(rid,));self.index_article(rid,c)
        self.event('personal_document_saved',kind=kind)
        return {'ok':True,'revision':actual+1}

    def manage_folder(self,action,rid,name=''):
        with self.db() as c:
            f=c.execute('SELECT * FROM dossiers WHERE id=?',(rid,)).fetchone()
            if not f:raise ValueError('专题不存在')
            if action=='rename':
                if not str(name).strip():raise ValueError('请输入专题名称')
                try:c.execute('UPDATE dossiers SET name=? WHERE id=?',(str(name).strip()[:40],rid))
                except sqlite3.IntegrityError:raise ValueError('同级专题名称已存在')
            elif action=='delete':
                children=[r[0] for r in c.execute('SELECT id FROM dossiers WHERE parent_id=?',(rid,))]
                for fid in children+[rid]:
                    c.execute('DELETE FROM dossier_items WHERE dossier_id=?',(fid,));c.execute('DELETE FROM dossiers WHERE id=?',(fid,))
            else:raise ValueError('未知专题操作')
        return {'ok':True}

    def batch(self,action,items,folder=None):
        if not isinstance(items,list) or not items or len(items)>500:raise ValueError('请选择 1—500 份文件')
        selected={(str(i.get('kind','')),str(i.get('id',''))) for i in items if isinstance(i,dict)}
        resources={(r['resource_kind'],r['resource_id']):r for r in self.resources(include_trashed=action=='restore')}
        if len(selected)!=len(items) or any(k not in resources for k in selected):raise ValueError('部分文件已变动，请刷新后重选')
        with self.db() as c:
            if action=='file' and not c.execute('SELECT 1 FROM dossiers WHERE id=?',(folder,)).fetchone():raise ValueError('请选择已有专题')
            for kind,rid in selected:
                if action=='file':c.execute('INSERT OR IGNORE INTO dossier_items VALUES(?,?,?)',(folder,kind,rid))
                elif action=='trash':
                    metadata={}
                    if kind=='article':
                        a=c.execute('SELECT state,archived,hidden FROM articles WHERE id=?',(rid,)).fetchone();metadata=dict(a)
                        c.execute("UPDATE articles SET hidden=1,archived=0,state='skipped' WHERE id=?",(rid,))
                    c.execute('INSERT OR IGNORE INTO resource_trash VALUES(?,?,?,?,?)',(kind,rid,resources[(kind,rid)]['title'],json.dumps(metadata),self.stamp()))
                elif action=='restore':
                    t=c.execute('SELECT * FROM resource_trash WHERE kind=? AND resource_id=?',(kind,rid)).fetchone()
                    if not t:raise ValueError('文件不在回收站')
                    if kind=='article':
                        meta=json.loads(t['metadata']);c.execute('UPDATE articles SET hidden=0,archived=1,state=? WHERE id=?',(meta.get('state','read'),rid))
                    c.execute('DELETE FROM resource_trash WHERE kind=? AND resource_id=?',(kind,rid))
                else:raise ValueError('未知批量操作')
        self.event('archive_batch',action=action,count=len(items));return {'ok':True,'count':len(items)}

    def trash(self):
        with self.db() as c:return [dict(r) for r in c.execute('SELECT kind,resource_id AS id,title,created FROM resource_trash ORDER BY created DESC')]
