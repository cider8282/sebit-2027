const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),site=path.join(root,'site');
let passed=0;
function check(label,fn){fn();console.log('PASS',label);passed++;}
check('project Pages paths resolve below the repository URL',()=>{
  const index=fs.readFileSync(path.join(site,'index.html'),'utf8');
  for(const [,src] of index.matchAll(/(?:src|href)="([^"]+)"/g)){
    assert(src.startsWith('./'));
    const url=new URL(src,'https://teacher.github.io/sebit-test/');
    assert(url.pathname.startsWith('/sebit-test/'));
    assert(fs.existsSync(path.join(site,src)));
  }
  const css=fs.readFileSync(path.join(site,'style.css'),'utf8');
  for(const [,src] of css.matchAll(/url\(['"]?([^)'" ]+)/g)){
    assert(!src.startsWith('/'));
    assert(fs.existsSync(path.join(site,src)));
  }
});
check('browser and server product catalogues agree',()=>{
  const a=JSON.parse(fs.readFileSync(path.join(site,'product-catalog.json'))), b=JSON.parse(fs.readFileSync(path.join(root,'functions/product-catalog.json')));
  assert.deepEqual(a.map(({src,...x})=>x),b.map(({src,...x})=>x));
});
check('website configuration contains no setup or service-account key',()=>{
  const config=fs.readFileSync(path.join(site,'config.js'),'utf8');
  assert(!config.includes('private_key'));
  assert(!config.includes('SEBIT_SETUP_KEY'));
  assert(!fs.readdirSync(site).some(x=>x.endsWith('.py')||x.includes('service-account')));
});
check('first setup UI requires a separate code',()=>{
  const app=fs.readFileSync(path.join(site,'app.js'),'utf8');
  assert(app.includes("field('학급 개설 코드','setupKey'"));
  assert(!app.includes("fetch('/api/"));
});
const calls=[],context=vm.createContext({window:{SEBIT_CONFIG:{apiBase:'https://example.cloudfunctions.net/sebit_api'}},URL,AbortController,setTimeout,clearTimeout,Error,TypeError,fetch:async(url,options)=>{calls.push({url,options});return {ok:true,json:async()=>({ok:true})}}});
vm.runInContext(fs.readFileSync(path.join(site,'transport.js'),'utf8'),context);
(async()=>{
  await context.window.SEBIT_TRANSPORT.request('command',{requestId:'same-request'},'private-session');
  check('API targets Firebase and sends the authenticated request',()=>{
    assert.equal(calls[0].url,'https://example.cloudfunctions.net/sebit_api/command');
    assert.equal(calls[0].options.headers.Authorization,'Bearer private-session');
    assert.equal(calls[0].options.credentials,'omit');
    assert.equal(JSON.parse(calls[0].options.body).requestId,'same-request');
  });
  context.window.SEBIT_CONFIG={apiBase:''};
  await assert.rejects(()=>context.window.SEBIT_TRANSPORT.request('status'),/설정되지/);
  check('unconfigured website explains the missing connection',()=>assert.equal(calls.length,1));
  context.window.SEBIT_CONFIG={apiBase:'http://example.com'};
  await assert.rejects(()=>context.window.SEBIT_TRANSPORT.request('status'),/HTTPS/);
  check('non-local unencrypted endpoints are rejected',()=>assert.equal(calls.length,1));
  console.log(`${passed} web deployment checks passed`);
})().catch(error=>{console.error(error);process.exitCode=1});
