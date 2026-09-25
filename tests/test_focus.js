const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');

// Exercise the real article loader and new presentation lifecycle with deferred
// responses. A slow article must never reopen over a different page or selection.
const classes = () => {
  const values = new Set();
  return {add: (...names) => names.forEach(n => values.add(n)),
    remove: (...names) => names.forEach(n => values.delete(n)),
    contains: n => values.has(n),
    toggle(n, force) { const on = force ?? !values.has(n); on ? values.add(n) : values.delete(n); return on; }};
};
const element = () => ({classList: classes(), style: {}, scrollTop: 0,
  innerHTML: '', textContent: '', dataset: {}, setAttribute() {}, removeAttribute() {},
  addEventListener() {}, focus() {}});
const reader = {...element(), open: false, close() {this.open = false;}};
const nodes = new Map([['#reader', reader]]);
const $ = selector => {if (!nodes.has(selector)) nodes.set(selector, element()); return nodes.get(selector);};
const pending = new Map();
const ctx = { console, $, $$: () => [], readerRequest: 0, readerTrail: [],
  state: {view: 'daily', article: null, region: 'national', query: ''},
  document: {addEventListener() {}, querySelectorAll: () => [], querySelector: $, body: {...element()}},
  window: {matchMedia: () => ({matches: true}), addEventListener() {}},
  api: url => new Promise(resolve => pending.set(url.split('=')[1], resolve)),
  stopVoice() {}, clearSelection() {}, captureSelection() {}, wireReaderSizing() {},
  localStorage: {getItem: () => ''},
  esc: text => String(text).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('"', '&quot;'),
  md: text => text, draft: () => '', name: () => '秘书',
  safeUrl: () => '#', pubfmt: () => '2026-09-24', regionName: () => '全国要闻',
  stateTag: () => '', bodyHTML: () => '', webToggle: () => '', noteCard: () => ''};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync('dist/focus.js', 'utf8'), ctx);
const app = fs.readFileSync('dist/app.js', 'utf8');
vm.runInContext(app.slice(app.indexOf('async function openArticle('), app.indexOf('async function refreshNotes(')), ctx);
let presentations = 0;
ctx.showReaderPresentation = () => {reader.open = true; presentations++;};
const article = id => ({id, title: '<材料>', source: '演示', minutes: 3,
  notes: [], topics: [], supplements: [], related: []});

(async () => {
  const first = ctx.openArticle('first');
  const second = ctx.openArticle('second');
  pending.get('second')(article('second')); await second;
  pending.get('first')(article('first')); await first;
  assert.equal(ctx.state.article.id, 'second');
  assert.equal(presentations, 1, 'stale response must not render');
  assert.match($('#reader-content').innerHTML, /&lt;材料>/);

  const late = ctx.openArticle('late');
  ctx.closeReader();
  pending.get('late')(article('late')); await late;
  assert.equal(reader.open, false, 'navigation/escape cancels pending presentation');
  assert.equal(presentations, 1);
  assert.equal(ctx.state.focusDismissed, true);

  ctx.state.focusItems = [
    {id:'n1', region:'national', title:'公共服务', topics:['民生']},
    {id:'n2', region:'national', title:'城市更新', topics:[]},
    {id:'g1', region:'guangdong', title:'公共服务', topics:[]}];
  ctx.state.query = '民生';
  assert.deepEqual(Array.from(ctx.focusFilteredItems(), a => a.id), ['n1']);
  ctx.state.query = '';
  assert.equal(ctx.focusFilteredItems().length, 2);
  ctx.state.region = 'guangdong';
  assert.deepEqual(Array.from(ctx.focusFilteredItems(), a => a.id), ['g1']);
  ctx.state.view = 'tasks';
  ctx.state.query = '仅正文命中';
  assert.equal(ctx.focusFilteredItems().length, 1, 'backend full-text matches must remain visible in tasks');

  ctx.toggleInspector(true);
  assert.equal($('.reader-aside').inert, false);
  ctx.toggleInspector(false);
  assert.equal($('.reader-aside').inert, true, 'closed inspector must leave the keyboard order');
  assert.equal(reader.classList.contains('inspector-open'), false);
  console.log('Focused reading: stale requests, navigation cancellation, filters and inspector accessibility passed.');
})().catch(error => {console.error(error); process.exitCode = 1;});
