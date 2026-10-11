/** One live store: /api/state plus the Atlas change stream (SSE). Every event refetches the state. */
import { useSyncExternalStore } from 'react'

export type Section = 'rules' | 'context_policies' | 'guardrails' | 'tool_access'
export type Verdict = { fixed: boolean; why?: string; regression_passed: number; regression_total: number; accepted: boolean }
export type Lesson = {
  _id: string; section: Section; text: string; status: string; created_at: string
  parents: string[]; gate: Verdict | null; prediction?: string
  source: { kind: string; tier: string; ref: string }
  failure?: { correction?: string; tier?: string; kind?: string; source_id?: string }
  similar?: { _id: string; score: number }[]; duplicate_of?: string
  tier?: string; tools?: string[]; allow?: boolean; only?: boolean; title?: string
}
export type ToolStep = { tool: string; args: string; result: string }
export type LiveStep = { tool: string; status: 'ok' | 'denied' | 'error' }
export type Episode = {
  _id: string; tier: string; input: { role: string; content: string }[]; steps: ToolStep[]
  reply: string; error: string | null; genome_version: number | null; created_at: string
}
export type Progress = { lesson: string; cases?: string[]; case?: string; passed?: boolean; retry?: boolean }
export type Cycle = {
  _id: string; status: string; source?: string; kind?: string; tier?: string; correction?: string | null
  lessons?: string[]; progress?: Progress[]; version?: number; why?: string; created_at: string; ended_at?: string
  flags?: string[]; flag_latency_s?: number
}
export type Run = {
  _id: string; label: string; split: string; model: string; genome_version: number | null
  n: number; passed: number; pass_rate: number; cost: number; trials?: number; trial_passed?: number[]; created_at: string
}
export type GenomeItem = { text: string; lesson: string | null }
export type State = {
  genome: { version: number; tool_access: Record<string, string[]>; created_at?: string; cause?: { op: string; lesson?: string; node?: string; revoked?: string[] } }
  genome_items: Record<'rules' | 'context_policies' | 'guardrails', GenomeItem[]>
  lessons: Lesson[]
  counters: { episodes: number; repairs: number; fallbacks: number; blocks: number; cost: number }
  runs: Run[]; curve: { version: number; pass_rate: number; n: number }[]
  gate_running: boolean; episodes: Episode[]; cycle: Cycle | null; versions: Record<string, number>
  sandbox?: boolean  // the judges' copy: web visitors are the owner
}
/** A live turn Raindrop flagged (GET /api/raindrop): what Tsugi did, the flag, the cycles it started, their lessons. */
export type Flagged = {
  _id: string; flags: string[]; flag_latency_s?: number; tier: string; genome_version: number | null; created_at: string
  message: string; tools: string[]; reply: string; leaked_private: number; cycles: Cycle[]
  lessons: Pick<Lesson, '_id' | 'title' | 'text' | 'section' | 'status' | 'gate' | 'created_at'>[]; scar: boolean
}
/** A run re-sent to Raindrop: its flags vs the deterministic checks (caught = flagged failures, false alarms = flagged passes). */
export type Agreement = { _id: string; label: string; split: string; model: string; genome_version: number | null
  raindrop_agreement: { n: number; failed: number; caught: number; passed: number; false_alarms: number; by_signal: Record<string, number> } }
export type LiveEvent = { coll: string; op: string; id: string; note?: string; t: number }
export type LNode = { _id: string; type: string; status: string; label: string; parents?: string[]; flags?: string[]; flag_latency_s?: number }
export type Conn = 'connecting' | 'live' | 'reconnecting' | 'mock'
type Snap = { state: State | null; events: LiveEvent[]; conn: Conn }

let snap: Snap = { state: null, events: [], conn: 'connecting' }
const subs = new Set<() => void>()
const set = (patch: Partial<Snap>) => { snap = { ...snap, ...patch }; subs.forEach(f => f()) }
const subscribe = (f: () => void) => { subs.add(f); return () => { subs.delete(f) } }
export const useLive = () => useSyncExternalStore(subscribe, () => snap)

