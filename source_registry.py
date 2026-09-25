"""Persisted regional sources. A successful, recent probe is required before adding a source."""
import hashlib
import json
import secrets
import sqlite3
import time
from urllib.parse import urlsplit, urlunsplit

REGIONS = dict(national='全国', beijing='北京', tianjin='天津', hebei='河北', shanxi='山西',
    neimenggu='内蒙古', liaoning='辽宁', jilin='吉林', heilongjiang='黑龙江', shanghai='上海',
    jiangsu='江苏', zhejiang='浙江', anhui='安徽', fujian='福建', jiangxi='江西', shandong='山东',
    henan='河南', hubei='湖北', hunan='湖南', guangdong='广东', guangxi='广西', hainan='海南',
    chongqing='重庆', sichuan='四川', guizhou='贵州', yunnan='云南', xizang='西藏', shaanxi='陕西',
    gansu='甘肃', qinghai='青海', ningxia='宁夏', xinjiang='新疆', taiwan='台湾', hongkong='香港', macau='澳门')


def same_site(url, source_url):
    host = (urlsplit(url).hostname or '').lower().removeprefix('www.')
    root = (urlsplit(source_url).hostname or '').lower().removeprefix('www.')
    return bool(root) and (host == root or host.endswith('.' + root))


class SourceRegistry:
    def __init__(self, db, stamp):
        self.db, self.stamp = db, stamp

    def migrate(self, c, defaults):
        c.executescript('''
        CREATE TABLE IF NOT EXISTS reading_regions(id TEXT PRIMARY KEY,name TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS news_sources(id TEXT PRIMARY KEY,name TEXT NOT NULL,url TEXT UNIQUE NOT NULL,
          region TEXT NOT NULL REFERENCES reading_regions(id),rank INTEGER NOT NULL,kind TEXT NOT NULL,
          enabled INTEGER NOT NULL DEFAULT 1,builtin INTEGER NOT NULL DEFAULT 0,format TEXT NOT NULL DEFAULT 'auto',
          tested_at TEXT NOT NULL DEFAULT '',test_report TEXT NOT NULL DEFAULT '{}');
        CREATE TABLE IF NOT EXISTS source_probes(token TEXT PRIMARY KEY,fingerprint TEXT NOT NULL,expires REAL NOT NULL,report TEXT NOT NULL);
        ''')
        if c.execute("SELECT 1 FROM metadata WHERE key='regional_sources_v1'").fetchone():
            return
        for rid in dict.fromkeys(['national', *[s['region'] for s in defaults]]):
            c.execute('INSERT OR IGNORE INTO reading_regions VALUES(?,?)', (rid, REGIONS[rid]))
        for s in defaults:
            c.execute('INSERT OR IGNORE INTO news_sources(id,name,url,region,rank,kind,enabled,builtin) VALUES(?,?,?,?,?,?,?,1)',
                      tuple(s[k] for k in ('id','name','url','region','rank','kind','enabled')))
        c.execute("INSERT INTO metadata VALUES('regional_sources_v1','1')")

    def sources(self):
        with self.db() as c:
            return [dict(r) for r in c.execute("SELECT * FROM news_sources ORDER BY region<>'national',rowid")]

    def regions(self):
        with self.db() as c:
            return [dict(r) | {'limit':20 if r['id']=='national' else 10}
                    for r in c.execute("SELECT * FROM reading_regions ORDER BY id<>'national',rowid")]

    def config(self):
        return {'regions':self.regions(), 'sources':self.sources(),
                'catalog':[{'id':k,'name':v} for k,v in REGIONS.items()]}

    def normalize(self, data):
        name = str(data.get('name','')).strip()
        if not 1 <= len(name) <= 60: raise ValueError('来源名称须为 1–60 个字')
        region = data.get('region')
        if region not in REGIONS: raise ValueError('请选择有效省份或全国')
        raw = str(data.get('url','')).strip()
        try:
            u = urlsplit(raw)
            if u.scheme != 'https' or not u.hostname or u.username or u.password or u.port not in (None,443):
                raise ValueError('自定义来源需填写公开 HTTPS 网址')
        except (ValueError, TypeError): raise ValueError('自定义来源需填写公开 HTTPS 网址')
        if len(raw)>2000 or any(ord(x)<32 for x in raw): raise ValueError('来源网址无效')
        url = urlunsplit(('https',u.netloc.lower(),u.path or '/',u.query,''))
        try: rank = int(data.get('rank',2))
        except (ValueError,TypeError): raise ValueError('来源权重应为 0–10 的整数')
        if not 0 <= rank <= 10: raise ValueError('来源权重应为 0–10 的整数，数字越小优先级越高')
        fmt = data.get('format','auto')
        if fmt not in ('auto','html','rss'): raise ValueError('来源格式无效')
        return {'name':name,'url':url,'region':region,'rank':rank,'format':fmt,'kind':'用户提供来源', 'enabled':1}

    @staticmethod
    def fingerprint(source):
        keys = ('name','url','region','rank','format')
        return hashlib.sha256(json.dumps({k:source.get(k,'auto' if k=='format' else '') for k in keys},sort_keys=True).encode()).hexdigest()

    def probe(self, data, tester):
        if data.get('id'):
            source = next((s for s in self.sources() if s['id']==data['id']), None)
            if not source: raise ValueError('来源不存在')
        else: source = self.normalize(data) | {'id':'custom-probe','builtin':0}
        try: report = tester(source)
        except Exception as e: report = {'ok':False,'message':str(e),'candidates':0,'samples':[]}
        report['tested_at'] = self.stamp()
        with self.db() as c:
            c.execute('DELETE FROM source_probes WHERE expires<?',(time.time(),))
            if data.get('id'):
                c.execute('UPDATE news_sources SET tested_at=?,test_report=? WHERE id=?',
                          (report['tested_at'],json.dumps(report,ensure_ascii=False),source['id']))
            if report.get('ok'):
                token = secrets.token_urlsafe(24)
                c.execute('INSERT INTO source_probes VALUES(?,?,?,?)',
                          (token,self.fingerprint(source),time.time()+1800,json.dumps(report,ensure_ascii=False)))
                report['test_token'] = token
        return report

    def save(self, data, add_region=False):
        source = self.normalize(data)
        with self.db() as c:
            # Serialize probe consumption, source insertion and province activation.
            c.execute('BEGIN IMMEDIATE')
            probe = c.execute('SELECT * FROM source_probes WHERE token=?',(str(data.get('test_token','')),)).fetchone()
            if not probe or probe['expires']<time.time() or probe['fingerprint']!=self.fingerprint(source):
                raise ValueError('请先测试此来源；修改参数后需要重新测试（有效期 30 分钟）')
            exists = c.execute('SELECT 1 FROM reading_regions WHERE id=?',(source['region'],)).fetchone()
            if add_region:
                if source['region']=='national' or exists: raise ValueError('该地区已存在，请直接新增来源')
                c.execute('INSERT INTO reading_regions VALUES(?,?)',(source['region'],REGIONS[source['region']]))
            elif not exists: raise ValueError('请使用“新增省份”同时提供并测试来源')
            if c.execute('SELECT count(*) FROM news_sources').fetchone()[0]>=60: raise ValueError('最多保存 60 个来源')
            rid = 'custom-' + secrets.token_hex(8)
            report = json.loads(probe['report'])
            try:
                c.execute('INSERT INTO news_sources(id,name,url,region,rank,kind,enabled,builtin,format,tested_at,test_report) VALUES(?,?,?,?,?,?,1,0,?,?,?)',
                          (rid,source['name'],source['url'],source['region'],source['rank'],source['kind'],source['format'],report['tested_at'],probe['report']))
            except sqlite3.IntegrityError: raise ValueError('此网址已添加，不能重复分配到多个地区')
            c.execute('DELETE FROM source_probes WHERE token=?',(data['test_token'],))
        return {'ok':True,'id':rid}

    def delete_source(self, rid):
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE')
            source=c.execute('SELECT * FROM news_sources WHERE id=?',(rid,)).fetchone()
            if not source: raise ValueError('来源不存在')
            if source['builtin'] and source['region']=='national': raise ValueError('全国内置来源固定保留')
            if source['region']!='national' and c.execute('SELECT count(*) FROM news_sources WHERE region=?',(source['region'],)).fetchone()[0]<=1:
                raise ValueError('这是该省份最后一个来源，请使用“删除省份”一并移除配置')
            c.execute('DELETE FROM news_sources WHERE id=?',(rid,))
        return {'ok':True}

    def delete_region(self, rid):
        if rid=='national': raise ValueError('全国栏目及内置来源不能删除')
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE')
            if not c.execute('SELECT 1 FROM reading_regions WHERE id=?',(rid,)).fetchone(): raise ValueError('省份不存在')
            c.execute('DELETE FROM news_sources WHERE region=?',(rid,))
            c.execute('DELETE FROM reading_regions WHERE id=?',(rid,))
        return {'ok':True,'message':'省份及对应来源已移除，已保存的文章与笔记保留在档案中'}
