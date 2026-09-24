"""Conservative lexical relevance and evidence-only citation selection."""
import re

NOISE = ['请结合','请根据','帮我','请你','请问','告诉我','介绍一下','解释一下','搜索一下','梳理一下',
         '相关材料','相关报道','相关内容','相关原文','参考资料','好词好句','历史讨论','当时怎么想的',
         '有哪些','是什么','什么是','为什么','怎么样','怎么看','如何','怎么','什么','一下',
         '相关','情况','材料','文章','新闻','档案','批注','心得','笔记','资料','原文','搜索','联网',
         '梳理','整理','介绍','解释','回顾','总结','列出','三个月','一个月','本月','已读','读过',
         '我的想法','我的判断','我的','这些','这篇','这件事','这条','我以前','我这','收集的',
         '以及','关于','有关','哪些','含义','意思','请','的','与','跟']


def terms(question):
    text = re.sub(r'https?://\S+|20\d{2}-\d{2}-\d{2}', ' ', question.casefold())
    for stop in sorted(NOISE, key=len, reverse=True):
        text = text.replace(stop, ' ')
    return [w for w in re.findall(r'[\u4e00-\u9fff]{2,}|[a-z][a-z0-9_-]{1,}', text) if w not in ('可以','需要','进行')]


def relevance_score(question, title, body=''):
    chunks = terms(question)
    if not chunks:
        return 0
    title, body = title.casefold(), body.casefold()
    hay = title+' '+body
    exact = [word for word in chunks if word in hay]
    if exact:
        # One short generic word cannot stand in for the longer subject in a query.
        weight = sum(len(w) for w in exact) / max(1, sum(len(w) for w in chunks))
        if weight >= .45 or any(len(w) >= 4 for w in exact):
            return sum(20 if word in title else 10 for word in exact)
    grams = {word[i:i+2] for word in chunks for i in range(len(word)-1)}
    hits = sum(g in hay for g in grams)
    if hits >= 3 and hits / max(1,len(grams)) >= .65 and any(g in title for g in grams):
        return hits
    return 0


def used_citations(answer, candidates):
    used = set(re.findall(r'\[资料(\d+)\]', answer))
    urls = set(re.findall(r'https?://[^\s<>\]\)）]+', answer))
    seen, result = set(), []
    for c in candidates:
        marker = str(c.get('ref', ''))
        url = c.get('url','')
        identity = (c.get('kind','article'), c.get('id') or url)
        if identity in seen or not (marker and marker in used or url and url in urls):
            continue
        seen.add(identity)
        result.append(c)
    return result
