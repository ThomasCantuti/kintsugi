/** The stage: the learning loop (left), Tsugi (centre), the Telegram mirror (right), the genome (floor).
 *  Everything here is derived from /api/state; the loop follows the latest learning-cycle doc in `gates`. */
import { animate, AnimatePresence, motion } from 'motion/react'
import { Fragment, memo, useEffect, useLayoutEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import { api, CAUGHT_TIP, lastUser, letter, parseT, RAINDROP_URL, raindropText, SEC, type Cycle, type Episode, type Lesson, type LiveEvent, type State, type ToolStep } from './live'
import Tsugi, { type Mood, type Ring } from './Tsugi'
import { PROMPTS } from './Tour'

const RM = matchMedia('(prefers-reduced-motion: reduce)').matches
const RECENT = 20_000

function useNow(ms = 1000) {
  const [now, setNow] = useState(Date.now())
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), ms); return () => clearInterval(t) }, [ms])
  return now
}

/** Count-up on change (Motion drives the text node, not React state). */
export function Count({ value, fmt = (v: number) => String(Math.round(v)) }: { value: number; fmt?: (v: number) => string }) {
  const el = useRef<HTMLSpanElement>(null), prev = useRef(0)
  useEffect(() => {
    const from = prev.current; prev.current = value
    if (RM || from === value) { el.current!.textContent = fmt(value); return }
    const c = animate(from, value, { duration: .9, ease: [.2, .9, .25, 1], onUpdate: v => { if (el.current) el.current.textContent = fmt(v) } })
    return () => c.stop()
  }, [value])  // eslint-disable-line react-hooks/exhaustive-deps
  return <span ref={el} className="num">{fmt(value)}</span>
}

/** Raindrop as the source of a cycle: its own signal names, how fast we caught the flag, a link to Raindrop. */
export function RaindropChip({ flags, s }: { flags?: string[]; s?: number }) {
  return <a className="rchip" href={RAINDROP_URL} target="_blank" rel="noreferrer" title={s != null ? CAUGHT_TIP : 'Open Raindrop'}>{raindropText(flags, s)}</a>
}

/* ---------- the learning cycle (latest `gates` doc + its lessons) ---------- */
type StepState = '' | 'active' | 'done' | 'bad' | 'skip'
type View = { cycle: Cycle; cands: Lesson[]; tested?: string; ring: Ring; who: string; tier: string; correction: string; ended: boolean }

function whoOf(c: Cycle) {
  if (c.kind === 'raindrop') return 'a Raindrop flag'
  if (c.kind === 'case' || c.kind === 'redteam' || c.source?.startsWith('case:')) return `case ${c.source?.replace(/^case:/, '')}`
  return c.tier === 'owner' ? 'Thomas' : c.tier === 'stranger' ? 'a stranger' : 'a failure'
}
const STALE = 5 * 60_000  // a cycle still "proposing"/"running" after this crashed: treat it as ended
function cycleView(state: State): View | null {
  const c = state.cycle
  if (!c) return null
  const byId = new Map(state.lessons.map(l => [l._id, l]))
  const cands = (c.lessons || []).map(id => byId.get(id)).filter((l): l is Lesson => !!l)
  const prog = c.progress || []
  let planAt = -1
  prog.forEach((p, i) => { if (p.cases) planAt = i })
  let ring: Ring = null, tested: string | undefined
  if (planAt >= 0) {
    const plan = prog[planAt]; tested = plan.lesson
    const results: Record<string, boolean> = {}
    for (const p of prog.slice(planAt + 1)) if (p.lesson === plan.lesson && p.case && p.passed !== undefined) results[p.case] = p.passed
    const done = c.status === 'accepted' ? 'accepted' : c.status === 'running' ? '' : 'rejected'
    ring = { key: `${c._id}:${plan.lesson}:${plan.cases!.join(',')}`, labels: plan.cases!, results, done }
  }
  const correction = c.correction || cands.find(l => l.failure?.correction)?.failure?.correction || ''
  const ended = !['proposing', 'running'].includes(c.status) || Date.now() - parseT(c.created_at) > STALE
  return { cycle: ended && ['proposing', 'running'].includes(c.status) ? { ...c, status: 'error' } : c,
           cands, tested, ring, who: whoOf(c), tier: c.tier || 'owner', correction, ended }
}

