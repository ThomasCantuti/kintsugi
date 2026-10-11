/** Lineage: every lesson points back to what caused it; revoke cascades through $graphLookup in one transaction. */
import { useEffect, useMemo, useRef, useState } from 'react'
import { api, CAUGHT_TIP, RAINDROP_URL, SEC, type LNode, type State } from './live'
import { RaindropChip } from './Stage'

const RM = matchMedia('(prefers-reduced-motion: reduce)').matches
const W = 214, H = 58, GX = 64, GY = 14
const SOURCE: Record<string, string> = { telegram: 'TELEGRAM', case: 'CASE', redteam: 'RED-TEAM CASE', raindrop: 'RAINDROP FLAG', episode: 'EPISODE' }

function layout(nodes: LNode[]) {
  const ids = new Set(nodes.map(n => n._id)), depth: Record<string, number> = {}
  nodes.forEach(n => { depth[n._id] = n.type === 'lesson' ? 1 : 0 })
  for (let k = 0; k < 6; k++) for (const n of nodes) for (const p of n.parents || []) if (ids.has(p)) depth[n._id] = Math.max(depth[n._id], depth[p] + 1)
  const cols: LNode[][] = []
  nodes.forEach(n => (cols[depth[n._id]] ??= []).push(n))
  const pos: Record<string, { x: number; y: number }> = {}
  const mid = (n: LNode) => { const ps = (n.parents || []).filter(p => pos[p]); return ps.length ? ps.reduce((s, p) => s + pos[p].y, 0) / ps.length : 0 }
  cols.forEach((col, c) => {
    if (!col) return
    if (c) col.sort((a, b) => mid(a) - mid(b))
    let y = 0
    for (const n of col) { const want = c ? Math.max(y, mid(n)) : y; pos[n._id] = { x: c * (W + GX), y: want }; y = want + H + GY }
  })
  const width = Math.max(W, cols.length * (W + GX) - GX), height = Math.max(H, ...Object.values(pos).map(p => p.y + H))
  return { pos, depth, width, height }
}

function descendants(nodes: LNode[], id: string) {
  const out = [id]
  for (let i = 0; i < out.length; i++) for (const n of nodes) if (n.parents?.includes(out[i]) && !out.includes(n._id)) out.push(n._id)
  return out.slice(1)
}

