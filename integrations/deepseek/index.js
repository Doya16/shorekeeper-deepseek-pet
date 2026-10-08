import {mkdirSync, writeFileSync, renameSync, statSync} from 'node:fs';
import {join} from 'node:path';
import {homedir} from 'node:os';
import {randomUUID} from 'node:crypto';
import {PetState, safeBalance} from './state.js';

export const name = 'shorekeeper-pet';
export const inject = ['sessions', 'deepseekAccount'];

export function apply(ctx) {
  const home = process.env.DSH_HOME || join(homedir(), '.dsh');
  const dir = join(home, 'shorekeeper-pet');
  const path = join(dir, 'desktop.json'), request = join(dir, 'refresh');
  const state = new PetState(), instance = randomUUID();
  let balance = {status: 'loading', wallets: [], bonus: []}, updated = 0;
  let disposed = false, busy = false, lastBalance = 0, lastRequest = 0, accountEpoch = 0;
  function flush(connected = true) {
    if (disposed && connected) return;
    try {
      mkdirSync(dir, {recursive: true});
      writeFileSync(path + '.tmp', JSON.stringify({schema: 1, backend: 'deepseek-harness',
        instance, connected, updated_at: Date.now() / 1000, ...state.snapshot(),
        balance: {...balance, updated_at: updated}}), {mode: 0o600});
      renameSync(path + '.tmp', path);
    } catch { /* A pet export failure must never interrupt a user's task. */ }
  }
  async function refresh() {
    if (busy || disposed) return;
    busy = true; lastBalance = Date.now();
    const epoch = accountEpoch;
    try {
      const value = await ctx.deepseekAccount.getBalance({version: '0.2.0-rc.2', locale: 'zh-CN',
        timezoneOffsetSeconds: -new Date().getTimezoneOffset() * 60});
      if (!disposed && epoch === accountEpoch) { balance = safeBalance(value); updated = Date.now() / 1000; }
    } catch { if (!disposed && epoch === accountEpoch) balance = {status: 'unavailable', wallets: [], bonus: []}; }
    finally { busy = false; flush(); }
  }
  ctx.on('session/event', (session, event) => {
    try { state.accept(session, event); } catch { /* Ignore unsupported event shape. */ }
  });
  ctx.on('deepseek-account/signed-out', () => {
    accountEpoch++;
    balance = {status: 'signed-out', wallets: [], bonus: []}; updated = Date.now() / 1000; flush();
  });
  ctx.effect(() => {
    flush(); void refresh();
    const timer = setInterval(() => {
      let requested = 0;
      try { requested = statSync(request).mtimeMs; } catch {}
      if (Date.now() - lastBalance > 120000 || (requested > lastRequest && Date.now() - lastBalance > 5000)) {
        lastRequest = requested; void refresh();
      }
      flush();
    }, 500);
    timer.unref();
    return () => { disposed = true; clearInterval(timer); flush(false); };
  });
}