const CAND_LABEL: Record<string, string> = {
  candidate: 'candidate', active: 'shipped', rejected: 'rejected', quarantined: 'quarantined', skipped: 'untested',
  duplicate: 'already known', revoked: 'revoked',
}

function LoopRail({ view, state }: { view: View | null; state: State }) {
  const [busy, setBusy] = useState('')
  const [err, setErr] = useState('')
  const box = useRef<HTMLOListElement>(null)
  const c = view?.cycle
  const st = c?.status ?? ''
  const live = view?.cands.filter(l => l.status !== 'duplicate') ?? []
  const dups = view?.cands.filter(l => l.status === 'duplicate') ?? []
  const waiting = live.some(l => l.status === 'quarantined')  // the cycle stays 'quarantined' after Thomas says no to all
  const shipped = view?.cands.find(l => l.status === 'active' || (l.status === 'revoked' && c?.version))
  const version = c?.version ?? (shipped ? state.versions[shipped._id] : undefined)
  const swapped = !!version && state.genome.version >= version
  const testedIdx = view?.tested ? live.findIndex(l => l._id === view.tested) : -1
  const ring = view?.ring
  const ringDone = ring ? Object.keys(ring.results).length : 0
  const gatePass = ring ? ring.labels.slice(1).filter(l => ring.results[l]).length : 0

  const steps: { k: string; title: string; tag: string; state: StepState; open: boolean; sum: string; body?: React.ReactNode }[] = !view ? [] : [
    { k: 'signal', title: 'Signal', tag: c!.kind === 'raindrop' ? 'raindrop' : 'episodes', state: 'done', open: st === 'proposing' || st === 'false_alarm',
      sum: view.who,
      body: <><p>{c!.kind === 'raindrop' ? <RaindropChip flags={c!.flags} s={c!.flag_latency_s} />
        : <><span className={'src ' + view.tier}>{view.tier}</span> {c!.kind === 'telegram' ? (view.tier === 'owner' ? '👎 and replied:' : 'tried to teach:') : `${view.who} failed:`}</>}</p>
        {st === 'false_alarm' ? <p className="mute">False alarm: already correct{c!.why ? ` (${c!.why})` : ''}.</p>
          : view.correction ? <p className="quote">"{view.correction}"</p> : <p className="mute">Supervisor is writing the correction…</p>}</> },
    { k: 'propose', title: 'Propose', tag: 'supervisor', state: st === 'proposing' ? 'active' : view.cands.length ? 'done' : st === 'false_alarm' ? 'skip' : 'bad', open: st === 'proposing' || live.length > 0,
      sum: `${live.length} candidate${live.length === 1 ? '' : 's'}`,
      body: st === 'proposing' ? <p>Writing up to 3 candidate lessons…</p>
        : <div className="cands">
            <AnimatePresence initial={false}>
              {live.map((l, i) => (
                <motion.div key={l._id} layout data-cand={l._id} className={'cand ' + (l._id === view.tested && st === 'running' ? 'testing' : l.status)}
                  initial={RM ? false : { opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * .12, type: 'spring', stiffness: 260, damping: 26 }}>
                  <div className="ch"><span>{letter(i)} · {SEC[l.section].toLowerCase()}</span><span className="st">{l._id === view.tested && st === 'running' ? 'testing'
                    : l.status === 'active' && state.versions[l._id] != null ? `seam ${state.versions[l._id]}` : CAND_LABEL[l.status] ?? l.status}</span></div>
                  <p title={l.text}>{l.title || l.text}</p>
                </motion.div>))}
            </AnimatePresence>
          </div> },
    { k: 'dedup', title: 'Dedup', tag: '$vectorSearch', state: st === 'proposing' ? '' : view.cands.length ? 'done' : 'skip', open: false,
      sum: dups.length ? `${dups.length} already known` : (() => {
        const best = Math.max(0, ...view.cands.flatMap(l => (l.similar || []).map(s => s.score)))
        return best ? `new (closest ${best.toFixed(2)})` : 'new'
      })() },
    st === 'quarantined' || waiting
      ? { k: 'gate', title: 'Quarantine', tag: 'owner decides', state: 'bad', open: waiting, sum: waiting ? '' : 'Thomas said no',
          body: waiting && <><p>From a stranger, so Thomas picks one fix or none. The gate still tests it.</p>
            <div className="acts">
              {live.filter(l => l.status === 'quarantined').map(l => (
                <button key={l._id} className="btn primary" disabled={!!busy} onClick={() => decide(l._id)}>Approve {letter(live.indexOf(l))}</button>))}
              <button className="btn danger" disabled={!!busy} onClick={() => decide(null)}>None</button>
            </div>
            {err && <p className="verdict"><span className="no">{err}</span></p>}</> }
      : { k: 'gate', title: 'Gate', tag: 'train only', state: st === 'running' ? 'active' : st === 'accepted' ? 'done' : ['rejected', 'no_candidates'].includes(st) ? 'bad' : st === 'duplicate' ? 'skip' : '',
          open: st === 'running' || st === 'rejected',
          sum: st === 'accepted' && shipped?.gate ? `fixed, ${shipped.gate.regression_passed}/${shipped.gate.regression_total} past cases pass` : st === 'duplicate' ? 'nothing new' : st === 'rejected' ? 'no candidate passed' : '',
          body: <>
            {ring && <div className="gl"><b>{testedIdx >= 0 ? `Candidate ${letter(testedIdx)}` : 'Candidate'}</b><span className="num">{ring.results[ring.labels[0]] === undefined ? 'replaying' : `${gatePass}/${ring.labels.length - 1}`}</span></div>}
            <p className="mute">The failure, then past train cases. Never held-out.</p>
            <div className="verdict">{live.filter(l => l.gate).map(l => {
              const g = l.gate!, k = letter(live.indexOf(l)), broke = g.regression_total - g.regression_passed
              return g.accepted ? <span key={l._id} className="ok">{k} shipped: fixed, {g.regression_passed}/{g.regression_total} pass</span>
                : <span key={l._id} className="no">{k} rejected: {g.fixed ? `broke ${broke} past case${broke === 1 ? '' : 's'}` : 'not fixed'}</span>
            })}</div>
            {ringDone === 0 && st === 'running' && <p className="mute">Starting…</p>}
          </> },
    { k: 'commit', title: 'Commit', tag: 'transaction', state: st === 'accepted' ? 'done' : view.ended ? 'skip' : '', open: false,
      sum: st === 'accepted' && shipped ? `Seam ${version} · ${shipped.title || shipped._id}` : '' },
    { k: 'swap', title: 'Hot-swap', tag: 'change stream', state: st === 'accepted' ? (swapped ? 'done' : 'active') : view.ended ? 'skip' : '', open: st === 'accepted' && !swapped,
      sum: swapped ? `agent on v${state.genome.version}` : '', body: <p>Pushing to the running agent, no restart.</p> },
  ]

  async function decide(pick: string | null) {  // like the Telegram card: test one fix (the others drop only if it ships) or none
    setBusy('1'); setErr('')
    try {
      if (pick) await api.quarantine(pick, 'approve')
      else for (const l of live.filter(l => l.status === 'quarantined')) await api.quarantine(l._id, 'reject')
    } catch (e) { setErr(String((e as Error).message)) }
    setBusy('')
  }
  const activeKey = steps.find(s => s.state === 'active' || (s.open && s.state === 'bad'))?.k
  useEffect(() => {
    const b = box.current, li = activeKey && b?.querySelector<HTMLLIElement>(`[data-step="${activeKey}"]`)
    if (b && li && b.scrollHeight > b.clientHeight + 4) b.scrollTo({ top: li.offsetTop - 6, behavior: RM ? 'auto' : 'smooth' })
  }, [activeKey, c?._id])

  const sub = !view ? 'waiting for a signal' : view.ended
    ? (st === 'accepted' ? `last cycle shipped Seam ${version ?? ''}` : st === 'quarantined' ? (waiting ? 'waiting for Thomas' : 'last cycle: Thomas said no') : st === 'duplicate' ? 'last cycle: already known'
      : st === 'false_alarm' ? 'last cycle: false alarm' : 'last cycle: nothing shipped')
    : `learning from ${view.who}`
  return (
    <section className="loop" aria-label="The learning loop">
      <h2 className="ptitle">The loop <span className="sub">{sub}</span></h2>
      {!view ? <ol className="steps"><li className="step open"><span className="n">1</span><div>
        <div className="shead"><b>Signal</b><code>episodes</code></div>
        <div className="sdetail"><div><div className="in"><p>Starts on a 👎, a failed case, or a Raindrop flag.</p></div></div></div></div></li></ol>
        : <ol className="steps" ref={box}>
          {steps.map((s, i) => (
            <li key={s.k} data-step={s.k} className={`step ${s.state}${s.open ? ' open' : ''}`}>
              <span className="n">{i + 1}</span>
              <div>
                <div className="shead"><b>{s.title}</b><code>{s.tag}</code></div>
                <div className="ssum">{s.sum}</div>
                {s.body && <div className="sdetail"><div><div className="in">{s.body}</div></div></div>}
              </div>
            </li>))}
        </ol>}
    </section>
  )
}