export default function Lineage({ state, selected, onSelect, visible, toast }:
  { state: State; selected: string | null; onSelect: (id: string) => void; visible: boolean; toast: (t: string) => void }) {
  const [all, setAll] = useState<LNode[]>([])
  const [err, setErr] = useState('')
  const [cascade, setCascade] = useState<string[]>([])
  const [running, setRunning] = useState(false)
  const svg = useRef<SVGSVGElement>(null)
  const key = state.genome.version + ':' + state.lessons.map(l => l.status[0]).join('')
  useEffect(() => {
    if (!visible || running) return
    api.lineage().then(d => { setAll(d.nodes); setErr('') }, e => setErr(String(e.message)))
  }, [visible, key, running])

  // lessons, and only the sources that something was learned from
  const nodes = useMemo(() => {
    const used = new Set(all.flatMap(n => n.type === 'lesson' ? n.parents || [] : []))
    return all.filter(n => n.type === 'lesson' || used.has(n._id))
  }, [all])
  const { pos, depth, width, height } = useMemo(() => layout(nodes), [nodes])
  const lessons = useMemo(() => new Map(state.lessons.map(l => [l._id, l])), [state.lessons])
  const byId = useMemo(() => new Map(nodes.map(n => [n._id, n])), [nodes])
  const sel = selected && byId.get(selected)?.type === 'lesson' ? selected
    : [...nodes].reverse().find(n => n.type === 'lesson' && n.status === 'active')?._id ?? null
  const l = sel ? lessons.get(sel) : undefined, node = sel ? byId.get(sel) : undefined
  const kids = sel ? descendants(nodes, sel) : []
  const liveKids = kids.filter(k => byId.get(k)?.status === 'active')
  const status = (n: LNode) => cascade.includes(n._id) ? 'revoked' : n.status
  const name = (id: string) => lessons.get(id)?.title || byId.get(id)?.label || id
  const seam = (id: string) => state.versions[id] != null ? `Seam ${state.versions[id]}` : ''
  const parents = (node?.parents || []).map(p => byId.get(p)).filter((p): p is LNode => !!p)

  async function revoke() {
    if (!sel || running) return
    setRunning(true)
    try {
      const res = await api.revoke(sel)
      const order = [...res.revoked].sort((a, b) => (depth[a] ?? 9) - (depth[b] ?? 9))
      for (const id of order) {
        setCascade(c => [...c, id])
        svg.current?.querySelector(`[data-id="${CSS.escape(id)}"]`)?.animate([{ transform: 'scale(1)' }, { transform: 'scale(1.06)' }, { transform: 'scale(1)' }], { duration: 550 })
        if (!RM) await new Promise(r => setTimeout(r, 480))
      }
      toast(`Revoked ${res.revoked.length} node${res.revoked.length === 1 ? '' : 's'}. Genome v${res.version} rebuilt.`)
    } catch (e) { toast('Revoke failed: ' + (e as Error).message) }
    await new Promise(r => setTimeout(r, 900))
    setCascade([]); setRunning(false)
  }

  return (
    <div className="scene lineage">
      <div className="lhead"><h2>Where every lesson came from</h2>
        <p>Revoke a lesson and everything built on it goes too.</p></div>
      <div className="graph">
        {err ? <p className="mute">Lineage unavailable: {err}</p> : !nodes.length ? <p className="mute">No lessons yet. A 👎 + correction on Telegram starts one.</p> :
          <svg ref={svg} viewBox={`-4 -4 ${width + 8} ${height + 8}`} style={{ maxWidth: width + 8 }} role="img" aria-label="Lineage graph">
            {nodes.flatMap(n => (n.parents || []).filter(p => pos[p]).map(p => {
              const a = pos[p], b = pos[n._id], x1 = a.x + W, y1 = a.y + H / 2, x2 = b.x, y2 = b.y + H / 2, m = (x1 + x2) / 2
              return <path key={p + '>' + n._id} className={'edge' + (status(n) === 'revoked' && cascade.includes(n._id) ? ' bad' : '')} d={`M${x1},${y1} C${m},${y1} ${m},${y2} ${x2},${y2}`} />
            }))}
            {nodes.map(n => {
              const p = pos[n._id], lesson = n.type === 'lesson', rain = n.type === 'raindrop'
              const full = lesson ? name(n._id) : rain && n.flags?.length ? n.flags.join(', ') : n.label
              const label = full.length > 31 ? full.slice(0, 30) + '…' : full
              const k = lesson ? [seam(n._id), status(n)].filter(Boolean).join(' · ').toUpperCase()
                : rain ? `🌧️ RAINDROP${n.flag_latency_s != null ? ` · CAUGHT IN ${n.flag_latency_s} S` : ''}` : SOURCE[n.type] ?? n.type.toUpperCase()
              const box = (

                <g key={n._id} data-id={n._id} className={`gn ${lesson ? 'lesson' : 'source'} t-${n.type} ${status(n)}${n._id === sel ? ' sel' : ''}`}
                  style={{ transformBox: 'fill-box', transformOrigin: 'center' }}
                  tabIndex={lesson ? 0 : -1} role={lesson ? 'button' : undefined} aria-label={n.label}
                  onClick={() => lesson && onSelect(n._id)} onKeyDown={e => { if (lesson && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); onSelect(n._id) } }}>
                  <title>{rain ? `${full}\n“${n.label}”${n.flag_latency_s != null ? `\n${CAUGHT_TIP}` : ''}` : full}</title>
                  <rect x={p.x} y={p.y} width={W} height={H} rx={10} />
                  <text className="k" x={p.x + 11} y={p.y + 19}>{k}</text>
                  <text className="v" x={p.x + 11} y={p.y + 40}>{label}</text>
                </g>)
              return rain ? <a key={n._id} href={RAINDROP_URL} target="_blank" rel="noreferrer">{box}</a> : box
            })}
          </svg>}
      </div>
      <aside className="inspector" aria-live="polite">
        {!sel || !node ? <p className="mute">Pick a lesson, or click a gold seam on Tsugi.</p> : <>
          <div className="ihead"><span className={'tag ' + status(node)}>{status(node)}</span>{seam(sel) && <span className="mono mute">{seam(sel)}</span>}</div>
          <p className="itext">{name(sel)}</p>
          {l?.title && <p className="mute" style={{ margin: 0 }}>{l.text}</p>}
          <dl className="meta">
            {l && <div><dt>Section</dt><dd>{SEC[l.section]}{l.section === 'tool_access' && l.tools ? `: ${l.only ? 'only' : l.allow ? 'allow' : 'remove'} ${l.tools.join(', ')} for ${l.tier}` : ''}</dd></div>}
            <div><dt>Came from</dt><dd>{parents.length ? parents.map(p => <span key={p._id} style={{ display: 'block' }}>
              {p.type === 'raindrop' ? <><RaindropChip flags={p.flags} s={p.flag_latency_s} /> “{p.label}”</>
                : p.type === 'lesson' ? <>{seam(p._id) || 'lesson'}: {name(p._id)}</> : <>{SOURCE[p.type] ?? p.type}: {p.label}</>}</span>)
              : l ? `${l.source.tier}, ${l.source.kind}` : 'unknown'}</dd></div>
            {l?.gate && <div><dt>Gate</dt><dd>{l.gate.fixed ? 'fixed' : 'not fixed'}, {l.gate.regression_passed}/{l.gate.regression_total} past cases pass</dd></div>}
            <div><dt>Shipped in</dt><dd>{state.versions[sel] != null ? `genome v${state.versions[sel]}` : 'not shipped'}</dd></div>
            {kids.length > 0 && <div><dt>Built on it</dt><dd>{kids.map(name).join(', ')}</dd></div>}
          </dl>
          {node.status === 'active' && !cascade.length && <button className="btn danger solid" disabled={running} onClick={revoke} style={{ justifySelf: 'start' }}>
            Revoke{liveKids.length ? ` with ${liveKids.length} descendant${liveKids.length === 1 ? '' : 's'}` : ''}</button>}
          <div><p className="mute" style={{ margin: '0 0 .35rem', fontSize: '.8rem' }}>Revoke in Atlas, one transaction</p>
<pre className={'code' + (running ? ' run' : '')}>{`db.lineage.aggregate([
  { $match: { _id: "${sel}" } },
  { `}<b>$graphLookup</b>{`: {
      from: "lineage",
      startWith: "$_id",
      connectFromField: "_id",
      connectToField: "parents",
      as: "down" } } ])`}</pre></div>
        </>}
      </aside>
    </div>
  )
}
