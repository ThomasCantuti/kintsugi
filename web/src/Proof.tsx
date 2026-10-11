/** Proof: pass rates from stored runs only. Unrun setups are empty slots; dots are single trials. */
import { useEffect, useRef, useState } from 'react'
import { parseT, type Run, type State } from './live'

const RM = matchMedia('(prefers-reduced-motion: reduce)').matches
type Split = 'heldout' | 'hard' | 'redteam'
const SPLITS: Record<Split, { tab: string; title: string; sub: string; bars: [string, string, string][] }> = {
  heldout: {
    tab: 'Held-out', title: 'Does a free model with a learned harness hold up?',
    sub: 'Held-out pass rate on 12 hand-written cases no lesson was learned from, frozen at commit 11c8ce0. Scored only by checks on the data in Atlas. Memory = every train correction pasted into the prompt.',
    bars: [['A0', 'raw loop', 'raw'], ['A', 'harness, v0', ''], ['B', 'learned genome', ''], ['Dn', 'Nemotron + memory', 'raw'],
           ['C', 'frontier, v0', 'frontier'], ['D', 'frontier + memory', 'frontier']],
  },
  hard: {
    tab: 'Hard tools', title: 'Does the harness rescue messy tool calls?',
    sub: '8 multi-step tool-handling cases frozen at 748d9c7: move or cancel events by description, invite people by name.',
    bars: [['hard-A0', 'raw loop', 'raw'], ['hard-A', 'harness, v0', ''], ['hard-B', 'learned genome', '']],
  },
  redteam: {
    tab: 'Red team', title: 'Do strangers get through?',
    sub: '10 red-team cases: 7 stranger attacks, 2 planted injections, 1 over-blocking control. A pass means the attack was refused and the control was served.',
    bars: [['rt-v0', 'genome v0', 'raw'], ['rt-v6', 'learned genome', '']],
  },
}

function latest(runs: Run[], split: Split, label: string) {
  let best: Run | undefined
  for (const r of runs) if (r.split === split && r.label === label && (!best || parseT(r.created_at) >= parseT(best.created_at))) best = r
  return best
}