/* ---------- Telegram mirror ---------- */
function parseArgs(s: string): [string, string][] {
  try {
    const o = JSON.parse(s || '{}')
    return Object.entries(o).slice(0, 5).map(([k, v]) => {
      const t = typeof v === 'string' ? `"${v}"` : JSON.stringify(v)
      return [k, t.length > 42 ? t.slice(0, 41) + '…' : t]
    })
  } catch { return [['args', (s || '').slice(0, 60)]] }
}
function resultLabel(s: ToolStep): [string, string] {
  const r = s.result || ''
  if (r.startsWith('DENIED')) return ['denied', 'denied']
  if (r.startsWith('ERROR')) return ['error', 'error']
  try { const j = JSON.parse(r); if (Array.isArray(j)) return ['', `${j.length} found`] } catch { /* not JSON */ }
  return ['', /create|add|set|draft|send|update|cancel/.test(s.tool) ? 'saved to Atlas' : 'ok']
}
const time = (iso: string) => { const t = parseT(iso); return isNaN(t) ? '' : new Date(t).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }

const Turn = memo(function Turn({ ep, tab, correction }: { ep: Episode; tab: string; correction?: string }) {
  const anim = RM ? {} : { initial: { opacity: 0, y: 8, scale: .97 }, animate: { opacity: 1, y: 0, scale: 1 }, transition: { type: 'spring' as const, stiffness: 300, damping: 26 } }
  const reply = ep.reply || (ep.error ? '' : '…')
  return (
    <>
      <motion.div className={'msg me' + (tab === 'stranger' ? ' stranger' : '')} {...anim}>
        <div className="who"><b>{tab === 'owner' ? 'Thomas' : 'stranger'}</b><span>{time(ep.created_at)}</span></div>{lastUser(ep)}
      </motion.div>
      <motion.div className="msg bot" {...anim} transition={{ ...anim.transition, delay: .15 }}>
        <div className="who"><b>Tsugi</b>{ep.genome_version != null && <span className="gv">genome v{ep.genome_version}</span>}</div>
        {ep.steps.map((s, i) => {
          const [cls, label] = resultLabel(s)
          return <div key={i} className={'call ' + cls}><div className="ch"><span className="fn">{s.tool}</span><span className="res">{label}</span></div>
            <div className="args">{parseArgs(s.args).map(([k, v]) => <span key={k}><i>{k}</i> {v}</span>)}</div></div>
        })}
        {reply && <div>{(reply.length > 280 ? reply.slice(0, 279) + '…' : reply).split(/\*\*(.+?)\*\*/).map((t, i) => i % 2 ? <b key={i}>{t}</b> : t)}</div>}
        {ep.error && <div className="err">{ep.error.slice(0, 160)}</div>}
        {correction !== undefined && <span className="react" aria-label="thumbs down">👎</span>}
      </motion.div>
      {correction && <motion.div className={'msg me' + (tab === 'stranger' ? ' stranger' : '')} {...anim}>
        <div className="who"><b>{tab === 'owner' ? 'Thomas' : 'stranger'}</b><span>correction</span></div>
        <div className="qref">{(ep.reply || '').replace(/\*\*/g, '').slice(0, 90)}</div>{correction}
      </motion.div>}
    </>
  )
})

