"""Finite daily editions. A completed file never causes another file to refill its slot."""
LIMITS={'national':20,'guangdong':10}

def migrate(c):
    if 'selected' not in {r[1] for r in c.execute('PRAGMA table_info(edition_items)')}:
        c.execute('ALTER TABLE edition_items ADD COLUMN selected INTEGER NOT NULL DEFAULT 1')

def select_edition(c,day,limits=None,names=None):
    limits=LIMITS if limits is None else limits
    names=names or {'national':'全国','guangdong':'广东'}
    rows=c.execute('SELECT a.*,e.parent_id FROM edition_items e JOIN articles a ON a.id=e.article_id WHERE e.day=? AND a.deleted=0 ORDER BY a.score DESC,a.tier,a.topics,a.published DESC,a.id',(day,)).fetchall()
    selected=set()
    for region,limit in limits.items():
        selected.update(r['id'] for r in [a for a in rows if a['region']==region and a['parent_id'] is None][:limit])
    c.execute('UPDATE edition_items SET selected=0 WHERE day=?',(day,))
    for r in rows:
        if r['id'] in selected or r['parent_id'] in selected:
            c.execute('UPDATE edition_items SET selected=1 WHERE day=? AND article_id=?',(day,r['id']))
    counts={region:sum(r['id'] in selected and r['region']==region for r in rows) for region in limits}
    briefing="本期"+"、".join(f"{names.get(r,r)} {counts[r]} 件" for r in limits)+"。按公共重要性编选；已办结文件不补位。"
    c.execute('UPDATE editions SET briefing=? WHERE day=?',(briefing,day))
    return selected

def migrate_existing(c):
    if not c.execute("SELECT 1 FROM metadata WHERE key='edition_limits_v3'").fetchone():
        for r in c.execute('SELECT day FROM editions').fetchall():select_edition(c,r['day'])
        c.execute("INSERT INTO metadata VALUES('edition_limits_v3','1')")