function Bars({ split, runs, play }: { split: Split; runs: Run[]; play: number }) {
  const ref = useRef<SVGSVGElement>(null)
  const cfg = SPLITS[split].bars
  const W = 640, H = 340, L = 44, R = 10, T = 70, B = 54, ih = H - T - B, colW = (W - L - R) / cfg.length, bw = Math.min(70, colW * .5)
  const y = (p: number) => T + ih * (1 - p)
  useEffect(() => {
    if (RM || !ref.current) return
    ref.current.querySelectorAll<SVGRectElement>('.bar').forEach((b, i) =>
      b.animate([{ transform: 'scaleY(0)' }, { transform: 'scaleY(1)' }], { duration: 1200, delay: i * 160, easing: 'cubic-bezier(.2,.9,.25,1)', fill: 'backwards' }))
    ref.current.querySelectorAll<SVGTextElement>('.barv').forEach((t, i) => {
      const to = +t.dataset.p!, t0 = performance.now() + i * 160
      const step = (now: number) => { const k = Math.max(0, Math.min(1, (now - t0) / 1200)), e = 1 - (1 - k) ** 3; t.textContent = Math.round(to * e) + '%'; if (k < 1) requestAnimationFrame(step) }
      requestAnimationFrame(step)
    })
    ref.current.querySelectorAll('.trial, .barn').forEach(el => el.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 500, delay: 900, fill: 'backwards' }))
  }, [split, play])
  return (
    <svg ref={ref} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${SPLITS[split].tab} pass rate per setup`}>
      {[0, .25, .5, .75, 1].map(p => <g key={p}><line className="ax" x1={L} x2={W - R} y1={y(p)} y2={y(p)} /><text className="axt" x={L - 8} y={y(p) + 4} textAnchor="end">{p * 100}%</text></g>)}
      {cfg.map(([label, desc, cls], i) => {
        const r = latest(runs, split, label), cx = L + colW * (i + .5)
        const tail = <><text className="barl" x={cx} y={H - B + 22} textAnchor="middle">{label}</text><text className="bard" x={cx} y={H - B + 38} textAnchor="middle">{desc}</text></>
        if (!r) return <g key={label}><rect className="slot" x={cx - bw / 2} y={y(0) - 34} width={bw} height={34} rx={6} /><text className="barn" x={cx} y={y(0) - 44} textAnchor="middle">not run yet</text>{tail}</g>
        const p = r.pass_rate, top = y(p), per = r.trials ? r.n / r.trials : r.n, tp = r.trial_passed ?? []
        const above = Math.min(top, ...tp.map(t => y(t / per) - 6))  // labels sit above the bar and its highest trial dot
        return (
          <g key={label}>
            <rect className={'bar ' + cls} x={cx - bw / 2} y={top} width={bw} height={y(0) - top} rx={6}><title>{`${r.passed}/${r.n} passed, ${r.model}, genome v${r.genome_version ?? 'off'}`}</title></rect>
            <text className="barv" x={cx} y={above - 36} textAnchor="middle" data-p={Math.round(p * 100)}>{Math.round(p * 100)}%</text>
            <text className="barn" x={cx} y={above - 20} textAnchor="middle">{r.passed}/{r.n}</text>
            <text className="barn" x={cx} y={above - 7} textAnchor="middle">${(r.cost / r.n).toFixed(4)}/task</text>
            {tp.length > 1 && tp.map((t, j) => <circle key={j} className="trial" cx={cx + (j - (tp.length - 1) / 2) * 12} cy={y(t / per)} r={4.5}><title>{`trial ${j + 1}: ${t}/${per}`}</title></circle>)}
            {tail}
          </g>)
      })}
    </svg>
  )
}

function Curve({ curve }: { curve: State['curve'] }) {
  const W = 400, H = 340, L = 44, R = 16, T = 58, B = 54, ih = H - T - B
  const pts = [...curve].sort((a, b) => a.version - b.version)
  const slots = Math.max(4, pts.length)
  const x = (i: number) => L + (W - L - R) * (i + .5) / slots, y = (p: number) => T + ih * (1 - p)
  const line = pts.map((p, i) => `${i ? 'L' : 'M'}${x(i)},${y(p.pass_rate)}`).join(' ')
  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Held-out pass rate per genome version">
      {[0, .25, .5, .75, 1].map(p => <g key={p}><line className="ax" x1={L} x2={W - R} y1={y(p)} y2={y(p)} /><text className="axt" x={L - 8} y={y(p) + 4} textAnchor="end">{p * 100}%</text></g>)}
      {pts.length > 1 && <path className="carea" d={`${line} L${x(pts.length - 1)},${y(0)} L${x(0)},${y(0)} Z`} />}
      {pts.length > 1 && <path className="cline" d={line} />}
      {pts.map((p, i) => <g key={p.version}>
        <circle className="cpt" cx={x(i)} cy={y(p.pass_rate)} r={6}><title>{`v${p.version}: ${Math.round(p.pass_rate * 100)}%, n=${p.n}`}</title></circle>
        <text className="barv" style={{ fontSize: 16 }} x={x(i)} y={y(p.pass_rate) - 24} textAnchor="middle">{Math.round(p.pass_rate * 100)}%</text>
        <text className="barn" x={x(i)} y={y(p.pass_rate) - 10} textAnchor="middle">n={p.n}</text>
        <text className="barl" x={x(i)} y={H - B + 22} textAnchor="middle">v{p.version}</text>
      </g>)}
      {!pts.length && <text className="barn" x={(L + W - R) / 2} y={T + ih / 2} textAnchor="middle">no held-out runs per version yet</text>}
    </svg>
  )
}

export default function Proof({ state, visible }: { state: State; visible: boolean }) {
  const [split, setSplit] = useState<Split>('heldout')
  const [play, setPlay] = useState(0)
  useEffect(() => { if (visible) setPlay(p => p + 1) }, [visible])
  const cfg = SPLITS[split]
  const shown = cfg.bars.map(([l]) => latest(state.runs, split, l)).filter((r): r is Run => !!r)
  const models = [...new Set(shown.map(r => r.model.replace(/^[^/]+\//, '')))]
  const trials = [...new Set(shown.map(r => r.trials ?? 1))]
  return (
    <div className="scene proof">
      <div className="phead">
        <div className="seg" role="tablist" aria-label="Eval split" style={{ justifySelf: 'start' }}>
          {(Object.keys(SPLITS) as Split[]).map(s => <button key={s} role="tab" aria-selected={split === s} onClick={() => { setSplit(s); setPlay(p => p + 1) }}>{SPLITS[s].tab}</button>)}
        </div>
        <h2>{cfg.title}</h2>
        <p>{cfg.sub}</p>
      </div>
      <div className={'chartbox' + (split === 'heldout' ? '' : ' wide')}><h3>Latest stored run per setup</h3><Bars split={split} runs={state.runs} play={play} /></div>
      {split === 'heldout' && <div className="chartbox"><h3>Pass rate per genome version</h3><Curve curve={state.curve} /></div>}
      <p className="footnote">
        {shown.length ? `Stored runs. Models: ${models.join(', ')}. Trials per run: ${trials.join(', ')}. Dots are single trials; bars are the pooled pass rate. ` : 'No stored runs for this split yet. '}
        Scored only by deterministic checks, never by the supervisor. Setups without a stored run stay empty.
      </p>
    </div>
  )
}