async function getState(): Promise<State> {
  const r = await fetch('/api/state')
  if (!r.ok) throw new Error(`/api/state ${r.status}`)
  return r.json()
}
let timer = 0
async function refresh() {
  try { set({ state: await getState() }) } catch { if (snap.conn !== 'mock') set({ conn: 'reconnecting' }) }
}
export function refreshSoon(ms = 250) { clearTimeout(timer); timer = window.setTimeout(refresh, ms) }

export async function start() {
  try { set({ state: await getState() }) } catch {
    const { MOCK } = await import('./mock')  // server unreachable: labelled mock data, never mixed with live data
    set({ state: MOCK, conn: 'mock' })
    return
  }
  const es = new EventSource('/api/events')
  es.onopen = () => set({ conn: 'live' })
  es.onerror = () => set({ conn: 'reconnecting' })
  es.onmessage = e => {
    try {
      const ev = JSON.parse(e.data)
      set({ events: [{ coll: ev.coll ?? ev.type, op: ev.op, id: ev.id, note: ev.note, t: Date.now() }, ...snap.events].slice(0, 40) })
      refreshSoon()
    } catch { /* ping or malformed: ignore */ }
  }
}

async function post(path: string, body?: unknown) {
  if (snap.conn === 'mock') throw new Error('server unreachable (mock data)')
  const r = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: body ? JSON.stringify(body) : undefined })
  const data = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(data.detail || `${r.status} ${path}`)
  refreshSoon(0)
  return data
}
export const api = {
  revoke: (id: string): Promise<{ revoked: string[]; version: number }> => post(`/api/revoke/${encodeURIComponent(id)}`),
  quarantine: (id: string, d: 'approve' | 'reject') => post(`/api/quarantine/${encodeURIComponent(id)}/${d}`),
  /** Streams the turn (NDJSON): onStep for each tool call as it happens, then the reply. */
  chat: async (text: string, tier = 'stranger', onStep?: (s: LiveStep) => void): Promise<{ reply: string; episode_id: string }> => {
    if (snap.conn === 'mock') throw new Error('server unreachable (mock data)')
    const r = await fetch('/api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text, tier }) })
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `${r.status} /api/chat`)
    const rd = r.body!.pipeThrough(new TextDecoderStream()).getReader()
    let buf = ''
    for (;;) {
      const { value, done } = await rd.read()
      if (done) throw new Error('connection lost before the reply')
      buf += value
      let i
      while ((i = buf.indexOf('\n')) >= 0) {
        const m = JSON.parse(buf.slice(0, i)); buf = buf.slice(i + 1)
        if (m.step) onStep?.(m.step)
        else if (m.error) throw new Error(m.error)
        else { refreshSoon(0); return m }
      }
    }
  },
  teach: (text: string, tier = 'stranger') => post('/api/teach', { text, tier }),
  raindrop: async (): Promise<{ flagged: Flagged[]; agreement: Agreement | null }> => {
    if (snap.conn === 'mock') return { flagged: [], agreement: null }
    const r = await fetch('/api/raindrop')
    if (!r.ok) throw new Error(`/api/raindrop ${r.status}`)
    return r.json()
  },
  lineage: async (): Promise<{ nodes: LNode[] }> => {
    if (snap.conn === 'mock') return (await import('./mock')).MOCK_LINEAGE
    const r = await fetch('/api/lineage')
    if (!r.ok) throw new Error(`/api/lineage ${r.status}`)
    return r.json()
  },
}

export const SEC: Record<Section, string> = { rules: 'Rules', context_policies: 'Context policies', guardrails: 'Guardrails', tool_access: 'Tool access' }
export const letter = (i: number) => String.fromCharCode(65 + i)  // candidates are A, B, C for people
export const RAINDROP_URL = 'https://app.raindrop.ai'
export const CAUGHT_TIP = "From the turn to Kintsugi seeing Raindrop's flag (includes Kintsugi's poll interval)"
export const raindropText = (flags?: string[], s?: number) =>
  ['🌧️ Raindrop', flags?.length ? flags.join(', ') : '', s != null ? `caught in ${s} s` : ''].filter(Boolean).join(' · ')
export const parseT = (s?: string) => Date.parse(/[zZ]|[+-]\d\d:?\d\d$/.test(s || '') ? s! : (s || '') + 'Z')  // naive datetimes are UTC
export const lastUser = (ep: Episode) => [...ep.input].reverse().find(m => m.role === 'user')?.content ?? ''
