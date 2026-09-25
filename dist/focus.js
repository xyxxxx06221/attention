/* Presentation-only helpers. All writes continue through the existing app actions. */
function uiIcon(name){return `<i class="f7-icons" aria-hidden="true">${name}</i>`}
function isFocusView(){return ['daily','tasks'].includes(state.view)&&!state.special}
function syncReaderSelection(){
 const placeholder=$('.reading-placeholder');if(placeholder){placeholder.inert=$('#reader').open;placeholder.setAttribute('aria-hidden',String($('#reader').open))}
 const docked=$('#reader').open&&$('#reader').classList.contains('docked'),mobile=window.matchMedia('(max-width: 760px)').matches;
 const inbox=$('.inbox');if(inbox)inbox.inert=docked&&(mobile||$('#reader').classList.contains('reader-full'));
 const sidebar=$('.sidebar');if(sidebar)sidebar.inert=docked&&mobile;
 document.querySelectorAll('.inbox-item').forEach(b=>{const selected=$('#reader').open&&b.dataset.open===state.article?.id;b.classList.toggle('selected',selected);b.setAttribute('aria-current',selected?'true':'false')});
}
function closeReader({dismiss=true}={}){
 ++readerRequest;readerTrail=[];stopVoice();clearSelection();state.focusDismissed=dismiss;state.focusArticleId=null;
 const reader=$('#reader');reader.close();reader.classList.remove('docked','reader-full','inspector-open');document.body.classList.remove('mobile-reading');syncReaderSelection();
}
function prepareSurface(view){
 const focused=isFocusView();document.body.classList.toggle('focused-view',focused);
 if(!focused&&$('#reader').classList.contains('docked'))closeReader();
 document.body.dataset.view=view==='sources'?'settings':view;
 document.querySelectorAll('.sidebar [data-view]').forEach(b=>{const active=b.dataset.view===(view==='sources'?'settings':view);b.classList.toggle('active',active);active?b.setAttribute('aria-current','page'):b.removeAttribute('aria-current')});
}
function settingsNavigation(section){return `<nav class="settings-nav" aria-label="设置分类"><button class="${section==='general'?'active':''}" data-view="settings" ${section==='general'?'aria-current="page"':''}>${uiIcon('slider_horizontal_3')}通用与 AI</button><button class="${section==='sources'?'active':''}" data-view="sources" ${section==='sources'?'aria-current="page"':''}>${uiIcon('tray_arrow_down')}来源与采集</button></nav>`}
function inboxItem(a){return `<button class="inbox-item ${state.article?.id===a.id&&$('#reader').open?'selected':''}" data-open="${esc(a.id)}" aria-current="${state.article?.id===a.id&&$('#reader').open}"><span class="inbox-dot ${a.state==='pending'?'unread':''}" aria-hidden="true"></span><span class="inbox-item-body"><strong>${esc(a.title)}</strong><span class="inbox-meta">${esc(a.source)} · ${a.minutes} 分钟${a.note_count?' · '+a.note_count+' 条批注':''}</span><span class="inbox-preview">${esc((a.summary||a.reason||a.topics.join(' / ')).replace(/\n/g,' '))}</span><span class="inbox-category">${esc(a.topics.join(' / '))}</span></span></button>`}
function focusFilteredItems(){const q=state.view==='tasks'?'':(state.query||'').trim().toLocaleLowerCase();return (state.focusItems||[]).filter(a=>a.region===state.region&&(!q||[a.title,a.source,a.summary,a.reason,...a.topics].join(' ').toLocaleLowerCase().includes(q)))}
function updateInboxRows(){
 const rows=focusFilteredItems(),box=$('#inbox-list');if(!box)return;
 box.innerHTML=rows.length?rows.map(inboxItem).join(''):`<div class="inbox-empty">${uiIcon('doc_text_search')}<h2>${state.query?'没有找到匹配材料':'本卷暂无待阅材料'}</h2><p>${state.query?'试试其他标题、主题或关键词。':'可以切换期次，或到档案室继续阅读。'}</p>${state.query?'<button class="btn" data-ui="clear-search">清除搜索</button>':'<button class="btn" data-view="archive">打开档案室</button>'}</div>`;
 $('#inbox-count').textContent=`${state.query?'找到':'待阅'} ${rows.length} 篇 · 约 ${rows.reduce((n,a)=>n+a.minutes,0)} 分钟`;syncReaderSelection();
}
async function renderFocusedInbox(items,daily=true){
 state.focusItems=items;
 const d=state.data,day=d.day;
 $('#content').innerHTML=`<div class="reading-workspace"><section class="inbox" aria-label="${daily?'本期文章':'代办文件'}"><header class="inbox-header"><div class="inbox-title"><h1>${daily?'今日阅文':'代办文件'}</h1><button class="icon-button" data-ui="edition-info" aria-label="${daily?'查看本期导读':'查看代办说明'}" title="${daily?'本期导读':'代办说明'}">${uiIcon('info_circle')}</button></div>${daily?collectionButton():''}${daily?`<label class="inbox-date"><span>阅读期次</span><input type="date" id="edition-date" aria-label="阅文日期" value="${day}" max="${today()}"></label>`:'<p class="inbox-description">留待继续阅读与办理的材料</p>'}<form id="search-form" class="inbox-search">${uiIcon('search')}<input id="focus-search" name="q" type="search" aria-label="${daily?'搜索本期文章':'检索所有代办'}" placeholder="${daily?'搜索标题、来源或主题':'检索代办全文，回车确认'}" value="${esc(state.query)}"></form><div class="inbox-tabs" aria-label="地区">${readingRegions().map(({id:r})=>`<button data-region="${r}" class="${state.region===r?'active':''}" aria-pressed="${state.region===r}">${esc(areaName(r))} <span>${items.filter(a=>a.region===r).length}</span></button>`).join('')}</div><p class="inbox-count" id="inbox-count"></p>${d.job.running?`<p id="job-message" class="collection-status" role="status">${esc(d.job.message)}</p>`:''}${daily&&d.edition?.status==='partial'?'<button class="collection-warning" data-view="sources">采集有缺项 · 查看报告</button>':''}</header><div class="inbox-list" id="inbox-list"></div><footer class="inbox-footer">${daily?`<button class="btn text" data-action="daily-summary">${uiIcon('text_bubble')}阅文小结</button><span>已处理 ${d.completed} / ${d.total}</span>`:`<button class="btn text" data-action="clear-tasks">${uiIcon('checkmark_circle')}清空本卷代办</button>`}</footer></section>${inboxSplitter()}<section class="reading-placeholder" aria-label="阅读区">${uiIcon('book')}<h2>${d.total&&!items.length?'这一期，读完了。':'选一篇，开始阅读。'}</h2><p>原文、批注与思考，在这里慢慢展开。</p><button class="btn" data-ui="read-first">阅读第一篇</button></section></div>`;
 updateInboxRows();restoreInboxWidth();
 const visible=focusFilteredItems();
 if($('#reader').open&&$('#reader').classList.contains('docked')&&visible.some(a=>a.id===state.article?.id))return;
 if($('#reader').open&&$('#reader').classList.contains('docked'))closeReader({dismiss:false});
 if(visible.length&&!state.focusDismissed&&window.matchMedia('(min-width: 761px)').matches)await openArticle(visible[0].id,{resetTrail:true});
}
function readerToolbar(a){return `<header class="reader-header"><div class="reader-location"><button class="icon-button" data-ui="reader-return" aria-label="${readerTrail.length?'返回上一份文件':'返回文章列表'}" title="返回">${uiIcon('chevron_left')}</button><span class="reader-path">${esc(regionName(a.region))}</span></div><div class="reader-tools"><button class="btn edit-personal" data-work="edit-document" data-kind="article" data-id="${esc(a.id)}" aria-label="编辑个人稿" title="编辑个人稿">${uiIcon('doc_text')}<span>编辑个人稿</span></button><details class="toolbar-menu"><summary class="icon-button type-button" aria-label="阅读字号与窗口" title="阅读字号与窗口">Aa</summary><div class="toolbar-popover"><span class="popover-label">阅读显示</span><div class="actions"><button class="btn" data-work="font-smaller" aria-label="减小字号">A−</button><button class="btn" data-work="font-larger" aria-label="增大字号">A＋</button></div><button class="btn text" data-work="reader-full">${uiIcon('arrow_up_left_arrow_down_right')}专注全屏</button><label>待阅列表宽度<input type="range" data-inbox-width min="260" max="620" value="368" aria-label="待阅列表宽度"></label><button class="btn text" data-release="reset-width">恢复默认宽度</button></div></details><button class="icon-button inspector-toggle" data-ui="toggle-inspector" aria-label="打开批注与讨论" aria-expanded="false" title="批注与讨论">${uiIcon('square_pencil')}</button><details class="toolbar-menu"><summary class="icon-button" aria-label="更多阅读操作" title="更多阅读操作">${uiIcon('ellipsis')}</summary><div class="toolbar-popover"><a class="btn text" href="${safeUrl(a.url)}" target="_blank" rel="noopener noreferrer">${uiIcon('arrow_up_right_square')}原始网页</a><button class="btn text" data-action="article-summary">${uiIcon('text_bubble')}请${esc(name())}梳理</button><button class="btn text" data-action="article-history">${uiIcon('clock')}历史问答</button><button class="btn text" data-action="feedback">${uiIcon('bubble_left')}选稿反馈</button><button class="btn text" data-article-action="hide">${uiIcon('archivebox')}移出档案</button><button class="btn text danger" data-article-action="delete">${uiIcon('trash')}彻底删除</button></div></details><span class="toolbar-divider"></span><button class="btn primary" title="标记已阅并存入档案，移出待阅" data-article-action="read">已阅归档</button></div></header>`}
function showReaderPresentation(){
 const r=$('#reader');r.classList.toggle('docked',isFocusView());r.classList.remove('reader-full','inspector-open');r.style.width='';r.style.height='';
 if(!r.open)isFocusView()?r.show():r.showModal();
 r.setAttribute('aria-modal',isFocusView()?'false':'true');state.focusArticleId=state.article.id;state.focusDismissed=false;
 document.body.classList.toggle('mobile-reading',isFocusView());syncReaderSelection();if(typeof restoreInboxWidth==='function')restoreInboxWidth();
}
function toggleInspector(force){
 const reader=$('#reader');const open=force===undefined?!reader.classList.contains('inspector-open'):force;
 reader.classList.toggle('inspector-open',open);const trigger=$('.inspector-toggle');trigger?.setAttribute('aria-expanded',String(open));trigger?.setAttribute('aria-label',open?'关闭批注与讨论':'打开批注与讨论');
 const aside=$('.reader-aside');if(aside)aside.inert=!open;
 if(open&&!state.quote)$('#note-text')?.focus({preventScroll:true});if(!open)trigger?.focus({preventScroll:true});
}
async function focusAction(action){
 if(action==='toggle-nav'){const expanded=document.body.classList.toggle('nav-expanded');$('#nav-toggle').setAttribute('aria-expanded',String(expanded));return}
 if(action==='clear-search'){state.query='';$('#focus-search').value='';if(state.view==='tasks')await renderRecords();else updateInboxRows();restoreInboxWidth();$('#focus-search').focus();return}
 if(action==='read-first'){const a=focusFilteredItems()[0];if(a)await openArticle(a.id);else toast('当前没有待阅材料');return}
 if(action==='toggle-inspector')return toggleInspector();
 if(action==='close-inspector')return toggleInspector(false);
 if(action==='reader-return'){if(readerTrail.length)return attentionAction('reader-back',{});closeReader();await load(false);return}
 if(action==='edition-info'){
  if(state.view==='tasks'){showDialog('#organize-dialog','代办说明','<p class="formal">这里收纳所有期次尚未办理的材料，按已配置地区分卷显示。输入关键词后按回车，可检索代办原文。已阅、略过和存档继续沿用原有办理规则。</p>');return}
  const d=state.data;
  showDialog('#organize-dialog',state.view==='daily'?'本期导读':'代办说明',`<p class="data-note">${d.day} · ${readingRegions().map(r=>`${esc(r.name)} ${d.edition_stats[r.id]?.total||0} 件`).join(' · ')}</p><div class="formal">${md(d.edition?.briefing||'全国最多 20 件、每个省份最多 10 件。已办理材料不会自动补位。')}</div><p class="data-note">本期已处理 ${d.completed} / ${d.total}，所有期次尚有 ${d.pending} 份代办文件。</p>`,'<button class="btn" data-view="sources">前往设置 · 来源与采集</button>');return;
 }
}
document.addEventListener('click',e=>{
 const b=e.target.closest('[data-ui]');if(b){e.preventDefault();focusAction(b.dataset.ui).catch(err=>toast(err.message))}
 const menu=e.target.closest('.toolbar-menu');document.querySelectorAll('.toolbar-menu[open]').forEach(d=>{if(d!==menu)d.open=false});
 if(e.target.closest('.toolbar-popover button,.toolbar-popover a'))menu?.removeAttribute('open');
});
document.addEventListener('input',e=>{if(e.target.id==='focus-search'&&state.view==='daily'){state.query=e.target.value;updateInboxRows()}});
window.addEventListener('resize',()=>{if(typeof state!=='undefined')syncReaderSelection()});
document.addEventListener('keydown',e=>{
 if(e.key==='Escape'&&$('#reader').open&&$('#reader').classList.contains('docked')&&!document.querySelector('dialog[open]:not(#reader)')){
  if(document.querySelector('.toolbar-menu[open]'))document.querySelectorAll('.toolbar-menu[open]').forEach(d=>d.open=false);
  else if($('#reader').classList.contains('inspector-open'))toggleInspector(false);
  else closeReader();e.preventDefault();
 }
});
