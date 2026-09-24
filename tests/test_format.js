const assert=require('node:assert/strict');
const {render}=require('../dist/format.js');
assert.match(render('## 一、工作安排\n\n**重点**内容。\n\n- 第一项\n- 第二项'),/<h3>一、工作安排<\/h3>.*<strong>重点<\/strong>.*<ul><li>第一项<\/li><li>第二项<\/li><\/ul>/s);
for(const input of ['<script>alert(1)</script>','[执行](javascript:alert)','[链接](https://example.com/"onclick="x)','<img src=x onerror=alert(1)>']){
 const output=render(input);assert.doesNotMatch(output,/<script|<img|href="javascript:|"onclick=/);
}
assert.match(render('一、议题\n\n（ 一 ）'),/<h3>一、议题<\/h3>/);
assert.match(render('| 项目 | 数量 |\n| --- | --- |\n| 材料 | 2 |'),/<table>.*<td>材料<\/td>/);
assert.match(render('```\n<script>\n```'),/&lt;script&gt;/);
console.log('Markdown formatting and unsafe-input checks passed.');
