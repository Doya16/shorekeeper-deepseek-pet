// Deliberately project identifiers and lifecycle only: never prompts, arguments,
// reasoning, result bodies, credentials, workspace paths or account profiles.
export function toolPhase(name = '') {
  if (/ask_user|request_user|permission|approval/.test(name)) return 'waiting';
  if (/edit|write|patch|replace|create_file/.test(name)) return 'writing';
  if (/read|search|browse|fetch|grep|glob|list|view|find/.test(name)) return 'reading';
  return 'working';
}

// Billed per successful request, separately from tokens.
const PAID_TOOLS = {web_search: 'search', web_fetch: 'fetch'};
const count = v => Number.isSafeInteger(v) && v >= 0 ? v : 0;
const label = v => typeof v === 'string' && /^[\w.:/-]{1,64}$/.test(v) ? v : '';

function emptyUsage() { return {tokens: new Map(), search: 0, fetch: 0}; }

export class PetState {
  constructor(clock = () => Date.now() / 1000) {
    this.clock = clock; this.sessions = new Map(); this.events = []; this.sequence = 0; this.paidCalls = new Map();
  }
  phase(row) {
    const tools = [...row.tools.values()];
    return row.approvals.size || tools.includes('waiting') ? 'waiting' : tools.at(-1) || 'thinking';
  }
  // Token counts only: provider, model, the hour it ran (prices differ by time of day) and three numbers.
  addUsage(row, d, time) {
    const u = d.usage, source = d.message?.source || {};
    if (!u || typeof u !== 'object') return;
    const ms = Number.isFinite(time) ? time : this.clock() * 1000;
    const provider = label(source.provider), model = label(source.model), hour = Math.floor(ms / 3600000);
    const key = `${provider}|${model}|${hour}`;
    const entry = row.usage.tokens.get(key) || {provider, model, hour, hit: 0, miss: 0, out: 0};
    entry.hit += count(u.cacheReadTokens);
    entry.miss += count(u.inputTokens) + count(u.cacheWriteTokens);
    entry.out += count(u.outputTokens);
    row.usage.tokens.set(key, entry);
  }
  // Paid web tools are counted when they succeed.
  trackPaid(sessionId, type, d, row) {
    if (type === 'tool/call' && PAID_TOOLS[d.name]) {
      this.paidCalls.set(`${sessionId}:${d.callId}`, PAID_TOOLS[d.name]);
      if (this.paidCalls.size > 256) this.paidCalls.delete(this.paidCalls.keys().next().value);
    } else if (type === 'tool/result') {
      const key = `${sessionId}:${d.message?.toolCallId}`, kind = this.paidCalls.get(key);
      if (!kind) return;
      this.paidCalls.delete(key);
      if (row && !d.message?.isError) row.usage[kind]++;
    }
  }
  // A subagent bills the turn of the conversation that started it.
  acceptSubagent(session, event) {
    // Logs write the parent as "session-<id>"; accept either form.
    const parent = String(session.header?.parentSession || '');
    const row = this.sessions.get(parent) || this.sessions.get(parent.replace(/^session-/, ''));
    const target = row?.active ? row : null;
    if (event.type === 'assistant/message' && target) this.addUsage(target, event.data || {}, event.time);
    else this.trackPaid(session.id, event.type, event.data || {}, target);
  }
  accept(session, event) {
    if (!session?.id) return;
    if (session.header?.origin === 'subagent') { this.acceptSubagent(session, event); return; }
    const type = event.type, d = event.data || {}, now = this.clock();
    let row = this.sessions.get(session.id);
    if (type === 'turn/start') {
      if (row?.turn_id === String(d.turn)) return;
      row = {thread_id: session.id, title: row?.title || `DeepSeek 会话 ${this.sessions.size + 1}`,
        turn_id: String(d.turn), state: 'thinking', active: true, started: now,
        ended: 0, last_event: now, revision: 0, tools: new Map(), approvals: new Set(), usage: emptyUsage()};
      this.sessions.set(session.id, row);
    }
    if (!row || !row.active) return;
    if (d.turn !== undefined && String(d.turn) !== row.turn_id) return;
    if (type === 'assistant/message') { this.addUsage(row, d, event.time); return; }
    if (type === 'tool/call' || type === 'tool/result') this.trackPaid(session.id, type, d, row);
    if (type === 'step/start') row.state = this.phase(row);
    else if (type === 'tool/call' || type === 'tool/ptc-dispatch-start') {
      const id = d.subCallId || d.callId;
      const phase = toolPhase(d.name);
      row.tools.set(id, phase); row.state = this.phase(row);
      row.held = phase; row.hold_until = now + 1.8;
    } else if (type === 'tool/result' || type === 'tool/ptc-dispatch') {
      row.tools.delete(type === 'tool/result' ? d.message?.toolCallId : d.subCallId);
      row.state = this.phase(row);
    } else if (type === 'approval/asked') { row.approvals.add(d.id); row.state = 'waiting'; }
    else if (type === 'approval/decided') {
      row.approvals.delete(d.id); row.state = this.phase(row);
    } else if (type === 'turn/end') {
      const reason = d.reason?.kind;
      row.state = reason === 'completed' ? 'done' : reason === 'blocked' ? 'waiting' :
        reason === 'error' || reason === 'max-tokens' ? 'error' : 'paused';
      row.active = false; row.ended = now; row.tools.clear(); row.approvals.clear(); row.held = null;
      // Historical repair/fork closers are not fresh completion notifications.
      if (!['interrupted', 'forked'].includes(reason)) {
        const {tokens, search, fetch} = row.usage;
        this.events.push({state: row.state, thread_id: row.thread_id, title: row.title,
          turn_id: row.turn_id, started: row.started, ended: now, seq: ++this.sequence,
          usage: {tokens: [...tokens.values()], search, fetch}});
        this.events = this.events.slice(-512);
      }
    } else if (type !== 'turn/start' && type !== 'step/start') return;
    if (row.approvals.size && row.active) row.state = 'waiting';
    row.last_event = now; row.revision++;
    for (const [id, value] of this.sessions) {
      if (this.sessions.size <= 128) break;
      if (!value.active) this.sessions.delete(id);
    }
  }
  snapshot() {
    const now = this.clock();
    return {sessions: [...this.sessions.values()].map(({tools, approvals, held, hold_until, usage, ...r}) => ({
      ...r, state: r.active && r.state === 'thinking' && now < hold_until ? held : r.state,
      message: '', stale: false,
    })), events: this.events, sequence: this.sequence, features: ['turn-usage']};
  }
}

export function safeBalance(value) {
  if (!value) return {status: 'signed-out', wallets: [], bonus: []};
  if (value.status !== 'ready') return {status: 'unavailable', wallets: [], bonus: []};
  const clean = rows => (Array.isArray(rows) ? rows : []).filter(r =>
    ['CNY', 'USD'].includes(r.currency) && typeof r.balance === 'string' && r.balance.length < 80 && /^-?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d{1,3})?$/i.test(r.balance)
  ).map(r => ({currency: r.currency, balance: r.balance}));
  return {status: 'ready', wallets: clean(value.value), bonus: clean(value.bonusWallets)};
}
