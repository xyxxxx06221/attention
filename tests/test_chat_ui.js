const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const storage=new Map();
function makeContext(){
  const listeners={},nodes={};
  const articleToggle={checked:false},officeToggle={checked:false},hint={textContent:''},url={disabled:true};
  const node=selector=>nodes[selector]??=( {value:'',textContent:'',innerHTML:'',isConnected:true,addEventListener(){}} );
  nodes['#article-web']=articleToggle;
  const ctx={window:{YuewenFormat:require('../dist/format.js'),addEventListener(){}},
    document:{querySelector:node,querySelectorAll:s=>s==='[data-web-toggle]'?[articleToggle,officeToggle]:s==='[data-web-hint]'?[hint]:s==='[data-web-url]'?[url]:[],
      addEventListener(type,fn){(listeners[type]??=[]).push(fn)}},
    localStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},
    fetch:()=>new Promise(()=>{}),setInterval(){},setTimeout(){},clearTimeout(){},URL};
  vm.createContext(ctx);vm.runInContext(fs.readFileSync('dist/app.js','utf8'),ctx);
  vm.runInContext(fs.readFileSync('dist/attention.js','utf8'),ctx);
  return {ctx,listeners,nodes,articleToggle,officeToggle,hint,url};
}
(async()=>{
  let env=makeContext();
  assert.equal(env.ctx.webEnabled(),false);
  const change=checked=>{
    const target={checked,matches:s=>s==='[data-web-toggle]'};
    for(const listener of env.listeners.change||[])listener({target});
  };
  change(true);
  assert.equal(env.articleToggle.checked,true);assert.equal(env.officeToggle.checked,true);
  assert.equal(env.url.disabled,false);assert.match(env.hint.textContent,/联网查找/);
  assert.match(env.ctx.webToggle(),/checked/);
  env=makeContext();assert.equal(env.ctx.webEnabled(),true); // A page reload keeps the explicit choice.
  change(false);
  assert.equal(env.url.disabled,true);assert.doesNotMatch(env.ctx.webToggle('article-web'),/checked/);
  const calls=[];
  env.ctx.api=async(path,body)=>{calls.push(body);return {answer:'测试答复[资料1]',citations:[{ref:'1',title:'来源',type:'DeepSeek 联网摘录',url:'https://www.tongji.edu.cn/bio.htm'}]}};
  vm.runInContext("state.article={id:'test-article'}",env.ctx);
  env.nodes['#article-question']={value:'请联网搜索政策'};
  env.nodes['#article-answer']={isConnected:true};
  env.ctx.toast=()=>{};
  await env.ctx.askArticle();assert.equal(calls[0].web,false);
  env.articleToggle.checked=true;env.nodes['#article-question'].value='政策是什么';
  await env.ctx.askArticle();assert.equal(calls[1].web,true);
  assert.match(env.nodes['#article-answer'].innerHTML,/https:\/\/www.tongji.edu.cn\/bio.htm/);
  assert.match(env.nodes['#article-answer'].innerHTML,/本答复引用/);
  console.log('Retrieval toggle persistence, shared controls and article request flags passed.');
})().catch(e=>{console.error(e);process.exitCode=1});
