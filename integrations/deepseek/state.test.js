import {test} from 'node:test';
import assert from 'node:assert/strict';
import {PetState, safeBalance} from './state.js';
test('native tool results clear the matching call while other calls remain active', () => {
  let now = 10; const s = new PetState(() => now);
  const emit = (type,data) => s.accept({id:'contract'}, {type,data});
  emit('turn/start',{turn:1});
  emit('tool/call',{callId:'read',name:'read_file'});
  emit('tool/call',{callId:'write',name:'write_file'});
  emit('tool/result',{turn:1,step:1,message:{role:'tool',toolCallId:'write',content:'SECRET'}});
  assert.equal(s.snapshot().sessions[0].state,'reading');
  emit('tool/result',{turn:1,step:1,message:{role:'tool',toolCallId:'read'}});
  now += 2; assert.equal(s.snapshot().sessions[0].state,'thinking');
  assert.equal(s.sessions.get('contract').tools.size,0);
  assert.ok(!JSON.stringify(s.snapshot()).includes('SECRET'));
  emit('tool/ptc-dispatch-start',{subCallId:'sub',name:'edit_file'});
  emit('tool/ptc-dispatch',{subCallId:'sub'});
  now += 2; assert.equal(s.snapshot().sessions[0].state,'thinking');
});
test('waiting survives parallel tool results and multiple approval decisions', () => {
  const s = new PetState(() => 20);
  const emit = (type,data={}) => s.accept({id:'approval'}, {type,data});
  emit('turn/start',{turn:1});
  emit('tool/call',{callId:'ask',name:'ask_user'});
  emit('tool/call',{callId:'read',name:'read_file'});
  assert.equal(s.snapshot().sessions[0].state,'waiting');
  emit('approval/asked',{id:'first'}); emit('approval/asked',{id:'second'});
  emit('tool/result',{message:{toolCallId:'ask'}});
  emit('approval/decided',{id:'first',outcome:'allowed-once'});
  emit('step/start'); assert.equal(s.snapshot().sessions[0].state,'waiting');
  emit('approval/decided',{id:'second',outcome:'rejected'});
  assert.equal(s.snapshot().sessions[0].state,'reading');
});
const session = {id: 'a', header: {}};
test('parallel sessions complete separately, tasks retain turn identity', () => {
  const s = new PetState(() => 10);
  const emit = (type, data = {}, sub = session) => s.accept(sub, {type, data});
  emit('turn/start', {turn: 1}); emit('turn/start', {turn: 1}, {id: 'b'});
  emit('tool/call', {callId: 'r', name: 'read_file', arguments: 'SECRET'});
  assert.equal(s.snapshot().sessions[0].state, 'reading');
  emit('tool/result', {message: {role:'tool', toolCallId: 'r'}});
  emit('tool/call', {callId: 'e', name: 'edit_file'});
  assert.equal(s.snapshot().sessions[0].state, 'writing');
  assert.equal(s.snapshot().sessions[0].turn_id, '1');
  emit('turn/end', {turn: 1, reason: {kind: 'completed'}});
  emit('turn/end', {turn: 1, reason: {kind: 'completed'}});
  assert.equal(s.events.length, 1); assert.equal(s.snapshot().sessions[1].active, true);
  assert.ok(!JSON.stringify(s.snapshot()).includes('SECRET'));
});
test('approval, errors, cancel, subagents, repair, tool holds', () => {
  let now = 10; const s = new PetState(() => now);
  const e = (type, data = {}) => s.accept(session, {type, data});
  e('turn/start', {turn: 1}); e('tool/call', {name: 'read_file', callId: 'a'});
  e('approval/asked'); assert.equal(s.snapshot().sessions[0].state, 'waiting');
  e('approval/decided'); e('tool/result', {message: {role:'tool', toolCallId: 'a'}});
  assert.equal(s.snapshot().sessions[0].state, 'reading'); now += 2;
  assert.equal(s.snapshot().sessions[0].state, 'thinking');
  e('turn/end', {reason: {kind: 'error'}}); assert.equal(s.events[0].state, 'error');
  e('turn/start', {turn: 2}); e('turn/end', {reason: {kind: 'aborted'}});
  assert.equal(s.events[1].state, 'paused');
  s.accept({id: 'sub', header: {origin: 'subagent'}}, {type: 'turn/start', data: {turn: 1}});
  assert.equal(s.sessions.size, 1);
  e('turn/start', {turn: 3}); e('turn/end', {reason: {kind: 'interrupted'}});
  assert.equal(s.events.length, 2);
});
test('balance projection cannot export credential fields or fake percentages', () => {
  const b = safeBalance({status:'ready', value:[{currency:'CNY',balance:'12.34',token:'SECRET'}], bonusWallets:[]});
  assert.deepEqual(b, {status:'ready', wallets:[{currency:'CNY',balance:'12.34'}], bonus:[]});
  assert.equal(safeBalance(null).status, 'signed-out');
  assert.equal(safeBalance({status:'failed'}).status, 'unavailable');
  assert.equal(safeBalance({status:'ready', value:[{currency:'CNY',balance:'0E-16'}]}).wallets.length, 1);
});
const used = (input, output, hit, provider = 'deepseek-account', model = 'deepseek-flash') =>
  ({turn: 1, step: 1, message: {role: 'assistant', content: 'SECRET', source: {kind: 'model', provider, model}},
    usage: {inputTokens: input, outputTokens: output, cacheReadTokens: hit, cacheWriteTokens: 0, totalTokens: input + output + hit}});
