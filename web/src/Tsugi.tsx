/** Tsugi, the porcelain spirit. Gold seam = active lesson, red crack = quarantined, thin gold scar = revoked.
 *  The gate runs as a ring of real case ids around it. SVG children and particles are driven imperatively
 *  from effects (per-frame values never go through React state). */
import { memo, useEffect, useRef } from 'react'
import type { Lesson } from './live'

export type Mood = 'idle' | 'thinking' | 'happy' | 'hurt'
export type Ring = { key: string; labels: string[]; results: Record<string, boolean>; done: '' | 'accepted' | 'rejected' } | null

const RM = matchMedia('(prefers-reduced-motion: reduce)').matches
const NS = 'http://www.w3.org/2000/svg'
const MOUTH: Record<Mood, string> = {
  idle: 'M140,180 Q150,188 160,180', thinking: 'M145,184 Q150,182 155,184',
  happy: 'M136,177 Q150,197 164,177 Z', hurt: 'M137,186 q4.3,-5 8.6,0 q4.3,5 8.6,0 q4.3,-5 8.6,0',
}
const RC = [150, 178], RR = 172

function hash(s: string) { let h = 2166136261; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619) } return h >>> 0 }
function rng(seed: number) { return () => { seed = (seed + 0x6D2B79F5) | 0; let t = Math.imul(seed ^ (seed >>> 15), 1 | seed); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296 } }
/** Deterministic crack from the lesson id: from just outside the body edge (clipped) inward, may branch. */
function seamPath(id: string, jag = 1.2) {
  const r = rng(hash(id)), cx = 150, cy = 180, rx = 100, ry = 117
  let a = -180 + r() * 300; if (a > 60) a += 60; a *= Math.PI / 180  // skip the bottom-centre band (sprout window)
  let x = cx + Math.cos(a) * rx * 1.08, y = cy + Math.sin(a) * ry * 1.08
  const pts = [[x, y]]
  for (let i = 0; i < 7; i++) {
    const dir = Math.atan2(cy - y, cx - x) + (r() - .5) * jag, st = 13 + r() * 9
    x += Math.cos(dir) * st; y += Math.sin(dir) * st; pts.push([x, y])
    if (Math.hypot((x - cx) / rx, (y - cy) / ry) < .56) break
  }
  let d = 'M' + pts.map(p => p.map(n => n.toFixed(1)).join(',')).join(' L')
  if (r() < .6 && pts.length > 3) {
    let [bx, by] = pts[2]; const base = Math.atan2(cy - by, cx - bx) + (r() < .5 ? -1 : 1) * (.7 + r() * .5)
    d += ` M${bx.toFixed(1)},${by.toFixed(1)}`
    for (let i = 0; i < 2; i++) { bx += Math.cos(base + (r() - .5) * .6) * (9 + r() * 6); by += Math.sin(base + (r() - .5) * .6) * (9 + r() * 6); d += ` L${bx.toFixed(1)},${by.toFixed(1)}` }
  }
  return d
}
const kindOf = (l: Lesson) => l.status === 'active' ? 'seam' : l.status === 'quarantined' ? 'crack' : l.status === 'revoked' ? 'scar' : ''
const leaf = (x: number, y: number, a: number, s: number) =>
  `<g transform="translate(${x} ${y}) rotate(${a})"><path class="leaf" d="M0,0 C${s * .25},${-s * .55} ${s * .75},${-s * .5} ${s},0 C${s * .75},${s * .5} ${s * .25},${s * .55} 0,0Z"/><path class="vein" d="M2,0 L${s * .78},0"/></g>`

type P = { kind: string; x: number; y: number; vx: number; vy: number; g: number; r: number; life: number; max: number; a: number }
const COL: Record<string, string> = { dust: '214,166,64', spark: '247,205,96', molten: '255,190,70', chip: '143,42,32' }

