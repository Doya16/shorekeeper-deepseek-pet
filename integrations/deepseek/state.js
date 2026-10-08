// Deliberately project identifiers and lifecycle only: never prompts, arguments,
// reasoning, result bodies, credentials, workspace paths or account profiles.
export function toolPhase(name = '') {
  if (/ask_user|request_user|permission|approval/.test(name)) return 'waiting';
  if (/edit|write|patch|replace|create_file/.test(name)) return 'writing';
  if (/read|search|browse|fetch|grep|glob|list|view|find/.test(name)) return 'reading';
  return 'working';
}

export class PetState {
  constructor(clock = () => Date.now() / 1000) {
    this.clock = clock; this.sessions = new Map(); this.events = []; this.sequence = 0;
  }
  phase(row) {
    const tools = [...row.tools.values()];
    return row.approvals.size || tools.includes('waiting') ? 'waiting' : tools.at(-1) || 'thinking';
  }
  accept(session, event) {
    if (!session?.id || session.header?.origin === 'subagent') return;
    const type = event.type, d = event.data || {}, now = this.clock();
    let row = this.sessions.get(session.id);
    if (type === 'turn/start') {
      if (row?.turn_id === String(d.turn)) return;
      row = {thread_id: session.id, title: row?.title || `DeepSeek 会话 ${this.sessions.size + 1}`,
        turn_id: String(d.turn), state: 'thinking', active: true, started: now,
        ended: 0, last_event: now, revision: 0, tools: new Map(), approvals: new Set()};
      this.sessions.set(session.id, row);
    }
    if (!row || !row.active) return;
    if (d.turn !== undefined && String(d.turn) !== row.turn_id) return;
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
        this.events.push({state: row.state, thread_id: row.thread_id, title: row.title,
          turn_id: row.turn_id, started: row.started, ended: now, seq: ++this.sequence});
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
    return {sessions: [...this.sessions.values()].map(({tools, approvals, held, hold_until, ...r}) => ({
      ...r, state: r.active && r.state === 'thinking' && now < hold_until ? held : r.state,
      message: '', stale: false,
    })), events: this.events, sequence: this.sequence};
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
