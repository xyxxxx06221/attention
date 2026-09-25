"""Generic HTML and RSS/Atom discovery for user-provided sources; no model calls."""
import datetime as dt
import email.utils
import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit
from xml.etree import ElementTree as ET
from source_registry import same_site


def feed_entries(raw, base):
    if not re.search(r'<(?:rss|feed|rdf:RDF)[\s>]',raw[:2000],re.I): return []
    try: root=ET.fromstring(raw)
    except ET.ParseError: return []
    entries=[]
    for item in root.iter():
        if item.tag.split('}')[-1] not in ('item','entry'): continue
        title=url=date=''
        for child in item:
            tag=child.tag.split('}')[-1]
            value=''.join(child.itertext()).strip()
            if tag=='title':title=value
            if tag=='link' and child.get('rel','alternate')=='alternate':url=child.get('href') or value
            if tag in ('pubDate','published','updated','date') and not date:date=value
        published='';precision='unknown'
        if date:
            try:
                parsed=dt.datetime.fromisoformat(date.replace('Z','+00:00')) if re.match(r'\d{4}-',date) else email.utils.parsedate_to_datetime(date)
                if parsed.tzinfo is None:parsed=parsed.replace(tzinfo=dt.timezone(dt.timedelta(hours=8)))
                published=parsed.isoformat();precision='day' if re.fullmatch(r'\d{4}-\d{2}-\d{2}',date) else 'minute'
            except (ValueError,TypeError,OverflowError):pass
        if title and url:entries.append({'url':urljoin(base,url),'title':title,'published':published,'precision':precision})
    return entries


class Links(HTMLParser):
    def __init__(self):super().__init__(convert_charrefs=True);self.items=[];self.link=None
    def handle_starttag(self,tag,attrs):
        if tag=='a':self.link=[dict(attrs).get('href',''),'']
    def handle_data(self,data):
        if self.link is not None:self.link[1]+=data
    def handle_endtag(self,tag):
        if tag=='a' and self.link is not None:self.items.append(self.link);self.link=None


def candidates(source, raw):
    feeds=feed_entries(raw,source['url'])
    if source.get('format')=='rss' or feeds:
        links=[(x['url'],x['title']) for x in feeds]
    else:
        page=Links();page.feed(raw);links=page.items
    result=[];seen=set()
    for href,title in links:
        title=re.sub(r'\s+',' ',title).strip()
        url=urljoin(source['url'],href);u=urlsplit(url)
        url=urlunsplit((u.scheme,u.netloc,u.path,u.query,''))
        if u.scheme!='https' or not same_site(url,source['url']) or not 6<=len(title)<=190:continue
        if url==source['url'] or url in seen:continue
        if re.search(r'\.(?:pdf|docx?|xlsx?|zip|rar|png|jpe?g|gif|mp4|mp3|css|js)$',u.path,re.I):continue
        if re.search(r'登录|注册|联系我们|网站地图|隐私政策|版权声明|网站首页|测评表|调查问卷|满意度调查|办事指南|在线申报',title):continue
        if re.search(r'/api-gateway/|/survey/|/login|/search[/.?]',url,re.I):continue
        seen.add(url);result.append((url,title))
        if len(result)>=120:break
    # Home pages often put surveys and evergreen channels before dated articles.
    # Prefer recognizable article paths, while retaining generic CMS slugs.
    def article_priority(pair):
        path=urlsplit(pair[0]).path
        dates=re.findall(r'(20\d{2})[-/年]?(0?[1-9]|1[0-2])[-/月]?(0?[1-9]|[12]\d|3[01])',path)
        date=max((int(y)*10000+int(m)*100+int(d) for y,m,d in dates),default=max((int(y)*10000 for y in re.findall(r'(?<!\d)(20\d{2})(?!\d)',path)),default=0))
        article=bool(re.search(r'/art/|/article/|/content/|post_\d+|/t\d+_|/c\.html|\.shtml$',path,re.I))
        return (date,article)
    return sorted(result,key=article_priority,reverse=True)
