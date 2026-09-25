const assert=require('node:assert/strict');
const {render}=require('../dist/format.js');
assert.match(render('## 一、工作安排\n\n**重点**内容。\n\n- 第一项\n- 第二项'),/<h3>一、工作安排<\/h3>.*<strong>重点<\/strong>.*<ul><li>第一项<\/li><li>第二项<\/li><\/ul>/s);
for(const input of ['<script>alert(1)</script>','[执行](javascript:alert)','[链接](https://example.com/"onclick="x)','<img src=x onerror=alert(1)>']){
 const output=render(input);assert.doesNotMatch(output,/<script|<img|href="javascript:|"onclick=/);
}
assert.match(render('一、议题\n\n（ 一 ）'),/<h3>一、议题<\/h3>/);
assert.match(render('| 项目 | 数量 |\n| --- | --- |\n| 材料 | 2 |'),/<table>.*<td>材料<\/td>/);
assert.match(render('```\n<script>\n```'),/&lt;script&gt;/);
assert.equal(render('第一行\n第二行\n\n新的段落'),'<p>第一行<br>第二行</p><p>新的段落</p>');
assert.equal(render('第一行  \r\n**重点**第二行'),'<p>第一行<br><strong>重点</strong>第二行</p>');
assert.match(render('### 标题\n第一行\n第二行\n\n- 要点一\n- 要点二'),/<h4>标题<\/h4><p>第一行<br>第二行<\/p><ul>/);
assert.equal(render('一、议题\n（一）本日共留存1次提问、1次答复。\n（二）后续事项待明确。'),'<h3>一、议题</h3><p>（一）本日共留存1次提问、1次答复。</p><p>（二）后续事项待明确。</p>');
assert.equal(render('（一）工作安排'),'<h4>（一）工作安排</h4>');
console.log('Markdown formatting and unsafe-input checks passed.');