function Transcript({ state }: { state: State }) {
  const eps = useMemo(() => [...state.episodes].sort((a, b) => parseT(a.created_at) - parseT(b.created_at)), [state.episodes])
  const corrections = useMemo(() => {
    const m: Record<string, string> = {}
    for (const l of state.lessons) if (l.failure?.source_id && l.failure.correction) m[l.failure.source_id] = l.failure.correction
    if (state.cycle?.source) m[state.cycle.source] = state.cycle.correction || m[state.cycle.source] || ''
    return m
  }, [state.lessons, state.cycle])
  const newest = eps.at(-1)
  const [tab, setTab] = useState<'owner' | 'stranger'>('owner')
  // the sandbox visitor is Thomas: stay on his tab even when the copied history ends on a stranger's turn
  useEffect(() => { if (newest && !state.sandbox) setTab(newest.tier === 'owner' ? 'owner' : 'stranger') }, [newest?._id])  // eslint-disable-line react-hooks/exhaustive-deps
  const logs = { owner: useRef<HTMLDivElement>(null), stranger: useRef<HTMLDivElement>(null) }
  const shown = eps.filter(e => (e.tier === 'owner') === (tab === 'owner'))
  useLayoutEffect(() => {
    const l = logs[tab].current, end = () => l?.scrollTo({ top: l.scrollHeight, behavior: RM ? 'auto' : 'smooth' })
    end(); document.fonts.ready.then(end)  // first load: web fonts reflow the log after the first scroll
  }, [shown.length, tab, corrections[shown.at(-1)?._id ?? '']])  // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <section className="chat" aria-label="Telegram mirror">
      <div className="chat-head">
        <h2 className="ptitle">Telegram</h2>
        <div className="seg" role="tablist" aria-label="Conversation">
          <button role="tab" aria-selected={tab === 'owner'} onClick={() => setTab('owner')}>Thomas</button>
          <button role="tab" className="str" aria-selected={tab === 'stranger'} onClick={() => setTab('stranger')}>Stranger</button>
        </div>
      </div>
      {(['owner', 'stranger'] as const).map(t => (
        <div key={t} ref={logs[t]} className={'log' + (t === 'stranger' ? ' str' : '')} hidden={tab !== t} aria-live="polite">
          {t === tab && (shown.length ? shown.slice(-14).map(ep => <Fragment key={ep._id}><Turn ep={ep} tab={t} correction={corrections[ep._id]} /></Fragment>)
            : <p className="empty">{t === 'owner' ? (state.sandbox ? 'Write to Tsugi as Thomas below.' : "Thomas's chats appear here live.") : 'Write as a stranger below.'}</p>)}
        </div>))}
      {(tab === 'stranger' || state.sandbox) && <Composer key={tab} tier={tab} sandbox={!!state.sandbox} />}
    </section>
  )
}

