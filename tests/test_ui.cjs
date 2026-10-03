// DOM-independent regression checks. These do not replace real Safari layout testing.
const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const handlers={},nodes={};
const node=selector=>nodes[selector]??={innerHTML:'',textContent:'',style:{},open:false,close(){this.open=false;},showModal(){this.open=true;}};
const context=vm.createContext({console,Intl,Date,Set,Map,URL,Uint8Array,JSON,Math,Number,String,Promise,Error,TypeError,performance:{getEntriesByType:()=>[]},crypto:require('node:crypto').webcrypto,sessionStorage:{getItem:()=>null,removeItem(){},setItem(){}},document:{querySelector:node,body:{setAttribute(){},removeAttribute(){}},addEventListener:(type,fn)=>(handlers[type]??=[]).push(fn)},setTimeout:()=>0,setInterval:()=>0,fetch:()=>{throw Error('unexpected request')}});
vm.runInContext(fs.readFileSync(path.join(root,'site/catalog.js'),'utf8'),context);
let source=fs.readFileSync(path.join(root,'site/app.js'),'utf8').replace(/start\(\);\s*$/,'');vm.runInContext(source,context);
const run=js=>vm.runInContext(js,context);
let count=0;function check(label,fn){fn();console.log('PASS',label);count++;}
check('five snack types and a single stationery choice',()=>{assert.equal(run("PRODUCT_CATALOG.filter(p=>p.category==='간식').length"),5);assert.equal(run("PRODUCT_CATALOG.filter(p=>p.category==='문구').length"),1)});
check('all catalogue images point to bundled files',()=>{for(const p of JSON.parse(run('JSON.stringify(PRODUCT_CATALOG)'))){if(p.src)assert(fs.existsSync(path.join(root,'site',p.src)));assert(!run(`productArt(${p.id})`).includes('undefined'));}});
check('old stationery choices resolve to the one new illustration',()=>{for(const id of [0,1,2,4,5])assert(run(`productArt(${id})`).includes('./assets/shop/stationery.png'))});
run(`state={actor:'teacher',students:[],products:[{id:'a',name:'마이쮸',image:8,price:0,stock:0,active:false},{id:'b',name:'문구',image:0,category:'문구',price:100,stock:2,active:true}],discounts:{},serverTime:Date.now(),threads:[]};`);
check('students cannot see unlisted starter snacks',()=>{run("state.actor='student';shopCategory='전체'");const html=run('shopPage()');assert(!html.includes('<h3>마이쮸</h3>'));assert(html.includes('<h3>문구</h3>'))});
check('category filters the shop',()=>{run("state.actor='teacher';shopCategory='간식'");let html=run('shopPage()');assert(html.includes('<h3>마이쮸</h3>'));assert(!html.includes('<h3>문구</h3>'))});
check('reply text survives render and is HTML escaped',()=>{run(`selectedThread='thread1';replyDrafts.thread1='<내 답장>';state.threads=[{id:'thread1',title:'문의',student:'student',closed:false,lastBy:'student',messages:[{body:'안녕',by:'student',time:Date.now()}]}]`);assert(run('messagesPage()').includes('&lt;내 답장&gt;'))});
check('product picker has visual radio choices',()=>{const html=run('productPicker(10)');assert.equal((html.match(/type="radio"/g)||[]).length,run('PRODUCT_CATALOG.length'));assert(html.includes('value="10" checked'))});
(async()=>{run("token='session-a';start=async()=>{};replyDrafts={thread1:'private'};messageDraft={title:'private',body:'private'}");await run('logout(false)');check('logout clears drafts before next user',()=>{assert.equal(run('Object.keys(replyDrafts).length'),0);assert.equal(run('messageDraft.body'),'');assert.equal(run('token'),null)});console.log(`${count} UI logic checks passed`);})().catch(e=>{console.error(e);process.exitCode=1});