test('a finished turn carries its token usage, grouped by model and hour, without message text', () => {
  const s = new PetState(() => 10);
  const e = (type, data = {}, time) => s.accept(session, {type, data, time});
  e('turn/start', {turn: 1});
  e('assistant/message', used(100, 20, 900), 3600000 * 5 + 10);
  e('assistant/message', used(50, 5, 1000), 3600000 * 5 + 20);
  e('assistant/message', used(10, 1, 0), 3600000 * 6 + 1);
  e('assistant/message', used(7, 7, 7, 'deepseek-account', 'deepseek-v4-pro'), 3600000 * 6 + 2);
  e('turn/end', {turn: 1, reason: {kind: 'completed'}});
  assert.deepEqual(s.events[0].usage, {search: 0, fetch: 0, tokens: [
    {provider: 'deepseek-account', model: 'deepseek-flash', hour: 5, hit: 1900, miss: 150, out: 25},
    {provider: 'deepseek-account', model: 'deepseek-flash', hour: 6, hit: 0, miss: 10, out: 1},
    {provider: 'deepseek-account', model: 'deepseek-v4-pro', hour: 6, hit: 7, miss: 7, out: 7}]});
  assert.ok(!JSON.stringify(s.snapshot()).includes('SECRET'));
  assert.deepEqual(s.snapshot().features, ['turn-usage']);
  assert.equal(s.snapshot().sessions[0].usage, undefined);
});
test('a new turn starts from zero and odd values are not trusted', () => {
  const s = new PetState(() => 10);
  const e = (type, data = {}) => s.accept(session, {type, data, time: 0});
  e('turn/start', {turn: 1}); e('assistant/message', used(5, 5, 5)); e('turn/end', {turn: 1, reason: {kind: 'completed'}});
  e('turn/start', {turn: 2});
  e('assistant/message', {...used(-3, 1.5, 'x', 'evil provider!', 'm'.repeat(99)), turn: 2});
  e('turn/end', {turn: 2, reason: {kind: 'completed'}});
  assert.deepEqual(s.events[1].usage.tokens, [{provider: '', model: '', hour: 0, hit: 0, miss: 0, out: 0}]);
});
test('subagents bill the active parent turn, and successful web searches and fetches are counted', () => {
  const s = new PetState(() => 10);
  const e = (type, data = {}, who = session) => s.accept(who, {type, data, time: 0});
  const sub = {id: 'child', header: {origin: 'subagent', parentSession: 'session-a'}};
  e('turn/start', {turn: 1});
  e('tool/call', {turn: 1, callId: 's1', name: 'web_search'}); e('tool/result', {turn: 1, message: {toolCallId: 's1'}});
  e('tool/call', {turn: 1, callId: 'f1', name: 'web_fetch'}); e('tool/result', {turn: 1, message: {toolCallId: 'f1', isError: true}});
  e('turn/start', {turn: 1}, sub); e('assistant/message', used(40, 4, 400), sub);
  e('tool/call', {turn: 1, callId: 'f2', name: 'web_fetch'}, sub); e('tool/result', {turn: 1, message: {toolCallId: 'f2'}}, sub);
  assert.equal(s.sessions.size, 1);
  e('turn/end', {turn: 1, reason: {kind: 'completed'}});
  e('assistant/message', used(1, 1, 1), sub);
  assert.deepEqual(s.events[0].usage, {search: 1, fetch: 1,
    tokens: [{provider: 'deepseek-account', model: 'deepseek-flash', hour: 0, hit: 400, miss: 40, out: 4}]});
});
test('ordinary forked conversations are observed, old turn endings are ignored', () => {
  const s=new PetState(() => 10), fork={id:'fork',header:{parentSession:'parent'}};
  s.accept(fork,{type:'turn/start',data:{turn:2}});
  s.accept(fork,{type:'turn/end',data:{turn:1,reason:{kind:'completed'}}});
  assert.equal(s.snapshot().sessions[0].active,true); assert.equal(s.events.length,0);
  s.accept(fork,{type:'turn/end',data:{turn:2,reason:{kind:'completed'}}});
  assert.equal(s.events.length,1);
});
