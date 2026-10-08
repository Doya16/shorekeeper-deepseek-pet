import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync, readFileSync, rmSync} from 'node:fs';
import {join,resolve,sep} from 'node:path';
import {tmpdir} from 'node:os';
import {apply} from './index.js';

test('a late balance response cannot resurrect a signed-out account', async () => {
  const dir=mkdtempSync(join(tmpdir(),'shorekeeper-account-'));
  const previous=process.env.DSH_HOME; process.env.DSH_HOME=dir;
  const listeners={},cleanups=[]; let finish;
  try {
    apply({sessions:{},deepseekAccount:{getBalance:()=>new Promise(r=>{finish=r;})},
      on:(type,handler)=>{listeners[type]=handler;},effect:run=>cleanups.push(run())});
    listeners['deepseek-account/signed-out']();
    finish({status:'ready',value:[{currency:'CNY',balance:'9'}]});
    await new Promise(resolve=>setTimeout(resolve,10));
    const state=JSON.parse(readFileSync(join(dir,'shorekeeper-pet/desktop.json'),'utf8'));
    assert.equal(state.balance.status,'signed-out'); assert.deepEqual(state.balance.wallets,[]);
  } finally {
    for(const cleanup of cleanups)cleanup();
    if(previous===undefined)delete process.env.DSH_HOME;else process.env.DSH_HOME=previous;
    assert.ok(resolve(dir).startsWith(resolve(tmpdir())+sep));rmSync(dir,{recursive:true,force:true});
  }
});

test('plugin lifecycle safely projects balance and real event shapes, disposes heartbeat', async () => {
  const dir=mkdtempSync(join(tmpdir(),'shorekeeper-host-'));
  const previous=process.env.DSH_HOME; process.env.DSH_HOME=dir;
  const listeners={},cleanups=[];
  let balanceCalls=0;
  try {
    apply({sessions:{},deepseekAccount:{async getBalance() {
      balanceCalls++;return {status:'ready',value:[{currency:'CNY',balance:'0E-16',token:'SECRET'}],bonusWallets:[{currency:'CNY',balance:'1e+1'}]};
    }},on:(type,handler)=>{listeners[type]=handler;},effect:run=>cleanups.push(run())});
    await new Promise(resolve=>setTimeout(resolve,10));
    const read=()=>JSON.parse(readFileSync(join(dir,'shorekeeper-pet/desktop.json'),'utf8'));
    assert.equal(read().balance.wallets[0].balance,'0E-16');
    assert.ok(!JSON.stringify(read()).includes('SECRET'));
    listeners['session/event']({id:'one',header:{}},{type:'turn/start',data:{turn:1}});
    listeners['session/event']({id:'one',header:{}},{type:'turn/end',data:{turn:1,reason:{kind:'completed'}}});
    await new Promise(resolve=>setTimeout(resolve,510));
    assert.equal(read().events[0].state,'done');assert.equal(balanceCalls,1);
    listeners['deepseek-account/signed-out']();assert.equal(read().balance.status,'signed-out');
    cleanups.pop()();assert.equal(read().connected,false);
  } finally {
    for(const cleanup of cleanups)cleanup();
    if(previous===undefined)delete process.env.DSH_HOME;else process.env.DSH_HOME=previous;
    assert.ok(resolve(dir).startsWith(resolve(tmpdir())+sep));
    rmSync(dir,{recursive:true,force:true});
  }
});
