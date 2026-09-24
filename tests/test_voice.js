const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
let recognition,status,inputEvents=0;
function classes(){return {add(){},remove(){}}}
const field={value:'',isConnected:true,dispatchEvent(){inputEvents++}};
const button={dataset:{voice:'question'},textContent:'开始转写',classList:classes(),setAttribute(){},closest(){return {append(s){status=s}}}};
class Recognition{constructor(){recognition=this}start(){}stop(){this.stopCalled=true}}
const context={window:{SpeechRecognition:Recognition},document:{getElementById(){return field},addEventListener(){},createElement(){return {classList:classes(),setAttribute(){},lastElementChild:{textContent:''},querySelector(){return this.textContent?null:{}},textContent:'',innerHTML:''}}},$$(){return [button]},Event:class{},toast(){}};
vm.createContext(context);vm.runInContext(fs.readFileSync('dist/workbench.js','utf8'),context);
(async()=>{
 await context.voice('question');assert.equal(button.textContent,'停止转写');assert.match(status.innerHTML,/启动/);
 recognition.onstart();assert.match(status.lastElementChild.textContent,/正在转写/);
 recognition.onresult({resultIndex:0,results:[Object.assign([{transcript:'独立判断。'}],{isFinal:true})]});assert.equal(field.value,'独立判断。');assert.equal(inputEvents,1);
 context.stopVoice();assert.equal(recognition.stopCalled,true);recognition.onend();assert.match(status.textContent,/已结束/);assert.equal(button.textContent,'开始转写');
 await context.voice('question');recognition.onerror({error:'not-allowed'});recognition.onend();assert.equal(status.textContent,'麦克风未获授权。');assert.equal(button.textContent,'开始转写');
 console.log('Voice start, transcription, stop and permission-error states passed.');
})().catch(e=>{console.error(e);process.exit(1)});
