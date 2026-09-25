#!/usr/bin/env python3
"""Offline UI review with fictional articles and a separate, disposable archive."""
import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
# Deliberately ignore an inherited data path. Never open the user's real archive.
os.environ['ZHUYI_V1_DATA'] = str(ROOT / 'data' / 'ui-review')
sys.path.insert(0, str(ROOT))
import app


def no_network(*args, **kwargs):
    raise ValueError('离线 UI 评审模式：联网采集与模型调用未启用。')


def seed():
    app.init()
    day = app.window()[1].date().isoformat()
    with app.db() as c:
        if c.execute('SELECT 1 FROM editions WHERE day=?', (day,)).fetchone():
            return
    rows = [
        ('完善公共服务体系，让民生保障更有温度', '公共服务的可及性、均衡性与可持续性，是本篇演示材料的阅读线索。关注政策如何从制度安排走向日常生活。', 0, 'national', 96, '民生保障', 6),
        ('从科技创新到产业创新：观察高质量发展的新路径', '围绕创新链与产业链协同，梳理基础研究、成果转化与企业创新之间的关系。', 2, 'national', 93, '科技创新', 5),
        ('把城市更新的落点，放在居民真实的生活需求上', '从老旧街区到社区服务，以公共空间和便民设施为切口，理解城市更新中的精细治理。', 1, 'national', 83, '城市治理', 4),
        ('在绿色转型中，寻找经济发展的长期动力', '从节能改造、资源循环到绿色消费，记录产业转型中值得持续观察的议题。', 0, 'national', 78, '绿色发展', 4),
        ('以优质文化供给，丰富基层公共生活', '关注公共文化服务如何连接社区、学校与乡村，让文化资源走进更广泛的日常生活。', 3, 'national', 74, '公共文化', 3),
        ('读懂县域经济：产业、人口与公共服务的协同', '通过几个观察维度，理解县域发展与城乡融合之间的联系。', 1, 'national', 66, '城乡发展', 5),
        ('广东观察：制造业转型中的创新与韧性', '以制造业为切入点，观察技术改造、人才培养和生产性服务之间的协同关系。', 4, 'guangdong', 95, '产业发展', 5),
        ('从一条绿道，看见城市公共空间的变化', '公共空间既承载出行，也连接休闲和社区生活。记录城市建设中以人为本的细节。', 5, 'guangdong', 80, '城市治理', 3),
        ('让优质教育资源更好地走向基层', '关注师资交流、课程共享与数字资源如何支撑公共服务均衡发展。', 4, 'guangdong', 72, '教育发展', 4),
        ('阅读之后：把材料转化为自己的问题', '这是一份已归档的演示材料，用于展示阅读进度和个人笔记。', 3, 'national', 70, '阅读方法', 3),
    ]
    start, end = app.window(day)
    with app.db() as c:
        c.execute('INSERT INTO editions(day,start,end,collected,status,report,briefing,method) VALUES(?,?,?,?,?,?,?,?)',
                  (day, start.isoformat(), end.isoformat(), app.stamp(), 'complete', '[]',
                   '本页为虚构演示材料，仅用于界面评审，不代表真实新闻或来源机构发布。阅读、批注与归档操作只保存在本评审目录。', 'UI 演示'))
    for i, (title, summary, source, region, score, topic, minutes) in enumerate(rows):
        body = '\n\n'.join([
            '【UI 演示材料】本文为界面设计演示而编写，并非真实新闻，不代表任何机构发布。',
            summary,
            '阅读一份材料，不只是记住结论，也是在辨认问题的来处。哪些变化值得关注，哪些条件尚待落实，哪些问题需要结合更多材料理解，都可以成为自己的阅读线索。',
            '从公共服务的视角出发，可以关注资源如何配置、服务如何抵达，以及不同群体的具体需求。制度层面的安排，需要通过清晰的执行机制和持续的反馈转化为实际改善。',
            '将视线落到具体的日常生活，会发现宏观议题与个人经验之间有许多连接。保留原文、记录疑问、对照不同时间的材料，有助于形成更完整的理解。',
            '读到这里，可以选中一句话留下批注，也可以在下方写一段阅后心得。所有修改只会保存到独立演示档案中。',
        ])
        aid = app.store_article(f'https://example.invalid/ui-review/{day}/{i}',
            {'title': title, 'body': body, 'published': start.isoformat(), 'precision': 'day'}, app.SOURCES[source])
        with app.db() as c:
            c.execute('UPDATE articles SET source=?,region=?,score=?,tier=?,kind=?,topics=?,summary=?,minutes=?,editor=?,reason=? WHERE id=?',
                ('演示来源 · 非真实报道', region, score, 1 if score >= 90 else 2, '观察材料', json.dumps([topic], ensure_ascii=False), summary, minutes, 'UI 演示', '虚构材料，仅供本地界面评审。', aid))
            c.execute('INSERT INTO edition_items(day,article_id,parent_id,selected) VALUES(?,?,NULL,1)', (day, aid))
            if i == 9:
                c.execute("UPDATE articles SET state='read',archived=1,opened=1 WHERE id=?", (aid,))
        if i in (0, 9):
            app.add_note({'article_id': aid, 'text': '把宏观安排与具体生活联系起来，是这次阅读想继续追问的方向。', 'kind': '阅后心得'})


class ReviewHandler(app.Handler):
    def do_POST(self):
        allowed = {'/api/article', '/api/note', '/api/notes', '/api/messages',
                   '/api/dossiers', '/api/archive-batch', '/api/edit-document',
                   '/api/conversations', '/api/file-resource', '/api/client-error', '/api/clear-tasks'}
        if urlsplit(self.path).path not in allowed:
            return self.send({'error': '这是离线 UI 评审版。可以体验阅读、批注和归档；采集、AI 与配置修改未启用。'}, 403)
        return super().do_POST()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8877)
    args = parser.parse_args()
    app.PORT = args.port
    app.request_url = no_network
    seed()
    server = app.ThreadingHTTPServer(('127.0.0.1', args.port), ReviewHandler)
    print(f'Offline UI review: http://127.0.0.1:{args.port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
