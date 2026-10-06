// DOM-independent regression checks. These do not replace real Safari layout testing.
const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const handlers={},nodes={};
const node=selector=>nodes[selector]??={innerHTML:'',textContent:'',style:{},open:false,close(){this.open=false;},showModal(){this.open=true;}};
const context=vm.createContext({console,Intl,Date,Set,Map,URL,Uint8Array,JSON,Math,Number,String,Promise,Error,TypeError,performance:{getEntriesByType:()=>[]},crypto:require('node:crypto').webcrypto,sessionStorage:{getItem:()=>null,removeItem(){},setItem(){}},document:{querySelector:node,body:{setAttribute(){},removeAttribute(){}},addEventListener:(type,fn)=>(handlers[type]??=[]).push(fn)},setTimeout:()=>0,setInterval:()=>0,fetch:()=>{throw Error('unexpected request')}});
vm.runInContext(fs.readFileSync(path.join(root,'site/catalog.js'),'utf8'),context);
let source=fs.readFileSync(path.join(root,'site/app.js'),'utf8').replace(/start\(\);\s*$/,'');vm.runInContext(source,context);
const run=js=>vm.runInContext(js,context);

run(`state={actor:'teacher',serverTime:Date.now(),students:[{id:'p1',name:'예시',number:1,active:true,xp:0,character:'default'}],ranks:[{xp:0,name:'알'}],jobs:[],jobPeriods:[],jobRecords:[],quests:[],applications:[],threads:[]}`);
run(`state.jobPeriods=[{id:'period',status:'active',assignments:{p1:'j'},jobs:{j:{name:'이름 변경 직업',reward:[20,10]}},adjustments:{p1:[]}}];state.jobRecords=Array.from({length:35},(_,i)=>({id:'r'+i,student:'p1',period:'period',date:today(),memo:'메모-'+i}));state.jobRecords[34].memo='<script>위험</script>'`);
const jobs=run('jobsPage()');assert(jobs.includes('오늘 완료 ✓'));assert(jobs.includes('인정 0일'));assert(jobs.includes('이름 변경 직업'));assert(jobs.includes('&lt;script&gt;'));assert(!jobs.includes('메모-4<'));assert(jobs.includes('메모-5<'));assert.equal(run('state.jobRecords.length'),35);
run(`state.quests=[{id:'old',name:'완료 과제',description:'',start:today(),end:today(),status:'ended',reward:[10,5]},{id:'new',name:'진행 과제',description:'',start:today(),end:today(),status:'published',reward:[10,5]},{id:'removed',name:'제거 과제',description:'',start:today(),end:today(),status:'ended',listRemoved:true,reward:[10,5]}]`);
let quests=run('questsPage()');assert(quests.indexOf('진행 과제')<quests.indexOf('완료 과제'));assert(!quests.includes('제거 과제'));assert(quests.includes('목록에서 삭제'));assert(!quests.includes('data-action="questDelete"'));
run(`state.threads=[{id:'thread',student:'p1',title:'대화',closed:true,lastBy:'teacher',messages:[{by:'teacher',body:'답장',time:Date.now()}]}];selectedThread='thread'`);assert(run('messagesPage()').includes('data-action="deleteThread"'));run(`state.actor='p1'`);assert(!run('messagesPage()').includes('data-action="deleteThread"'));
console.log('PASS job status, latest 30 records, escaped memo, quest order/removal, teacher-only closed conversation button');
