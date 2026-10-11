/** Raindrop: every live turn Raindrop flagged, told end to end. What Tsugi did, Raindrop's flag, the lessons Kintsugi
 *  proposed, what the gate decided, what shipped. All from GET /api/raindrop (Atlas); private notes are blanked server-side. */
import { useEffect, useRef, useState } from 'react'
import { api, CAUGHT_TIP, letter, parseT, RAINDROP_URL, SEC, type Flagged, type State } from './live'

const time = (s?: string) => s ? new Date(parseT(s)).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }) : ''
const secs = (a?: string, b?: string) => a && b ? Math.round((parseT(b) - parseT(a)) / 1000) : null
const dur = (s: number | null) => s == null ? '' : s < 90 ? `${s} s` : `${Math.floor(s / 60)} min ${s % 60} s`

/** The reply with each blanked private note marked, scrolled so the first one shows (the leak, not the prompt, is the point). */
function Reply({ text }: { text: string }) {
  const ref = useRef<HTMLPreElement>(null)
  useEffect(() => {
    const pre = ref.current, m = pre?.querySelector('mark')
    if (pre && m) pre.scrollTop = m.offsetTop - pre.clientHeight / 3
  }, [text])
  const parts = text.split('[private note]')
  return <pre ref={ref} className="code rreply">{parts.map((p, i) => <span key={i}>{p}{i < parts.length - 1 && <mark>[private note]</mark>}</span>)}</pre>
}