/** Gold dust + sparks on a canvas over the SVG. */
function particles(cvs: HTMLCanvasElement) {
  const g2 = cvs.getContext('2d')!
  let parts: P[] = [], W = 0, H = 0, raf = 0
  const ro = new ResizeObserver(() => { const r = cvs.getBoundingClientRect(), dpr = devicePixelRatio || 1; W = r.width; H = r.height; cvs.width = W * dpr; cvs.height = H * dpr; g2.setTransform(dpr, 0, 0, dpr, 0, 0) })
  ro.observe(cvs)
  const make = (kind: string, x = 0, y = 0): P => {
    const a = Math.random() * Math.PI * 2, s = kind === 'spark' ? .6 + Math.random() * 2.4 : kind === 'molten' ? .3 + Math.random() * .9 : 1 + Math.random() * 1.5
    if (kind === 'dust') return { kind, x: Math.random() * W, y: Math.random() * H, vx: (Math.random() - .5) * .15, vy: -.06 - Math.random() * .18, g: 0, r: .7 + Math.random() * 1.5, life: 0, max: 400 + Math.random() * 500, a: .25 + Math.random() * .4 }
    return { kind, x, y, vx: Math.cos(a) * s, vy: Math.sin(a) * s - (kind === 'molten' ? .3 : 0), g: kind === 'spark' ? .025 : .05, r: kind === 'spark' ? 1 + Math.random() * 1.8 : 1.3 + Math.random() * 1.6, life: 0, max: 40 + Math.random() * 40, a: 1 }
  }
  const tick = () => {
    g2.clearRect(0, 0, W, H)
    if (W) { let nd = 0; for (const p of parts) if (p.kind === 'dust') nd++; for (let want = Math.round(W * H / 12000); nd < want; nd++) parts.push(make('dust')) }
    parts = parts.filter(p => p.life++ < p.max)
    for (const p of parts) {
      p.vy += p.g; p.x += p.vx; p.y += p.vy
      const k = p.life / p.max, a = p.a * (p.kind === 'dust' ? Math.sin(Math.PI * k) : 1 - k), c = COL[p.kind]
      g2.fillStyle = `rgba(${c},${a * .28})`; g2.beginPath(); g2.arc(p.x, p.y, p.r * 2.8, 0, 7); g2.fill()
      g2.fillStyle = `rgba(${c},${a})`; g2.beginPath(); g2.arc(p.x, p.y, p.r, 0, 7); g2.fill()
    }
    raf = requestAnimationFrame(tick)
  }
  if (!RM) raf = requestAnimationFrame(tick)
  const at = (el: SVGGraphicsElement, x: number, y: number): [number, number] => {
    const m = el.getScreenCTM(); if (!m) return [-99, -99]
    const p = new DOMPoint(x, y).matrixTransform(m), r = cvs.getBoundingClientRect(); return [p.x - r.left, p.y - r.top]
  }
  const emit = (kind: string, [x, y]: [number, number], n: number) => { if (!RM) for (let i = 0; i < n; i++) parts.push(make(kind, x, y)) }
  /** particles at the tip of a path that is drawing in */
  const trace = (path: SVGPathElement, delay: number, dur: number, kind: string, burst = false) => {
    if (RM) return
    const L = path.getTotalLength(), t0 = performance.now() + delay, ease = (k: number) => k < .5 ? 2 * k * k : 1 - (-2 * k + 2) ** 2 / 2
    const step = (t: number) => {
      if (!path.isConnected) return
      const k = (t - t0) / dur
      if (k > 1) { if (burst) { const e = path.getPointAtLength(L); emit('spark', at(path, e.x, e.y), 30) } return }
      if (k >= 0) { const p = path.getPointAtLength(L * ease(k)); emit(kind, at(path, p.x, p.y), kind === 'chip' ? 2 : 3) }
      requestAnimationFrame(step)
    }
    requestAnimationFrame(step)
  }
  return { emit, trace, at, stop: () => { cancelAnimationFrame(raf); ro.disconnect() } }
}