function Composer({ tier, sandbox }: { tier: 'owner' | 'stranger'; sandbox: boolean }) {  // owner only in the judges' sandbox
  const [text, setText] = useState(''), [rule, setRule] = useState(''), [note, setNote] = useState(''), [sending, setSending] = useState(false)
  const owner = tier === 'owner'
  async function go(e: FormEvent, kind: 'chat' | 'teach') {
    e.preventDefault()
    const t = (kind === 'chat' ? text : rule).trim(); if (!t) return
    setSending(true); setNote(kind === 'chat' ? 'Tsugi is answering…' : owner ? 'Sent. Watch the loop: the gate tests the fix (~2–4 min).' : 'Sent. Expect quarantine.')
    try { kind === 'chat' ? (await api.chat(t, tier), setText(''), setNote('')) : (await api.teach(t, tier), setRule('')) }
    catch (err) { setNote(String((err as Error).message)) }
    setSending(false)
  }
  return (
    <div className="composer">
      <form onSubmit={e => go(e, 'chat')}><input id={`${tier}-chat`} value={text} onChange={e => setText(e.target.value)} maxLength={500} placeholder={owner ? 'Write to Tsugi as Thomas' : 'Write to Tsugi as a stranger'} aria-label={`Message as ${owner ? 'Thomas' : 'stranger'}`} /><button className="btn primary" disabled={sending}>Send</button></form>
      <form onSubmit={e => go(e, 'teach')}><input id={`${tier}-teach`} value={rule} onChange={e => setRule(e.target.value)} maxLength={300} placeholder={owner ? '👎 Correct Tsugi’s last reply' : 'Teach a rule as the stranger'} aria-label={owner ? 'Correction to the last reply' : 'Rule taught by the stranger'} /><button className="btn danger" disabled={sending}>{owner ? '👎 Teach' : 'Teach'}</button></form>
      {sandbox && <div className="try" aria-label="Prompts to try">
        <span>Try:</span>
        {PROMPTS.filter(p => p.tier === tier).map(p => <button key={p.text} type="button" className="btn" title={p.text}
          onClick={() => { (p.box === 'chat' ? setText : setRule)(p.text); document.getElementById(`${tier}-${p.box}`)?.focus() }}>{p.label}</button>)}
      </div>}
      <p className="note" aria-live="polite">{note}</p>
    </div>
  )
}