function Case({ f, versions, onLesson }: { f: Flagged; versions: State['versions']; onLesson: (id: string) => void }) {
  const first = f.cycles[0], byId = new Map(f.lessons.map(l => [l._id, l]))
  const cands = (first?.lessons ?? f.lessons.map(l => l._id)).filter(id => byId.has(id))
  const lastCycle = (id: string) => f.cycles.findLastIndex(c => c.lessons?.includes(id))
  const tested = f.lessons.filter(l => l.gate).sort((a, b) => lastCycle(a._id) - lastCycle(b._id))
  const shipped = f.lessons.find(l => versions[l._id] != null)
  const status = (id: string) => {
    const l = byId.get(id)!
    return versions[id] != null ? (l.status === 'revoked' ? 'revoked' : `shipped v${versions[id]}`)
      : l.status === 'skipped' ? 'not tested' : l.status === 'quarantined' ? 'waiting for Thomas' : l.status
  }
  const falseAlarm = first?.status === 'false_alarm'
  return (
    <ol className="rsteps">
      <li className="rstep broke" style={{ ['--i' as string]: 0 }}>
        <span className="rk">1 · Tsugi got it wrong</span>
        <p className="mute rmeta">{f.tier} · genome v{f.genome_version ?? '?'} · {time(f.created_at)}</p>
        <p className="quote">“{f.message}”</p>
        <p>{f.tools.length ? <>Ran <code>{f.tools.join(', ')}</code>, then replied</> : 'Replied'}
          {f.leaked_private > 0 && <> with <b className="bad">{f.leaked_private} private note{f.leaked_private === 1 ? '' : 's'}</b></>}:</p>
        <Reply text={f.reply || '(no reply)'} />
        {f.leaked_private > 0 && <p className="mute rsmall">Private notes are hidden on this page. Raindrop saw the real reply.</p>}
      </li>
      <li className="rstep flag" style={{ ['--i' as string]: 1 }}>
        <span className="rk">2 · Raindrop flagged it</span>
        <div className="rflags">{f.flags.map(x => <a key={x} className="rchip" href={RAINDROP_URL} target="_blank" rel="noreferrer">🌧️ {x}</a>)}</div>
        {f.flag_latency_s != null && <p className="rbig" title={CAUGHT_TIP}><b className="num">{f.flag_latency_s} s</b><span className="mute">from the turn to the flag</span></p>}
        <p>Nobody had 👎'd this turn. Raindrop's classifiers caught it on their own, and Kintsugi reads the flags from Raindrop's API every minute.</p>
      </li>
      <li className="rstep" style={{ ['--i' as string]: 2 }}>
        <span className="rk">3 · Kintsugi wrote a fix</span>
        {falseAlarm ? <p>The supervisor checked the turn against its own correction: Tsugi already did the right thing. <b>False alarm, no lesson.</b></p> : <>
          {first?.correction && <><p className="mute rsmall">The supervisor's correction:</p><p className="quote">“{first.correction}”</p></>}
          <p>{cands.length} candidate lesson{cands.length === 1 ? '' : 's'}{secs(first?.created_at, first?.ended_at) != null ? ` in ${secs(first?.created_at, first?.ended_at)} s` : ''}
            {f.tier === 'stranger' ? '. It came from a stranger\'s turn, so Thomas picks which to test (✅/❌ on Telegram).' : '.'}</p>
          <ul className="rcands">{cands.map((id, i) => <li key={id}><b>{letter(i)}</b> {byId.get(id)!.title || byId.get(id)!.text}
            <span className={'tag ' + byId.get(id)!.status}>{status(id)}</span></li>)}</ul>
        </>}
      </li>
      <li className="rstep" style={{ ['--i' as string]: 3 }}>
        <span className="rk">4 · The gate tested it</span>
        {!tested.length ? <p className="mute">{falseAlarm ? 'Nothing to test.' : 'No candidate tested yet.'}</p> : <>
          <p className="mute rsmall">Each lesson replays the flagged turn on a copy of the live data, then re-runs past cases that passed before.</p>
          {tested.map(l => {
            const c = f.cycles[lastCycle(l._id)], g = l.gate!
            return <div key={l._id} className={'rverdict ' + (g.accepted ? 'ok' : 'no')}>
              <p><span className="rmark" aria-hidden="true">{g.accepted ? '✓' : '✗'}</span>
                {f.tier === 'stranger' && <span className="mute">Thomas ✅ {letter(cands.indexOf(l._id))} · </span>}<b>{l.title || l.text}</b></p>
              <p className="rsmall">{g.accepted ? 'Accepted' : 'Rejected'}: {g.why}</p>
              <p className="mute rsmall">{g.fixed ? 'turn fixed' : 'turn not fixed'} · {g.regression_total ? `past cases ${g.regression_passed}/${g.regression_total}` : 'past cases not run'}{c ? ` · ${dur(secs(c.created_at, c.ended_at))}` : ''}</p>
            </div>
          })}
        </>}
      </li>
      <li className={'rstep ' + (shipped ? 'ship' : '')} style={{ ['--i' as string]: 4 }}>
        <span className="rk">5 · {shipped ? 'Shipped' : 'Not shipped'}</span>
        {shipped ? <>
          <p className="rbig"><b>Seam {versions[shipped._id]}</b><span className="mute">genome v{versions[shipped._id]} · {SEC[shipped.section]}</span></p>
          <p className="itext">{shipped.title || shipped.text}</p>
          <p className="mute rsmall">{shipped.text}</p>
          {f.scar && <p>Now a scar: while this lesson is active, every later gate replays this turn as a test.</p>}
          <button className="btn primary" type="button" onClick={() => onLesson(shipped._id)} style={{ justifySelf: 'start' }}>See it in Lineage</button>
        </> : <p className="mute">{falseAlarm ? 'Raindrop flagged it, Kintsugi checked, nothing needed fixing.' : 'No lesson from this flag has passed the gate yet.'}</p>}
      </li>
    </ol>
  )
}

export default function Raindrop({ state, visible, onLesson }: { state: State; visible: boolean; onLesson: (id: string) => void }) {
  const [flagged, setFlagged] = useState<Flagged[] | null>(null), [err, setErr] = useState('')
  useEffect(() => {
    if (!visible) return
    api.raindrop().then(r => { setFlagged(r.flagged); setErr('') }, e => setErr((e as Error).message))
  }, [visible, state])
  const all = flagged ?? [], lessons = all.flatMap(f => f.lessons)
  const shipped = lessons.filter(l => state.versions[l._id] != null).length, rejected = lessons.filter(l => l.status === 'rejected').length
  return (
    <div className="scene raindrop">
      <div className="lhead">
        <h2>Raindrop sees it. Kintsugi fixes it.</h2>
        <p>Raindrop watches every live turn and flags the ones that went wrong, even when nobody complained.
          Kintsugi turns each flag into a lesson, and the lesson ships only if the gate passes it.</p>
        {flagged && <p className="mute rsmall">{all.length} flagged turn{all.length === 1 ? '' : 's'} · {shipped} lesson{shipped === 1 ? '' : 's'} shipped · {rejected} rejected by the gate · eval and gate runs are never sent to Raindrop</p>}
      </div>
      {err ? <p className="mute">Raindrop view unavailable: {err}</p>
        : !flagged ? <p className="empty">Loading…</p>
        : !all.length ? <p className="empty">No Raindrop flags yet. Flagged live turns show up here within a minute.</p>
        : <div className="rcases">{all.map(f => <Case key={f._id} f={f} versions={state.versions} onLesson={onLesson} />)}</div>}
    </div>
  )
}
