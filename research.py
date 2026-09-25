"""Public-web research: bounded queries, relevance gates and retrieved source text."""
import concurrent.futures
import re
import json
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import parse_qs, quote, urljoin, urlsplit
from xml.etree import ElementTree
from relevance import relevance_score

OFFICIAL=('gov.cn','people.com.cn','news.cn','xinhuanet.com','qstheory.cn','southcn.com','nfnews.com')
def official(url):
    host=urlsplit(url).hostname or ''
    return any(host==d or host.endswith('.'+d) for d in OFFICIAL)

def primary(url):
    host=urlsplit(url).hostname or ''
    return official(url) or any(host==d or host.endswith('.'+d) for d in ('edu.cn','ac.cn','cas.cn'))

def query_plan(question,article_title=''):
    text=re.sub(r'\s+',' ',question).strip()
    bio=re.search(r'([\u4e00-\u9fff]{2,4})(?:同志)?(?:的)?(?:简历|履历)',text)
    if bio:
        subject=re.sub(r'^(?:一下|搜索|一下子|关于|一下|查查|查找|同志)','',bio.group(1)).removesuffix('同志')
        # Prefer the name adjacent to 同志 when an instruction precedes it.
        named=re.search(r'([\u4e00-\u9fff]{2,4})同志',text)
        if named:subject=re.sub(r'^(?:一下|关于|搜索|查查)','',named.group(1))
        return {'query':subject+' 简历','subject':subject,'intent':'biography'}
    location=re.search(r'([\u4e00-\u9fff]{2,5}(?:县|市|区|省))(?:具体|到底|是|在|位于|的|哪里)',text)
    if location and re.search('哪里|哪儿|位置|位于',text):
        subject=re.sub(r'^(?:请问|我想问|关于)','',location.group(1))
        return {'query':subject+' 地理位置','subject':subject,'intent':'location'}
    for prefix in ['请你','帮我','请','你去','你能','搜索一下','查找一下','搜索','搜一下','查一下','联网','告诉我','然后给我','给我']:
        text=text.replace(prefix,' ')
    text=re.sub(r'[，。！？、；：\n]+',' ',text);text=re.sub(r'\s+',' ',text).strip()
    if article_title and (len(text)>50 or re.search('这篇|本文|本篇|这件事|这条',text)):
        text=re.sub(r'[丨|]',' ',article_title)[:70]
    return {'query':text[:90],'subject':'','intent':'general'}

def relevant(plan,title,body=''):
    hay=(title+' '+body).casefold();subject=plan['subject']
    if subject:return subject.casefold() in hay
    return relevance_score(plan['query'],title,body)>0

class SearchPage(HTMLParser):
    def __init__(self):
        super().__init__();self.results=[];self.active=None;self.part=None;self.depth=0
    def handle_starttag(self,tag,attrs):
        a=dict(attrs);classes=a.get('class','')
        if tag=='a' and 'result__a' in classes:
            url=a.get('href','');url=parse_qs(urlsplit(urljoin('https://duckduckgo.com',url)).query).get('uddg',[url])[0]
            self.active={'title':'','url':url,'snippet':''};self.results.append(self.active);self.part='title';self.depth=1
        elif 'result__snippet' in classes and self.active:
            self.part='snippet';self.depth=1
        elif self.part and tag not in ('br','img','input','meta','link'):self.depth+=1
    def handle_endtag(self,tag):
        if self.part:
            self.depth-=1
            if self.depth<=0:self.part=None
    def handle_data(self,text):
        if self.part and self.active:self.active[self.part]+=text

class Research:
    def __init__(self,request,parse,event):self.request,self.parse,self.event=request,parse,event
    def candidates(self,query,provider):
        if provider=='duckduckgo':
            raw,_=self.request('https://html.duckduckgo.com/html/?q='+quote(query))
            if 'anomaly.js' in raw:raise ValueError('搜索服务要求人工验证')
            p=SearchPage();p.feed(raw);return p.results
        raw,_=self.request('https://www.bing.com/search?format=rss&mkt=zh-CN&q='+quote(query))
        root=ElementTree.fromstring(raw)
        return [{'title':r.findtext('title',''),'url':r.findtext('link',''),'snippet':r.findtext('description','')} for r in root.findall('.//item')]
    def search(self,question,article_title=''):
        plan=query_plan(question,article_title)
        if not plan['query']:raise ValueError('请补充要查证的对象')
        diagnostics=[];candidates=[];seen=set();read_urls=set();items=[]
        registry=Path(__file__).parent/'sources'/'references.json'
        for r in json.loads(registry.read_text(encoding='utf-8')) if registry.exists() else []:
            if r['subject']==plan['subject'] and r['intent']==plan['intent']:
                candidates.append(r|{'snippet':r['subject']});seen.add(r['url'])
        # Prefer primary sources for people and geography; still allow broader research.
        queries=[plan['query']+' site:gov.cn',plan['query']]
        attempts=[('duckduckgo',queries[0]),('duckduckgo',queries[1]),('bing',plan['query'])]
        def read(r):
            try:
                raw,url=self.request(r['url'],official=official(r['url']));p=self.parse(raw,url,r['title']);body=p['body']
                if len(body)<80 or not relevant(plan,p['title'],body):return None
                if plan['intent']=='biography' and not re.search(r'简历|履历|年参加工作|参加工作|历任|年\d{1,2}月生',body+p['title']):return None
                return {'title':p['title'],'url':url,'text':body[:18000],'published':p['published'],'type':'官方原文' if official(url) else '机构原文' if primary(url) else '外部网页正文'}
            except Exception as exc:
                self.event('search_source_failed',error=type(exc).__name__);return None
        def read_pending():
            pending=sorted((r for r in candidates if r['url'] not in read_urls),key=lambda r:not primary(r['url']))[:6]
            read_urls.update(r['url'] for r in pending)
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                for result in pool.map(read,pending):
                    if result and not any(x['url']==result['url'] for x in items):items.append(result)
        if candidates:read_pending()
        for provider,query in attempts:
            # A search hit is not evidence until its body can actually be read.
            if len(items)>=2:break
            try:found=self.candidates(query,provider)
            except Exception as exc:
                diagnostics.append({'provider':provider,'query':query,'accepted':0,'status':'unavailable','reason':str(exc)[:240]});self.event('search_provider_failed',provider=provider,error=type(exc).__name__);continue
            accepted=0
            for r in found:
                url=r['url'];host=urlsplit(url).hostname or ''
                if url in seen or urlsplit(url).scheme not in ('https','http'):continue
                if urlsplit(url).scheme=='http' and not official(url):continue
                if plan['intent'] in ('biography','location') and not primary(url):continue
                if not relevant(plan,r['title'],r['snippet']):continue
                seen.add(url);candidates.append(r);accepted+=1
            before=len(items);read_pending()
            diagnostics.append({'provider':provider,'query':query,'accepted':accepted,'readable':len(items)-before,'status':'ok' if len(items)>before else 'no_readable_results' if accepted else 'no_relevant_results'})
        items.sort(key=lambda r:r['published'] or '',reverse=True)
        self.event('research_completed',sources=len(items),rejected=len(candidates)-len(items))
        error=''
        if not items:
            reasons=list(dict.fromkeys(d['reason'] for d in diagnostics if d.get('reason')))
            error='没有找到可读取的相关网页。'+('；'.join(reasons)+'。' if reasons else '检索结果未通过相关性或正文读取检查。')
        return {'items':items[:4],'query':plan['query'],'attempts':diagnostics,'error':error}