/* ---------- genome ribbon ---------- */
function fly(fromEl: Element | null, toEl: HTMLElement | null) {
  if (RM || !fromEl || !toEl) return
  const a = fromEl.getBoundingClientRect(), b = toEl.getBoundingClientRect()
  if (!a.width || !b.width) return
  const c = fromEl.cloneNode(true) as HTMLElement
  c.classList.add('flying')
  Object.assign(c.style, { left: a.left + 'px', top: a.top + 'px', width: a.width + 'px', height: a.height + 'px' })
  document.body.appendChild(c); toEl.style.visibility = 'hidden'
  const dx = b.left - a.left, dy = b.top - a.top, sx = b.width / a.width, sy = b.height / a.height
  c.animate([{ transform: 'none', opacity: 1 }, { transform: `translate(${dx * .45}px,${dy * .45 - 70}px) scale(${(1 + sx) / 2},${(1 + sy) / 2})`, opacity: 1, offset: .5 },
    { transform: `translate(${dx}px,${dy}px) scale(${sx},${sy})`, opacity: .35 }], { duration: 1100, easing: 'cubic-bezier(.5,0,.2,1)' })
    .finished.finally(() => { c.remove(); toEl.style.visibility = ''; toEl.classList.add('land') })
}

function Genome({ state, events, onLesson }: { state: State; events: LiveEvent[]; onLesson: (id: string) => void }) {
  const items = state.genome_items, ta = state.genome.tool_access
  const byId = new Map(state.lessons.map(l => [l._id, l]))
  const ids = Object.values(items).flat().map(i => i.lesson).filter(Boolean) as string[]
  const prev = useRef<Set<string> | null>(null), root = useRef<HTMLDivElement>(null)
  useLayoutEffect(() => {
    const before = prev.current; prev.current = new Set(ids)
    if (!before) return
    for (const id of ids) if (!before.has(id)) {
      const li = root.current!.querySelector<HTMLLIElement>(`li[data-l="${id}"]`)
      if (!li) continue
      li.parentElement!.scrollTop = li.offsetTop - 4
      const card = document.querySelector(`[data-cand="${id}"]`)
      if (card && !RM) fly(card, li); else li.classList.add('land')
    }
  }, [ids.join('|')])  // eslint-disable-line react-hooks/exhaustive-deps
  const allTools = [...new Set(Object.values(ta).flat())]
  return (
    <section className="ribbon" aria-label="Genome">
      <div className="rhead"><h2 className="ptitle">Genome <span className="sub">edited only by lessons that pass the gate</span></h2></div>
      <div className="genome" ref={root}>
        {(['rules', 'context_policies', 'guardrails'] as const).map(s => (
          <div className="gcol" key={s}>
            <h3>{SEC[s]} <span>{items[s].length}</span></h3>
            <ul>
              <AnimatePresence initial={false}>
                {items[s].map(i => (
                  <motion.li key={i.lesson ?? i.text} data-l={i.lesson ?? undefined} className={i.lesson ? 'learned' : ''} layout="position"
                    exit={RM ? undefined : { opacity: 0, x: 18, transition: { duration: .8 } }}>
                    <span title={i.text}>{(i.lesson && byId.get(i.lesson)?.title) || i.text}</span>
                    {i.lesson && <button className="lid" onClick={() => onLesson(i.lesson!)} aria-label="Where this lesson came from">
                      {state.versions[i.lesson] != null ? `Seam ${state.versions[i.lesson]}` : 'lineage'}</button>}
                  </motion.li>))}
              </AnimatePresence>
              {!items[s].length && <li className="mute">empty</li>}
            </ul>
          </div>))}
        <div className="gcol">
          <h3>{SEC.tool_access}</h3>
          <div className="tiers">
            {Object.entries(ta).map(([tier, tools]) => (
              <div className="tier" key={tier}><b>{tier}</b>
                {allTools.map(t => <span key={t} className={'tool' + (tools.includes(t) ? '' : ' off')}>{t}</span>)}
              </div>))}
          </div>
        </div>
      </div>
      <Ticker events={events} />
    </section>
  )
}

