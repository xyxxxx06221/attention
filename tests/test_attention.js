const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const ctx={document:{addEventListener(){}},esc:s=>String(s).replaceAll('&','&amp;').replaceAll('"','&quot;').replaceAll('<','&lt;'),setInterval(){}};
vm.createContext(ctx);vm.runInContext(fs.readFileSync('dist/workbench.js','utf8'),ctx);
const note=(id,start,end,style)=>({id,quote:'共同',paragraph:0,anchor_start:start,anchor_end:end,style,color:'red'});
let html=ctx.highlight('共同共同',[note('one',0,2,'highlight'),note('two',2,4,'underline')],0);
assert.match(html,/data-mark-ids="one"[^>]*>共同/);assert.match(html,/data-mark-ids="two"[^>]*>共同/);
html=ctx.highlight('共同',[note('one',0,2,'highlight'),note('two',0,2,'underline')],0);assert.match(html,/data-mark-ids="two,one"/);assert.match(html,/tabindex="0"/);
assert.equal(ctx.highlight('<script>',[],0),'&lt;script>');console.log('Inline marks retain exact anchors, overlapping IDs and escaped text.');