type Props = { lessons: Lesson[]; mood: Mood; episodes: number; ring: Ring; onSeam: (id: string) => void }

function Tsugi({ lessons, mood, episodes, ring, onSeam }: Props) {
  const canvas = useRef<HTMLCanvasElement>(null), shake = useRef<SVGGElement>(null), seams = useRef<SVGGElement>(null)
  const sprout = useRef<SVGGElement>(null), ripples = useRef<SVGGElement>(null), ringG = useRef<SVGGElement>(null)
  const nodes = useRef<SVGGElement>(null), comet = useRef<SVGCircleElement>(null)
  const fx = useRef<ReturnType<typeof particles> | null>(null)
  const seamEls = useRef(new Map<string, SVGGElement>()), seeded = useRef(false)
  const leaves = useRef(-1), lastEpisodes = useRef(episodes), built = useRef(''), seen = useRef<Record<string, boolean>>({}), cometA = useRef(-90)
  const onSeamRef = useRef(onSeam); onSeamRef.current = onSeam

  useEffect(() => { fx.current = particles(canvas.current!); return () => fx.current?.stop() }, [])

  // seams: draw new ones, crack on quarantine, molten-gold repair on revoke
  const key = lessons.map(l => l._id + kindOf(l)).join('|')
  useEffect(() => {
    const animate = seeded.current && !RM; seeded.current = true
    const want = new Map(lessons.map(l => [l._id, kindOf(l)] as const).filter(([, k]) => k))
    for (const [id, el] of seamEls.current) if (!want.has(id)) {
      seamEls.current.delete(id)
      if (animate) el.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 1200, fill: 'forwards' }).finished.then(() => el.remove(), () => el.remove())
      else el.remove()
    }
    for (const [id, kind] of want) {
      const old = seamEls.current.get(id)
      if (old?.dataset.kind === kind) continue
      if (old?.dataset.kind === 'seam' && kind === 'scar') { repair(old, animate); continue }
      old?.remove()
      const g = document.createElementNS(NS, 'g'), d = kind === 'crack' ? seamPath(id + '!', 2) : seamPath(id)
      g.setAttribute('class', 'seam ' + (kind === 'seam' ? '' : kind)); g.dataset.kind = kind
      const les = lessons.find(l => l._id === id), text = les?.title || les?.text || ''
      g.innerHTML = `<title></title><path class="hit" d="${d}"/><path class="line" pathLength="100" d="${d}"/>`
      g.querySelector('title')!.textContent = text
      g.addEventListener('click', () => onSeamRef.current(id))
      seams.current!.appendChild(g); seamEls.current.set(id, g)
      if (!animate || kind === 'scar') continue
      const line = g.querySelector<SVGPathElement>('.line')!
      line.animate([{ strokeDasharray: '100', strokeDashoffset: 100 }, { strokeDasharray: '100', strokeDashoffset: 0 }],
        { duration: kind === 'crack' ? 600 : 1600, easing: kind === 'crack' ? 'steps(6)' : 'cubic-bezier(.45,0,.55,1)' })
      if (kind === 'seam') fx.current?.trace(line, 0, 1600, 'spark', true)
      else {
        shake.current?.animate([{ transform: 'none' }, { transform: 'translateX(-6px) rotate(-1.5deg)' }, { transform: 'translateX(6px) rotate(1.5deg)' }, { transform: 'translateX(-4px)' }, { transform: 'none' }], { duration: 550 })
        fx.current?.trace(line, 0, 600, 'chip')
      }
    }
    function repair(el: SVGGElement, animate: boolean) {  // kintsugi: red flash, molten gold flows in, cools into a scar
      el.dataset.kind = 'scar'
      const line = el.querySelector<SVGPathElement>('.line')!, done = () => el.setAttribute('class', 'seam scar')
      if (!animate) return done()
      line.animate([{ stroke: '#d1382a' }, { stroke: 'transparent' }, { stroke: '#d1382a' }, { stroke: 'transparent' }, { stroke: '#d1382a' }], { duration: 900 })
      const m = document.createElementNS(NS, 'path')
      m.setAttribute('class', 'molten'); m.setAttribute('pathLength', '100'); m.setAttribute('d', line.getAttribute('d')!)
      el.appendChild(m)
      m.animate([{ strokeDasharray: '100', strokeDashoffset: 100, stroke: '#fff6d0' }, { strokeDasharray: '100', strokeDashoffset: 0, stroke: '#ffd25a', offset: .6 },
        { strokeDasharray: '100', strokeDashoffset: 0, stroke: '#e0a83c', opacity: 0 }], { duration: 2400, delay: 900, easing: 'cubic-bezier(.45,0,.55,1)', fill: 'both' })
        .finished.then(() => { m.remove(); done() }, () => {})
      fx.current?.trace(m, 900, 1400, 'molten')
    }
  }, [key])  // eslint-disable-line react-hooks/exhaustive-deps

  // sprout: a leaf per live episode (up to 4), wilts while a stranger's lesson is quarantined, pulses on a new episode
  const wilt = lessons.some(l => l.status === 'quarantined')
  useEffect(() => {
    const sp = sprout.current!, extra = Math.min(4, episodes)
    if (extra !== leaves.current) {
      leaves.current = extra
      const base = 266, h = 26 + extra * 5, top = base - h
      let html = `<path class="stem" d="M150,${base} Q145,${base - h / 2} 150,${top}"/>`
      for (let i = 0; i < extra; i++) { const y = base - 10 - (i + 1) * (h - 16) / (extra + 1), l = i % 2 === 0; html += leaf(l ? 148 : 151, y, l ? -160 : -20, 12) }
      sp.innerHTML = html + leaf(150, top, -148, 18) + leaf(150, top, -32, 18)
    }
    if (episodes > lastEpisodes.current) {
      sp.classList.add('recall'); setTimeout(() => sp.classList.remove('recall'), 1400)
      if (!RM) for (const d of [0, 280]) setTimeout(() => {
        const r = document.createElementNS(NS, 'ellipse')
        for (const [k, v] of Object.entries({ cx: 150, cy: 266, rx: 25, ry: 8.5, class: 'ripple' })) r.setAttribute(k, String(v))
        ripples.current?.appendChild(r); setTimeout(() => r.remove(), 1700)
      }, d)
    }
    lastEpisodes.current = episodes
  }, [episodes])

  // gate ring: one node per case (the failure first), lit as results arrive in the gates doc
  useEffect(() => {
    const g = ringG.current!, place = (deg: number) => { const a = deg * Math.PI / 180; comet.current!.setAttribute('cx', (RC[0] + Math.cos(a) * RR).toFixed(1)); comet.current!.setAttribute('cy', (RC[1] + Math.sin(a) * RR).toFixed(1)) }
    if (!ring) { g.classList.remove('on'); built.current = ''; return }
    const n = ring.labels.length, angle = (i: number) => -90 + i * 360 / n
    if (built.current !== ring.key) {
      built.current = ring.key; seen.current = {}; cometA.current = -90; place(-90)
      g.getAnimations().forEach(a => a.cancel())
      nodes.current!.innerHTML = ring.labels.map((lab, i) => {
        const a = angle(i) * Math.PI / 180, x = RC[0] + Math.cos(a) * RR, y = RC[1] + Math.sin(a) * RR, c = Math.cos(a), s = Math.sin(a)
        const lx = RC[0] + c * (RR + 20), ly = RC[1] + s * (RR + 20) + 4 + (s < -.9 ? -8 : s > .9 ? 10 : 0)
        return `<g class="node${lab.startsWith('scar ') ? ' scar' : ''}" data-i="${i}"><circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${i === 0 ? 11 : 8}"/><text x="${lx.toFixed(1)}" y="${ly.toFixed(1)}" text-anchor="${c > .3 ? 'start' : c < -.3 ? 'end' : 'middle'}"></text></g>`
      }).join('')
      nodes.current!.querySelectorAll('text').forEach((t, i) => { t.textContent = ring.labels[i].startsWith('scar ') ? 'scar' : ring.labels[i] })  // a past live mistake, replayed
      g.classList.add('on')
    }
    let firstPending = -1, newest = -1
    ring.labels.forEach((lab, i) => {
      const node = nodes.current!.querySelector<SVGGElement>(`.node[data-i="${i}"]`)!, r = ring.results[lab]
      if (r === undefined && firstPending < 0 && !ring.done) firstPending = i
      node.setAttribute('class', 'node ' + (lab.startsWith('scar ') ? 'scar ' : '') + (r === true ? 'pass' : r === false ? 'fail' : i === firstPending ? 'testing' : ''))
      if (r !== undefined && seen.current[lab] !== r) {
        seen.current[lab] = r; newest = i
        const c = node.querySelector('circle')!
        fx.current?.emit(r ? 'spark' : 'chip', fx.current.at(c, +c.getAttribute('cx')!, +c.getAttribute('cy')!), r ? 10 : 6)
      }
    })
    const target = newest >= 0 ? newest : firstPending
    if (target >= 0) {
      const from = cometA.current, to = angle(target), t0 = performance.now()
      const step = (t: number) => { const k = Math.min(1, (t - t0) / 260), e = 1 - (1 - k) ** 3; place(from + (to - from) * e); if (k < 1) requestAnimationFrame(step); else cometA.current = to }
      RM ? place(to) : requestAnimationFrame(step)
    }
    if (ring.done) {
      const t = setTimeout(() => {
        if (RM || ring.done !== 'accepted') { g.classList.remove('on'); return }
        g.animate([{ transform: 'none', opacity: 1 }, { transform: 'scale(.35)', opacity: 0 }], { duration: 650, easing: 'cubic-bezier(.6,0,.4,1)', fill: 'forwards' })
          .finished.then(() => { g.classList.remove('on'); g.getAnimations().forEach(a => a.cancel()) }, () => {})
      }, 1400)
      return () => clearTimeout(t)
    }
  }, [ring])

  return (
    <div className="plate">
      <canvas ref={canvas} aria-hidden="true" />
      <svg id="tsugi" className={'mood-' + mood} viewBox="-80 -40 460 440" role="img" aria-label="Tsugi, a porcelain spirit. Gold seams are lessons that passed the gate.">
        <defs>
          <radialGradient id="glaze" cx="38%" cy="28%" r="78%"><stop offset="0" stopColor="#ffffff" /><stop offset=".55" stopColor="#fbf6ea" /><stop offset="1" stopColor="#e6dbc4" /></radialGradient>
          <linearGradient id="goldGrad" gradientUnits="userSpaceOnUse" x1="50" y1="60" x2="250" y2="300"><stop offset="0" stopColor="#f9de8a" /><stop offset=".5" stopColor="#dcaa42" /><stop offset="1" stopColor="#b08024" /></linearGradient>
          <filter id="glow" filterUnits="userSpaceOnUse" x="-80" y="-40" width="460" height="440"><feGaussianBlur stdDeviation="2.2" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
          <filter id="glowBig" filterUnits="userSpaceOnUse" x="-80" y="-40" width="460" height="440"><feGaussianBlur stdDeviation="5" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
          <clipPath id="bodyClip"><path d="M150,62 C210,62 248,110 250,180 C252,250 214,296 150,296 C86,296 48,250 50,180 C52,110 90,62 150,62 Z" /></clipPath>
        </defs>
        <g ref={ringG} className="ring"><circle className="base" cx="150" cy="178" r="172" /><g ref={nodes} /><circle ref={comet} className="comet" r="5.5" cx="150" cy="6" filter="url(#glow)" /></g>
        <ellipse id="shadow" cx="150" cy="316" rx="84" ry="9" />
        <g className="sparkles">
          <path transform="translate(52 96)" d="M0,-11 L2.8,-2.8 11,0 2.8,2.8 0,11 -2.8,2.8 -11,0 -2.8,-2.8Z" />
          <path transform="translate(250 110) scale(.75)" d="M0,-11 L2.8,-2.8 11,0 2.8,2.8 0,11 -2.8,2.8 -11,0 -2.8,-2.8Z" />
          <path transform="translate(240 40) scale(.5)" d="M0,-11 L2.8,-2.8 11,0 2.8,2.8 0,11 -2.8,2.8 -11,0 -2.8,-2.8Z" />
        </g>
        <g ref={shake}><g id="float"><g id="breath">
          <g fill="url(#glaze)" stroke="#d6c8ac" strokeWidth="2">
            <ellipse cx="50" cy="214" rx="13" ry="20" transform="rotate(28 50 214)" />
            <ellipse cx="250" cy="214" rx="13" ry="20" transform="rotate(-28 250 214)" />
            <ellipse cx="118" cy="294" rx="20" ry="10" /><ellipse cx="182" cy="294" rx="20" ry="10" />
            <path d="M150,62 C210,62 248,110 250,180 C252,250 214,296 150,296 C86,296 48,250 50,180 C52,110 90,62 150,62 Z" />
            <path d="M104,70 C108,46 192,46 196,70 Z" />
            <ellipse cx="150" cy="70" rx="47" ry="8" fill="#f8f1e2" />
            <circle cx="150" cy="42" r="9" />
          </g>
          <path d="M116,62 C134,54 166,54 184,62" fill="none" stroke="#35548f" strokeWidth="2" strokeLinecap="round" />
          <g clipPath="url(#bodyClip)">
            <ellipse className="sheen" cx="100" cy="112" rx="15" ry="32" transform="rotate(28 100 112)" fill="#fff" opacity=".75" />
            <path d="M58,274 C110,296 190,296 242,274" fill="none" stroke="#35548f" strokeWidth="1.6" opacity=".45" />
            <g ref={seams} />
          </g>
          <g className="face">
            <ellipse cx="102" cy="172" rx="11" ry="6" fill="#f2a59c" opacity=".45" />
            <ellipse cx="198" cy="172" rx="11" ry="6" fill="#f2a59c" opacity=".45" />
            <g className="look">
              <g className="eyes-open" fill="#2a2420">
                <ellipse cx="122" cy="148" rx="12" ry="15" /><ellipse cx="178" cy="148" rx="12" ry="15" />
                <circle cx="126" cy="142" r="4.2" fill="#fff" /><circle cx="182" cy="142" r="4.2" fill="#fff" />
                <circle cx="118" cy="154" r="1.8" fill="#fff" /><circle cx="174" cy="154" r="1.8" fill="#fff" />
              </g>
              <g className="eyes-happy" fill="none" stroke="#2a2420" strokeWidth="4.5" strokeLinecap="round"><path d="M110,152 Q122,136 134,152" /><path d="M166,152 Q178,136 190,152" /></g>
            </g>
            <g className="brows" fill="none" stroke="#2a2420" strokeWidth="3.5" strokeLinecap="round"><path d="M107,130 L132,123" /><path d="M168,123 L193,130" /></g>
            <path className="tear" d="M199,134 q6,9 0,12 q-6,-3 0,-12z" fill="#9cc7e8" />
            <path className="mouth" d={MOUTH[mood]} />
          </g>
          <g className="window"><ellipse cx="150" cy="266" rx="25" ry="8.5" fill="#5b4631" stroke="#d6a640" strokeWidth="2.4" /></g>
          <g ref={ripples} className="ripples" />
          <g className="sprout-wrap"><g ref={sprout} className={'sprout' + (wilt ? ' wilt' : '')} /></g>
        </g></g></g>
      </svg>
    </div>
  )
}
export default memo(Tsugi)