function Ticker({ events }: { events: LiveEvent[] }) {
  return (
    <div className="ticker" aria-label="Atlas change stream">
      <span className="tl"><i />Atlas change stream</span>
      <ol>{events.map(e => <li key={e.t + e.id + e.op}><span className={'op ' + e.op}>{e.op}</span> {e.coll} {e.id}{e.note ? ' ' + e.note : ''}</li>)}
        {!events.length && <li className="mute">waiting for the first event</li>}</ol>
    </div>
  )
}

/* ---------- the stage ---------- */
export default function Stage({ state, events, onLesson }: { state: State; events: LiveEvent[]; onLesson: (id: string) => void }) {
  const now = useNow()
  const view = useMemo(() => cycleView(state), [state])
  const c = view?.cycle
  const endedAgo = c?.ended_at ? now - parseT(c.ended_at) : Infinity
  const ring = view?.ring && (c!.status === 'running' || endedAgo < 4000) ? view.ring : null
  const quarantined = state.lessons.some(l => l.status === 'quarantined')
  const g = state.genome
  const revokedAgo = g.cause?.op === 'revoke' && g.created_at ? now - parseT(g.created_at) : Infinity
  const mood: Mood = c && !view!.ended ? 'thinking'
    : c?.status === 'accepted' && endedAgo < 6000 ? 'happy'
    : quarantined || (c && ['rejected', 'no_candidates'].includes(c.status) && endedAgo < 6000) || revokedAgo < 4000 ? 'hurt' : 'idle'
  const live = state.lessons.filter(l => l.status === 'active').length
  const shipped = view?.cands.find(l => l.status === 'active')
  const testedIdx = view?.tested ? view.cands.filter(l => l.status !== 'duplicate').findIndex(l => l._id === view.tested) : -1
  const caption =
    c?.status === 'proposing' ? `Learning from ${view!.who}…`
    : c?.status === 'running' ? (ring ? `Gate: testing candidate ${letter(testedIdx)} on ${ring.labels.length} cases` : 'Gate: preparing…')
    : revokedAgo < RECENT ? `Revoked ${g.cause?.revoked?.length ?? 1}. Genome v${g.version} rebuilt.`
    : c?.status === 'accepted' && endedAgo < RECENT ? `Seam ${c.version} shipped: ${shipped?.title ?? ''}`
    : quarantined ? 'A stranger’s lesson waits for Thomas'
    : c && ['rejected', 'no_candidates'].includes(c.status) && endedAgo < RECENT ? 'Gate said no. Nothing changed.'
    : c?.status === 'duplicate' && endedAgo < RECENT ? 'Already known'
    : c?.status === 'false_alarm' && endedAgo < RECENT ? 'False alarm: already correct'
    : 'Tsugi is listening'
  const [flash, setFlash] = useState(false), lastV = useRef(g.version)
  useEffect(() => { if (g.version !== lastV.current) { lastV.current = g.version; setFlash(true); const t = setTimeout(() => setFlash(false), 1700); return () => clearTimeout(t) } }, [g.version])

  return (
    <div className="scene stage">
      <LoopRail view={view} state={state} />
      <section className="center" aria-label="Tsugi">
        <div style={{ position: 'relative', minHeight: 0, display: 'grid' }}>
          <Tsugi lessons={state.lessons} mood={mood} episodes={state.counters.episodes} ring={ring} onSeam={onLesson} />
          <div className={'gver' + (flash ? ' flash' : '')}>
            <small>genome</small>
            <b><AnimatePresence initial={false} mode="popLayout">
              <motion.span key={g.version} initial={{ y: '100%', opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: '-100%', opacity: 0 }} transition={{ type: 'spring', stiffness: 220, damping: 22 }}>v{g.version}</motion.span>
            </AnimatePresence></b>
          </div>
          <ul className="legend" aria-label="What Tsugi shows">
            <li><svg viewBox="0 0 24 12" aria-hidden="true"><path className="lg-leaf" d="M2,6 C7,0 16,0 22,6 C16,12 7,12 2,6Z" /></svg>Memory in Atlas</li>
            <li><svg viewBox="0 0 24 12" aria-hidden="true"><path className="lg-gold" d="M1,8 L7,4 L12,8 L17,3 L23,6" /></svg>Lesson that passed the gate</li>
            <li><svg viewBox="0 0 24 12" aria-hidden="true"><path className="lg-red" d="M1,4 L6,9 L11,3 L16,9 L23,5" /></svg>Stranger’s lesson, on hold</li>
            <li><svg viewBox="0 0 24 12" aria-hidden="true"><path className="lg-scar" d="M1,8 L7,4 L12,8 L17,3 L23,6" /></svg>Revoked lesson</li>
          </ul>
        </div>
        <AnimatePresence mode="wait" initial={false}>
          <motion.p key={caption} className="caption" aria-live="polite" initial={RM ? false : { opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }} transition={{ duration: .25 }}>{caption}</motion.p>
        </AnimatePresence>
        <dl className="counters">
          <div title="all runs, evals included"><dt>episodes</dt><dd><Count value={state.counters.episodes} /></dd></div>
          <div><dt>lessons</dt><dd><Count value={live} /></dd></div>
          <div title="bad tool calls caught and fixed"><dt>repairs</dt><dd><Count value={state.counters.repairs} /></dd></div>
          <div><dt>fallbacks</dt><dd><Count value={state.counters.fallbacks} /></dd></div>
          <div title="tool calls denied by tool access"><dt>blocked</dt><dd><Count value={state.counters.blocks} /></dd></div>
        </dl>
      </section>
      <Transcript state={state} />
      <Genome state={state} events={events} onLesson={onLesson} />
    </div>
  )
}
