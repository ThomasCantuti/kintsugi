import { Activity, lazy, Suspense, useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { useLive, type Conn } from './live'
import Stage, { Count } from './Stage'
import Tour, { Prompts } from './Tour'

const Proof = lazy(() => import('./Proof'))
const Lineage = lazy(() => import('./Lineage'))
const Raindrop = lazy(() => import('./Raindrop'))
const SCENES = [['stage', 'Stage'], ['proof', 'Proof'], ['lineage', 'Lineage'], ['raindrop', 'Raindrop']] as const
type Scene = typeof SCENES[number][0]
const CONN: Record<Conn, string> = { connecting: 'connecting', live: 'live', reconnecting: 'reconnecting', mock: 'MOCK data' }

export default function App() {
  const { state, events, conn } = useLive()
  const [scene, setScene] = useState<Scene>(() => (SCENES.find(([s]) => '#' + s === location.hash)?.[0]) ?? 'stage')
  const [selected, setSelected] = useState<string | null>(null)
  const [theme, setTheme] = useState(() => document.documentElement.dataset.theme || 'dark')
  const [toastMsg, setToast] = useState('')
  const [tour, setTour] = useState(false), [prompts, setPrompts] = useState(false)
  const [toured, setToured] = useState(() => { try { return !!localStorage.getItem('toured') } catch { return false } })
  const startTour = () => { setTour(true); setToured(true); try { localStorage.setItem('toured', '1') } catch { /* private mode */ } }
  const tabs = useRef<HTMLElement>(null), ind = useRef<HTMLSpanElement>(null)

  const go = useCallback((s: Scene) => {
    const swap = () => { setScene(s); history.replaceState(null, '', '#' + s) }
    // view transition: a crossfade between scenes where the browser supports it
    const vt = (document as Document & { startViewTransition?: (f: () => void) => void }).startViewTransition
    if (vt && !matchMedia('(prefers-reduced-motion: reduce)').matches) vt.call(document, swap); else swap()
  }, [])
  const openLesson = useCallback((id: string) => { setSelected(id); go('lineage') }, [go])
  const toast = useCallback((t: string) => { setToast(t); setTimeout(() => setToast(''), 3500) }, [])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement).closest('input,textarea') || e.metaKey || e.ctrlKey || e.altKey) return
      const s = SCENES[+e.key - 1]; if (s) go(s[0])
      if (e.key === 't') setTheme(t => t === 'dark' ? 'light' : 'dark')
    }
    addEventListener('keydown', onKey); return () => removeEventListener('keydown', onKey)
  }, [go])
  useEffect(() => { document.documentElement.dataset.theme = theme; try { localStorage.setItem('theme', theme) } catch { /* private mode */ } }, [theme])
  useLayoutEffect(() => {
    const place = () => {
      const b = tabs.current?.querySelector<HTMLButtonElement>(`[data-scene="${scene}"]`)
      if (b && ind.current) ind.current.style.transform = `translateX(${b.offsetLeft + 10}px) scaleX(${Math.max(1, b.offsetWidth - 20)})`
    }
    place(); document.fonts?.ready.then(place)
    addEventListener('resize', place); return () => removeEventListener('resize', place)
  }, [scene])

  const g = state?.genome
  return (
    <>
      <header className="top">
        <div className="brand">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 4 L9 10 L6.5 14 L13 18.5 L21 12" /><path d="M9 10 L13.5 8.5" /></svg>
          <h1>Kintsugi</h1><span className="kanji" lang="ja">金継ぎ</span><small>Tsugi live</small>
        </div>
        <nav className="tabs" role="tablist" aria-label="Scenes" ref={tabs}>
          {SCENES.map(([s, label], i) => <button key={s} role="tab" data-scene={s} aria-selected={scene === s} title={`${label} (${i + 1})`} onClick={() => go(s)}>{label}</button>)}
          <span className="ind" ref={ind} aria-hidden="true" />
        </nav>
        <div className="chips">
          <span className="chip ver"><span>genome v<span className="roll"><AnimatePresence initial={false} mode="popLayout">
            <motion.span key={g?.version ?? '-'} initial={{ y: '100%' }} animate={{ y: 0 }} exit={{ y: '-100%' }} transition={{ type: 'spring', stiffness: 260, damping: 24 }}>{g?.version ?? '-'}</motion.span>
          </AnimatePresence></span></span></span>
          <span className={'chip gate' + (state?.gate_running ? ' on' : '')}>{state?.gate_running ? 'gate testing' : 'gate idle'}</span>
          <span className={'chip c-' + conn}><span className="live" />{CONN[conn]}</span>
          <span className="chip"><b><Count value={state?.counters.cost ?? 0} fmt={v => '$' + v.toFixed(2)} /></b>&nbsp;spent</span>
          <button className="themebtn" type="button" onClick={() => setTheme(t => t === 'dark' ? 'light' : 'dark')} aria-label={`Theme: ${theme === 'dark' ? 'Lacquer' : 'Porcelain'}. Switch theme`}>
            {theme === 'dark' ? 'Lacquer' : 'Porcelain'}</button>
        </div>
      </header>
      {state?.sandbox && <div className="sandbox-note">
        <button className={'tour-btn' + (toured ? '' : ' pulse')} onClick={startTour}>▶ Start the tour</button>
        <button className="btn" onClick={() => setPrompts(p => !p)} aria-expanded={prompts}>Prompts</button>
        <p>Judges' sandbox: a copy of Tsugi where you are Thomas, the owner. Chat in the Telegram panel (Thomas tab), 👎 a reply and correct it, then watch the gate test your lesson. Thomas's own Tsugi isn't affected.</p>
      </div>}
      <main>
        {!state ? <div className="scene"><p className="empty">Connecting to Atlas…</p></div> : <>
          <Activity mode={scene === 'stage' ? 'visible' : 'hidden'}><Stage state={state} events={events} onLesson={openLesson} /></Activity>
          <Suspense fallback={null}>
            <Activity mode={scene === 'proof' ? 'visible' : 'hidden'}><Proof state={state} visible={scene === 'proof'} /></Activity>
            <Activity mode={scene === 'lineage' ? 'visible' : 'hidden'}><Lineage state={state} selected={selected} onSelect={setSelected} visible={scene === 'lineage'} toast={toast} /></Activity>
            <Activity mode={scene === 'raindrop' ? 'visible' : 'hidden'}><Raindrop state={state} visible={scene === 'raindrop'} onLesson={openLesson} /></Activity>
          </Suspense>
        </>}
      </main>
      {toastMsg && <div className="toast" role="status">{toastMsg}</div>}
      {tour && state && <Tour go={go} onClose={chat => { setTour(false); if (chat) setPrompts(true) }} />}
      {prompts && !tour && <section className="prompts-panel" aria-label="Prompts to try">
        <div className="prompts-head"><h2>Try these</h2><button className="btn" onClick={() => setPrompts(false)} aria-label="Close prompts">✕</button></div>
        <Prompts />
      </section>}
    </>
  )
}
