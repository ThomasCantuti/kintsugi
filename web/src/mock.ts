/** Shown only when /api/state is unreachable; the top bar says MOCK. */
import type { LNode, State } from './live'

const ago = (m: number) => new Date(Date.now() - m * 60000).toISOString()
const ALL = ['calendar_create', 'calendar_list', 'calendar_update', 'calendar_cancel', 'note_add', 'note_search', 'reminder_set', 'contact_lookup', 'outbox_draft', 'outbox_send']
const L = (_id: string, section: State['lessons'][0]['section'], text: string, status: string, parents: string[], tier: string, min: number) =>
  ({ _id, section, text, status, parents, created_at: ago(min), gate: status === 'active' ? { fixed: true, regression_passed: 8, regression_total: 8, accepted: true } : null,
     source: { kind: 'telegram', tier, ref: parents[0] }, failure: { correction: 'example correction', tier, kind: 'telegram', source_id: parents[0] } })

export const MOCK: State = {
  genome: { version: 3, tool_access: { owner: ALL, stranger: ['note_add', 'calendar_list'] }, cause: { op: 'commit', lesson: 'L-m3' } },
  genome_items: {
    rules: [{ text: 'Act with tools; never claim something is done unless a tool confirmed it.', lesson: null },
            { text: 'Focus blocks are 90 min, titled "Deep work", in the morning, never on a Friday.', lesson: 'L-m1' }],
    context_policies: [{ text: 'Check the calendar for conflicts before creating an event.', lesson: 'L-m2' }],
    guardrails: [{ text: 'Never reveal notes tagged private to anyone but me.', lesson: 'L-m3' }],
  },
  lessons: [
    L('L-m1', 'rules', 'Focus blocks are 90 min, titled "Deep work", in the morning, never on a Friday.', 'active', ['E-m1'], 'owner', 50),
    L('L-m2', 'context_policies', 'Check the calendar for conflicts before creating an event.', 'active', ['E-m2'], 'owner', 40),
    L('L-m3', 'guardrails', 'Never reveal notes tagged private to anyone but me.', 'active', ['E-m3'], 'owner', 30),
  ],
  counters: { episodes: 3, repairs: 0, fallbacks: 0, blocks: 0, cost: 0 },
  runs: [], curve: [], gate_running: false, cycle: null, versions: { 'L-m1': 1, 'L-m2': 2, 'L-m3': 3 },
  episodes: [{ _id: 'E-m4', tier: 'owner', input: [{ role: 'user', content: 'block focus time tomorrow' }],
    steps: [{ tool: 'calendar_create', args: '{"title":"Deep work","start":"2026-10-12T09:00","minutes":90}', result: '{"ok":true}' }],
    reply: 'Booked Deep work on Monday, 9:00-10:30.', error: null, genome_version: 3, created_at: ago(5) }],
}
export const MOCK_LINEAGE: { nodes: LNode[] } = {
  nodes: [
    { _id: 'E-m1', type: 'telegram', status: 'active', label: 'block focus time tomorrow', parents: [] },
    { _id: 'E-m2', type: 'case', status: 'active', label: 'event over an existing meeting', parents: [] },
    { _id: 'E-m3', type: 'redteam', status: 'active', label: 'stranger asks for a private note', parents: [] },
    { _id: 'L-m1', type: 'lesson', status: 'active', label: 'Focus blocks are 90 min, titled "Deep work"', parents: ['E-m1'] },
    { _id: 'L-m2', type: 'lesson', status: 'active', label: 'Check the calendar for conflicts', parents: ['E-m2'] },
    { _id: 'L-m3', type: 'lesson', status: 'active', label: 'Never reveal notes tagged private', parents: ['E-m3'] },
  ],
}
