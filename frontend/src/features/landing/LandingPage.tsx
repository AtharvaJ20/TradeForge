import { useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import {
  motion,
  useScroll,
  useTransform,
  useInView,
} from 'framer-motion'
import { useTheme } from '@/shared/hooks/useTheme'
import { EquityCurveCanvas } from './EquityCurveCanvas'
import { HeroBackground } from './HeroBackground'
import { PnLCounter } from './PnLCounter'

// ─── Motion variants ─────────────────────────────────────────────────────────

const fadeUp = {
  hidden: { opacity: 0, y: 24 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.55, ease: [0.22, 1, 0.36, 1] } },
}

const stagger = {
  visible: { transition: { staggerChildren: 0.1 } },
}

// ─── Icons ───────────────────────────────────────────────────────────────────

function IconSun() {
  return (
    <svg width="18" height="18" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
      <path d="M8 10.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z" />
      <path d="M8 .75a.75.75 0 0 1 .75.75v1a.75.75 0 0 1-1.5 0v-1A.75.75 0 0 1 8 .75ZM1.17 4.285a.75.75 0 0 1 1.03-.265l.866.5a.75.75 0 1 1-.75 1.3l-.866-.5a.75.75 0 0 1-.28-1.035ZM4.285 14.83a.75.75 0 0 1-.265-1.03l.5-.866a.75.75 0 0 1 1.3.75l-.5.866a.75.75 0 0 1-1.035.28ZM.75 8a.75.75 0 0 1 .75-.75h1a.75.75 0 0 1 0 1.5h-1A.75.75 0 0 1 .75 8ZM14.83 11.715a.75.75 0 0 1-1.03.265l-.866-.5a.75.75 0 0 1 .75-1.3l.866.5a.75.75 0 0 1 .28 1.035ZM11.715 1.17a.75.75 0 0 1 .265 1.03l-.5.866a.75.75 0 1 1-1.3-.75l.5-.866a.75.75 0 0 1 1.035-.28ZM8 13.5a.75.75 0 0 1 .75.75v1a.75.75 0 0 1-1.5 0v-1A.75.75 0 0 1 8 13.5ZM13.48 4.517a.75.75 0 1 0-.75-1.3l-.866.5a.75.75 0 0 0 .75 1.3l.866-.5Z" />
    </svg>
  )
}

function IconMoon() {
  return (
    <svg width="18" height="18" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
      <path d="M14.438 10.148c.19-.425-.321-.787-.748-.601A5.5 5.5 0 0 1 6.453 2.31c.186-.427-.176-.938-.6-.748a6.501 6.501 0 1 0 8.585 8.586Z" />
    </svg>
  )
}

function IconCheck() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="M13.5 4.5L6.5 11.5L3 8" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function IconArrowRight() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="M3 8h10M9 4l4 4-4 4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

// ─── Broker Logo Images ───────────────────────────────────────────────────────

function BrokerLogo({ src, alt }: { src: string; alt: string }) {
  return (
    <img
      src={src}
      alt={alt}
      width={52}
      height={52}
      className="rounded-xl object-contain"
      draggable={false}
    />
  )
}

function ZerodhaIcon()  { return <BrokerLogo src="/brokers/zerodha.png"  alt="Zerodha" /> }
function UpstoxIcon()   { return <BrokerLogo src="/brokers/upstox.png"   alt="Upstox" /> }
function AngelOneIcon() { return <BrokerLogo src="/brokers/angelone.png" alt="Angel One" /> }
function FivePaisaIcon(){ return <BrokerLogo src="/brokers/fivepaisa.png"alt="5Paisa" /> }
function DhanIcon()     { return <BrokerLogo src="/brokers/dhan.png"     alt="Dhan" /> }
function FyersIcon()    { return <BrokerLogo src="/brokers/fyers.png"    alt="Fyers" /> }

function BrokerMarquee() {
  const trackRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = trackRef.current
    if (!el) return
    // Measure the exact pixel width of one set (item[6].left – item[0].left)
    const item0 = el.children[0] as HTMLElement
    const itemN = el.children[BROKERS.length] as HTMLElement
    const loopPx = itemN.getBoundingClientRect().left - item0.getBoundingClientRect().left
    el.style.setProperty('--marquee-offset', `-${loopPx}px`)
  }, [])

  // Repeat enough times so the total track always exceeds the widest viewport (4k).
  // One set ≈ 660px; 10 copies ≈ 6600px — well beyond 3840px.
  const copies = Array.from({ length: 10 }, (_, i) => i)

  return (
    <div
      ref={trackRef}
      className="flex w-max gap-14 animate-marquee will-change-transform hover:[animation-play-state:paused]"
    >
      {copies.flatMap((copy) =>
        BROKERS.map(({ name, Icon }) => (
          <div
            key={`${copy}-${name}`}
            aria-hidden={copy > 0 || undefined}
            className="flex flex-col items-center gap-2"
          >
            <Icon />
            <span className="text-xs font-semibold text-text-muted">{name}</span>
          </div>
        ))
      )}
    </div>
  )
}

const BROKERS = [
  { name: 'Zerodha', Icon: ZerodhaIcon },
  { name: 'Upstox', Icon: UpstoxIcon },
  { name: 'Angel One', Icon: AngelOneIcon },
  { name: '5Paisa', Icon: FivePaisaIcon },
  { name: 'Dhan', Icon: DhanIcon },
  { name: 'Fyers', Icon: FyersIcon },
]

// ─── Product Gallery Illustrations ───────────────────────────────────────────

function AnalyticsIllustration() {
  const bars = [58, 82, 47, 91, 65, 73, 88, 52, 79, 96]
  return (
    <svg viewBox="0 0 320 200" xmlns="http://www.w3.org/2000/svg" className="w-full" aria-hidden="true">
      {/* BG */}
      <rect width="320" height="200" rx="12" fill="var(--color-surface-base)" />
      <rect width="320" height="200" rx="12" fill="none" stroke="var(--color-border)" />
      {/* Header row */}
      <text x="16" y="26" fontSize="9" fontWeight="600" fill="var(--color-text-muted)" fontFamily="system-ui">Analytics</text>
      <rect x="240" y="14" width="64" height="16" rx="4" fill="var(--color-brand)" opacity="0.15" />
      <text x="272" y="26" fontSize="8" fontWeight="600" fill="var(--color-brand)" textAnchor="middle" fontFamily="system-ui">This month</text>
      {/* Stat row */}
      {[
        { label: 'Win Rate', val: '68.4%', x: 16, color: 'var(--color-success)' },
        { label: 'Expectancy', val: '1.82R', x: 96, color: 'var(--color-text-primary)' },
        { label: 'Profit Factor', val: '2.71', x: 192, color: 'var(--color-success)' },
      ].map((s) => (
        <g key={s.label}>
          <text x={s.x} y="52" fontSize="7.5" fill="var(--color-text-muted)" fontFamily="system-ui">{s.label}</text>
          <text x={s.x} y="66" fontSize="13" fontWeight="700" fill={s.color} fontFamily="monospace">{s.val}</text>
        </g>
      ))}
      {/* Bar chart */}
      <text x="16" y="90" fontSize="7" fill="var(--color-text-muted)" fontFamily="system-ui">Monthly P&L</text>
      {bars.map((h, i) => (
        <g key={i}>
          <rect
            x={16 + i * 29}
            y={180 - h * 0.8}
            width="18"
            height={h * 0.8}
            rx="3"
            fill={h > 70 ? 'var(--color-success)' : 'var(--color-danger)'}
            opacity={h > 70 ? 0.85 : 0.7}
          />
        </g>
      ))}
      {/* Equity curve overlay */}
      <polyline
        points="16,170 45,148 74,155 103,130 132,137 161,118 190,110 219,122 248,100 277,90 306,78"
        fill="none"
        stroke="var(--color-brand)"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity="0.6"
      />
    </svg>
  )
}

function JournalIllustration() {
  const trades = [
    { sym: 'RELIANCE', dir: 'LONG', pnl: '+₹4,250', score: 8, up: true },
    { sym: 'NIFTY24DEC', dir: 'SHORT', pnl: '-₹1,120', score: 6, up: false },
    { sym: 'HDFCBANK', dir: 'LONG', pnl: '+₹7,680', score: 9, up: true },
  ]
  const emotions = ['Calm', 'Confident', 'Focused']

  return (
    <svg viewBox="0 0 320 200" xmlns="http://www.w3.org/2000/svg" className="w-full" aria-hidden="true">
      <rect width="320" height="200" rx="12" fill="var(--color-surface-base)" />
      <rect width="320" height="200" rx="12" fill="none" stroke="var(--color-border)" />
      <text x="16" y="26" fontSize="9" fontWeight="600" fill="var(--color-text-muted)" fontFamily="system-ui">Trade Journal</text>
      {/* Emotion chips */}
      {emotions.map((e, i) => (
        <g key={e}>
          <rect x={16 + i * 72} y="34" width={64} height="16" rx="8" fill="var(--color-brand)" opacity="0.12" />
          <text x={16 + i * 72 + 32} y="46" fontSize="7.5" fill="var(--color-brand)" textAnchor="middle" fontFamily="system-ui">{e}</text>
        </g>
      ))}
      {/* Trade rows */}
      {trades.map((t, i) => (
        <g key={t.sym}>
          <rect x="16" y={60 + i * 42} width="288" height="36" rx="6" fill="var(--color-surface-subtle)" />
          {/* Dir badge */}
          <rect x="24" y={66 + i * 42} width="30" height="14" rx="3" fill={t.up ? 'var(--color-surface-success)' : 'var(--color-surface-danger)'} />
          <text x="39" y={77 + i * 42} fontSize="7" fontWeight="700" fill={t.up ? 'var(--color-success)' : 'var(--color-danger)'} textAnchor="middle" fontFamily="system-ui">{t.dir}</text>
          {/* Symbol */}
          <text x="62" y={77 + i * 42} fontSize="8" fontWeight="600" fill="var(--color-text-primary)" fontFamily="monospace">{t.sym}</text>
          {/* P&L */}
          <text x="220" y={77 + i * 42} fontSize="8.5" fontWeight="700" fill={t.up ? 'var(--color-success)' : 'var(--color-danger)'} fontFamily="monospace">{t.pnl}</text>
          {/* Discipline score */}
          <text x="272" y={72 + i * 42} fontSize="7" fill="var(--color-text-muted)" textAnchor="middle" fontFamily="system-ui">Score</text>
          <text x="272" y={84 + i * 42} fontSize="10" fontWeight="700" fill="var(--color-brand)" textAnchor="middle" fontFamily="system-ui">{t.score}</text>
        </g>
      ))}
    </svg>
  )
}

function RiskIllustration() {
  const positions = [
    { sym: 'NIFTY FUT', size: 85, color: 'var(--color-brand)' },
    { sym: 'BANKNIFTY', size: 62, color: 'var(--color-success)' },
    { sym: 'RELIANCE', size: 44, color: 'var(--color-warning)' },
    { sym: 'INFY OPT', size: 28, color: 'var(--color-danger)' },
  ]

  return (
    <svg viewBox="0 0 320 200" xmlns="http://www.w3.org/2000/svg" className="w-full" aria-hidden="true">
      <rect width="320" height="200" rx="12" fill="var(--color-surface-base)" />
      <rect width="320" height="200" rx="12" fill="none" stroke="var(--color-border)" />
      <text x="16" y="26" fontSize="9" fontWeight="600" fill="var(--color-text-muted)" fontFamily="system-ui">Risk Dashboard</text>
      {/* Portfolio heat bar */}
      <text x="16" y="46" fontSize="7.5" fill="var(--color-text-muted)" fontFamily="system-ui">Portfolio heat</text>
      <rect x="16" y="52" width="288" height="12" rx="6" fill="var(--color-surface-subtle)" />
      <rect x="16" y="52" width="172" height="12" rx="6" fill="var(--color-warning)" opacity="0.7" />
      <text x="195" y="62" fontSize="7" fill="var(--color-warning)" fontFamily="system-ui">59.7%</text>
      {/* Position bars */}
      <text x="16" y="82" fontSize="7.5" fill="var(--color-text-muted)" fontFamily="system-ui">Open positions</text>
      {positions.map((p, i) => (
        <g key={p.sym}>
          <text x="16" y={97 + i * 24} fontSize="8" fill="var(--color-text-secondary)" fontFamily="monospace">{p.sym}</text>
          <rect x="100" y={86 + i * 24} width="180" height="12" rx="4" fill="var(--color-surface-subtle)" />
          <rect x="100" y={86 + i * 24} width={p.size * 1.8} height="12" rx="4" fill={p.color} opacity="0.75" />
          <text x="290" y={97 + i * 24} fontSize="7.5" fill="var(--color-text-muted)" fontFamily="system-ui">{p.size}%</text>
        </g>
      ))}
      {/* Max drawdown tile */}
      <rect x="16" y="184" width="84" height="0" rx="6" fill="var(--color-surface-subtle)" />
      <text x="16" y="178" fontSize="7.5" fill="var(--color-text-muted)" fontFamily="system-ui">Max drawdown</text>
      <text x="16" y="194" fontSize="13" fontWeight="700" fill="var(--color-danger)" fontFamily="monospace">9.2%</text>
      <text x="140" y="178" fontSize="7.5" fill="var(--color-text-muted)" fontFamily="system-ui">Risk per trade</text>
      <text x="140" y="194" fontSize="13" fontWeight="700" fill="var(--color-text-primary)" fontFamily="monospace">1.0R</text>
      <text x="240" y="178" fontSize="7.5" fill="var(--color-text-muted)" fontFamily="system-ui">Daily loss limit</text>
      <text x="240" y="194" fontSize="13" fontWeight="700" fill="var(--color-success)" fontFamily="monospace">₹8,000</text>
    </svg>
  )
}

const GALLERY = [
  {
    title: 'Performance Analytics',
    desc: 'Win rate, expectancy, profit factor — every number that reveals your real edge.',
    Illustration: AnalyticsIllustration,
  },
  {
    title: 'Trade Journal',
    desc: 'Log entries with emotion tags and discipline scores. Build your trading process.',
    Illustration: JournalIllustration,
  },
  {
    title: 'Risk Dashboard',
    desc: 'Portfolio heat, position sizing, and drawdown tiers to protect your capital.',
    Illustration: RiskIllustration,
  },
]

// ─── Dashboard Mockup ─────────────────────────────────────────────────────────

function DashboardMockup() {
  const mockTrades = [
    { symbol: 'RELIANCE', type: 'LONG', pnl: '+₹4,250', positive: true },
    { symbol: 'INFY', type: 'SHORT', pnl: '-₹1,120', positive: false },
    { symbol: 'HDFCBANK', type: 'LONG', pnl: '+₹7,680', positive: true },
    { symbol: 'TCS', type: 'LONG', pnl: '+₹2,190', positive: true },
  ]

  return (
    <div
      className="relative w-full max-w-lg rounded-2xl border border-border bg-surface-base shadow-2xl"
      style={{ boxShadow: '0 32px 80px rgba(0,0,0,0.28), 0 0 0 1px rgba(255,255,255,0.04)' }}
      aria-hidden="true"
    >
      {/* Titlebar */}
      <div className="flex items-center gap-1.5 rounded-t-2xl border-b border-border bg-surface-subtle px-4 py-3">
        <span className="h-2.5 w-2.5 rounded-full bg-danger/60" />
        <span className="h-2.5 w-2.5 rounded-full bg-warning/60" />
        <span className="h-2.5 w-2.5 rounded-full bg-success/60" />
        <span className="ml-3 text-xs font-medium text-text-muted">TradeForge — Dashboard</span>
      </div>

      <div className="p-4">
        {/* Stats row */}
        <div className="mb-4 grid grid-cols-3 gap-3">
          {[
            { label: 'Total P&L', value: '+₹2,47,850', up: true },
            { label: 'Win Rate', value: '68.4%', up: true },
            { label: 'R:R Ratio', value: '2.41', up: null },
          ].map((s) => (
            <div key={s.label} className="rounded-lg border border-border bg-surface-subtle p-3">
              <p className="mb-0.5 text-[10px] font-medium text-text-muted">{s.label}</p>
              <p
                className={`font-mono text-sm font-semibold ${s.up === true ? 'text-success' : s.up === false ? 'text-danger' : 'text-text-primary'}`}
              >
                {s.value}
              </p>
            </div>
          ))}
        </div>

        {/* 3D equity curve */}
        <div className="mb-4 overflow-hidden rounded-lg border border-border bg-surface-subtle">
          <div className="border-b border-border px-3 py-2">
            <p className="text-[10px] font-medium text-text-muted">Equity Curve</p>
          </div>
          {/* Perspective 3D wrapper */}
          <div style={{ perspective: '600px', perspectiveOrigin: '50% 80%' }}>
            <div
              style={{
                transform: 'rotateX(14deg) scaleX(1.04)',
                transformOrigin: 'bottom center',
                transformStyle: 'preserve-3d',
              }}
            >
              <EquityCurveCanvas className="h-24 w-full" durationMs={2800} />
            </div>
          </div>
        </div>

        {/* Recent trades */}
        <div className="space-y-1.5">
          <p className="mb-2 text-[10px] font-semibold text-text-muted">
            Recent Trades
          </p>
          {mockTrades.map((t) => (
            <div
              key={t.symbol}
              className="flex items-center justify-between rounded-md px-2 py-1.5 hover:bg-surface-subtle"
            >
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs font-semibold text-text-primary">
                  {t.symbol}
                </span>
                <span
                  className={`rounded px-1.5 py-0.5 text-[9px] font-semibold ${t.type === 'LONG' ? 'bg-surface-success text-success' : 'bg-surface-danger text-danger'}`}
                >
                  {t.type}
                </span>
              </div>
              <span
                className={`font-mono text-xs font-semibold ${t.positive ? 'text-success' : 'text-danger'}`}
              >
                {t.pnl}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ─── How it works ─────────────────────────────────────────────────────────────

const HOW_IT_WORKS = [
  {
    step: '01',
    title: 'Connect your broker',
    desc: 'Import trades via CSV or connect directly to Zerodha, Upstox, and Angel One.',
  },
  {
    step: '02',
    title: 'Review your patterns',
    desc: 'See win rates, expectancy, drawdown, and every metric that exposes your edge.',
  },
  {
    step: '03',
    title: 'Improve your process',
    desc: 'Journal trades, score your discipline, and track progress week over week.',
  },
]

const FEATURES = [
  {
    size: 'large',
    title: 'Performance Analytics',
    desc: 'Win rate, expectancy, profit factor, Sharpe ratio, MAE/MFE — every number that separates consistent traders from gamblers. Updated live.',
    tags: ['Equity Curve', 'Drawdown', 'R-Multiples'],
  },
  {
    size: 'large',
    title: 'Trade Journal',
    desc: 'Log every trade with notes, emotional state, and discipline score. Build the habit of reflection that separates professionals from the rest.',
    tags: ['Discipline Score', 'Pattern Recognition', 'Notes'],
  },
  {
    size: 'small',
    title: 'Broker Import',
    desc: 'CSV import from Zerodha, Upstox, and Angel One. Trades populate automatically.',
  },
  {
    size: 'small',
    title: 'Risk Management',
    desc: 'Position sizing, portfolio heat, drawdown tiers — protect your capital.',
  },
  {
    size: 'small',
    title: 'Multi-Account',
    desc: 'Track separate accounts for different strategies. One login, full picture.',
  },
]

// ─── LandingPage ─────────────────────────────────────────────────────────────

export function LandingPage() {
  const { theme, toggle } = useTheme()
  const isDark = theme === 'dark'

  // Scroll-driven nav
  const { scrollY } = useScroll()
  const navBg = useTransform(scrollY, [0, 60], [0, 1])

  // Section refs for whileInView (mobile fallback)
  const galleryRef = useRef<HTMLElement>(null)
  const galleryInView = useInView(galleryRef, { once: true, margin: '-80px' })

  return (
    <div className="min-h-screen bg-canvas text-text-primary">
      {/* ── Nav ─────────────────────────────────────────────── */}
      <motion.header
        className="sticky top-0 z-40 border-b"
        style={{
          borderColor: `color-mix(in srgb, var(--color-border) calc(${navBg} * 100%), transparent)`,
          backgroundColor: `color-mix(in srgb, var(--color-canvas) calc(${navBg} * 90%), transparent)`,
          backdropFilter: 'blur(12px)',
        }}
      >
        <nav
          data-testid="landing-nav"
          className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4"
          aria-label="Landing page navigation"
        >
          <span className="text-lg font-extrabold tracking-tight text-brand">TradeForge</span>
          <div className="flex items-center gap-3">
            <button
              type="button"
              data-testid="theme-toggle"
              onClick={toggle}
              aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
              className="flex items-center justify-center rounded-lg p-2 text-text-secondary hover:bg-surface-base hover:text-text-primary focus:outline-none focus:ring-2 focus:ring-brand/50"
            >
              <span className={isDark ? 'text-toggle-moon' : 'text-toggle-sun'}>
                {isDark ? <IconMoon /> : <IconSun />}
              </span>
            </button>
            <Link
              to="/login"
              className="rounded-lg px-4 py-2 text-sm font-medium text-text-secondary hover:text-text-primary focus:outline-none focus:ring-2 focus:ring-brand/50"
            >
              Sign in
            </Link>
            <Link
              to="/register"
              className="rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-brand-emphasis focus:outline-none focus:ring-2 focus:ring-brand/50"
            >
              Get started
            </Link>
          </div>
        </nav>
      </motion.header>

      {/* ── Hero ─────────────────────────────────────────────── */}
      <section
        data-testid="landing-hero"
        className="relative overflow-hidden px-6 pb-24 pt-10 md:pt-16"
        style={isDark
          ? { background: '#000e06' }
          : { background: 'linear-gradient(160deg, #e8f9ef 0%, #f4fdf7 50%, #ffffff 100%)' }
        }
        aria-label="Hero"
      >
        <HeroBackground
          dark={isDark}
          className="pointer-events-none absolute inset-0 h-full w-full"
        />

        {/* CRT scan-line overlay */}
        <div
          className="pointer-events-none absolute inset-0"
          aria-hidden="true"
          style={{
            background:
              'repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.025) 2px, rgba(0,0,0,0.025) 4px)',
          }}
        />

        {/* Edge vignette — darkens far corners only, keeps lines visible in mid */}
        <div
          className="pointer-events-none absolute inset-0"
          aria-hidden="true"
          style={{
            background: isDark
              ? 'radial-gradient(ellipse 90% 80% at 50% 50%, transparent 45%, rgba(5,6,20,0.45) 100%)'
              : 'radial-gradient(ellipse 90% 80% at 50% 50%, transparent 45%, rgba(255,255,255,0.40) 100%)',
          }}
        />

        {/* Brand glow — left of hero copy */}
        <div
          className="pointer-events-none absolute left-1/4 top-0 h-[32rem] w-[32rem] -translate-x-1/2 rounded-full blur-3xl"
          style={{ background: isDark ? 'rgba(91,82,242,0.10)' : 'rgba(79,70,229,0.05)' }}
          aria-hidden="true"
        />

        {/* Bottom fade into next section */}
        <div
          className="pointer-events-none absolute bottom-0 left-0 right-0 h-24"
          aria-hidden="true"
          style={{
            background: isDark
              ? 'linear-gradient(to bottom, transparent, #000e06)'
              : 'linear-gradient(to bottom, transparent, var(--color-canvas))',
          }}
        />

        <div className="relative mx-auto flex max-w-6xl flex-col items-center gap-16 lg:flex-row lg:items-center lg:gap-14">
          {/* Left: copy */}
          <motion.div
            className="flex-1 pt-4"
            initial="hidden"
            animate="visible"
            variants={stagger}
          >
            <motion.p
              variants={fadeUp}
              className="mb-4 inline-flex items-center gap-2 rounded-full border border-brand/30 bg-brand/8 px-4 py-1.5 text-xs font-semibold text-brand"
              style={{ background: isDark ? 'rgba(91,82,242,0.1)' : 'rgba(79,70,229,0.06)' }}
            >
              Trading Intelligence Platform
            </motion.p>

            <motion.h1
              variants={fadeUp}
              className="mb-6 text-4xl font-extrabold leading-tight tracking-tight text-text-primary md:text-5xl lg:text-[3.25rem]"
            >
              Stop guessing.
              <br />
              <span className="text-brand">Start compounding.</span>
            </motion.h1>

            <motion.p
              variants={fadeUp}
              className="mb-8 max-w-md text-lg leading-relaxed text-text-secondary"
            >
              TradeForge turns your trade history into a performance engine — analytics, journaling,
              and risk management in one place.
            </motion.p>

            {/* Live fluctuating P&L */}
            <motion.div
              variants={fadeUp}
              className="mb-8 inline-flex items-baseline gap-2.5 rounded-xl border border-border bg-surface-base/80 px-5 py-3 backdrop-blur-sm"
            >
              <span className="h-2 w-2 rounded-full bg-success animate-pulse" aria-hidden="true" />
              <PnLCounter className="font-mono text-2xl font-bold text-success" />
              <span className="text-sm font-medium text-text-secondary">realised P&L</span>
            </motion.div>

            <motion.div variants={fadeUp} className="flex flex-wrap gap-3">
              <Link
                to="/register"
                className="inline-flex items-center gap-2 rounded-xl bg-brand px-6 py-3 text-base font-semibold text-white hover:bg-brand-emphasis focus:outline-none focus:ring-2 focus:ring-brand/50"
              >
                Start for free
                <IconArrowRight />
              </Link>
              <Link
                to="/login"
                className="rounded-xl border border-border px-6 py-3 text-base font-medium text-text-secondary hover:border-brand hover:text-text-primary focus:outline-none focus:ring-2 focus:ring-brand/50"
              >
                Sign in
              </Link>
            </motion.div>

            <motion.ul
              variants={fadeUp}
              className="mt-6 flex flex-wrap gap-x-6 gap-y-2 text-sm text-text-muted"
            >
              {['Free to start', 'No credit card', 'CSV import in 30 seconds'].map((t) => (
                <li key={t} className="flex items-center gap-1.5">
                  <span className="text-success">
                    <IconCheck />
                  </span>
                  {t}
                </li>
              ))}
            </motion.ul>
          </motion.div>

          {/* Right: dashboard mockup */}
          <motion.div
            className="w-full flex-shrink-0 lg:w-auto"
            initial={{ opacity: 0, x: 32, scale: 0.96 }}
            animate={{ opacity: 1, x: 0, scale: 1 }}
            transition={{ duration: 0.7, delay: 0.2, ease: [0.22, 1, 0.36, 1] }}
          >
            <DashboardMockup />
          </motion.div>
        </div>
      </section>

      {/* ── Broker strip ─────────────────────────────────────── */}
      <div className="border-y border-border bg-surface-base py-8">
        <p className="mb-6 text-center text-xs font-semibold uppercase tracking-widest text-text-muted">
          Connects with your broker
        </p>
        {/* Marquee: single flat track, duplicated list. JS measures exact pixel offset of
            item[6] (first duplicate) and sets --marquee-offset, so the loop point is
            pixel-perfect regardless of label widths. */}
        <div className="overflow-hidden [mask-image:linear-gradient(to_right,transparent,black_12%,black_88%,transparent)]">
          <BrokerMarquee />
        </div>
      </div>

      {/* ── Product Gallery ───────────────────────────────────── */}
      <section
        ref={galleryRef}
        className="px-6 py-24"
        aria-label="Product overview"
      >
        <div className="mx-auto max-w-6xl">
          <motion.div
            className="mb-16 max-w-2xl"
            initial={{ opacity: 0, y: 24 }}
            animate={galleryInView ? { opacity: 1, y: 0 } : {}}
            transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
          >
            <h2 className="mb-4 text-3xl font-bold tracking-tight text-text-primary md:text-4xl">
              Everything in one place
            </h2>
            <p className="text-lg text-text-secondary">
              A full-stack view of your trading performance. Not just a spreadsheet — a system
              that learns your patterns and surfaces what matters.
            </p>
          </motion.div>

          <motion.div
            className="grid grid-cols-1 gap-6 md:grid-cols-3"
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: '-60px' }}
            variants={stagger}
          >
            {GALLERY.map(({ title, desc, Illustration }) => (
              <motion.div
                key={title}
                variants={fadeUp}
                className="overflow-hidden rounded-2xl border border-border bg-surface-base"
              >
                {/* Illustration */}
                <div className="border-b border-border bg-surface-subtle p-4">
                  <Illustration />
                </div>
                {/* Caption */}
                <div className="p-5">
                  <h3 className="mb-1.5 text-base font-semibold text-text-primary">{title}</h3>
                  <p className="text-sm leading-relaxed text-text-secondary">{desc}</p>
                </div>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* ── How it works ─────────────────────────────────────── */}
      <section className="bg-surface-base px-6 py-24" aria-label="How it works">
        <div className="mx-auto max-w-6xl">
          <motion.h2
            className="mb-16 text-3xl font-bold tracking-tight text-text-primary md:text-4xl"
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5 }}
          >
            Live in minutes
          </motion.h2>
          <motion.div
            className="grid grid-cols-1 gap-8 md:grid-cols-3"
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: '-60px' }}
            variants={stagger}
          >
            {HOW_IT_WORKS.map((s, i) => (
              <motion.div key={s.step} className="relative" variants={fadeUp}>
                {i < HOW_IT_WORKS.length - 1 && (
                  <div
                    className="absolute left-8 top-8 hidden h-px w-full bg-border md:block"
                    aria-hidden="true"
                  />
                )}
                <div className="relative mb-5 flex h-16 w-16 items-center justify-center rounded-2xl border border-border bg-surface-subtle">
                  <span className="font-mono text-sm font-bold text-brand">{s.step}</span>
                </div>
                <h3 className="mb-2 text-lg font-semibold text-text-primary">{s.title}</h3>
                <p className="text-sm leading-relaxed text-text-secondary">{s.desc}</p>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* ── Features ─────────────────────────────────────────── */}
      <section
        data-testid="landing-features"
        className="bg-canvas px-6 py-24"
        aria-label="Features"
      >
        <div className="mx-auto max-w-6xl">
          <motion.h2
            className="mb-16 text-3xl font-bold tracking-tight text-text-primary md:text-4xl"
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5 }}
          >
            Built for the serious trader
          </motion.h2>
          <motion.div
            className="grid grid-cols-1 gap-4 md:grid-cols-3"
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: '-60px' }}
            variants={stagger}
          >
            {FEATURES.filter((f) => f.size === 'large').map((f) => (
              <motion.div
                key={f.title}
                variants={fadeUp}
                className="flex flex-col justify-between rounded-2xl border border-border bg-surface-base p-8"
              >
                <div>
                  <h3 className="mb-3 text-xl font-bold text-text-primary">{f.title}</h3>
                  <p className="text-sm leading-relaxed text-text-secondary">{f.desc}</p>
                </div>
                {f.tags && (
                  <div className="mt-6 flex flex-wrap gap-2">
                    {f.tags.map((tag) => (
                      <span
                        key={tag}
                        className="rounded-full border border-border px-3 py-1 text-xs font-medium text-text-secondary"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                )}
              </motion.div>
            ))}
            <div className="flex flex-col gap-4">
              {FEATURES.filter((f) => f.size === 'small').map((f) => (
                <motion.div
                  key={f.title}
                  variants={fadeUp}
                  className="rounded-2xl border border-border bg-surface-base p-6"
                >
                  <h3 className="mb-2 text-base font-semibold text-text-primary">{f.title}</h3>
                  <p className="text-sm text-text-secondary">{f.desc}</p>
                </motion.div>
              ))}
            </div>
          </motion.div>
        </div>
      </section>

      {/* ── CTA ──────────────────────────────────────────────── */}
      <section
        data-testid="landing-cta-band"
        className="px-6 py-24"
        aria-label="Call to action"
      >
        <motion.div
          className="mx-auto max-w-2xl rounded-2xl border border-brand/30 px-8 py-16 text-center"
          style={{ background: isDark ? 'rgba(91,82,242,0.08)' : 'rgba(79,70,229,0.05)' }}
          initial={{ opacity: 0, y: 32 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
        >
          <h2 className="mb-4 text-3xl font-bold tracking-tight text-text-primary md:text-4xl">
            Your edge is one decision away
          </h2>
          <p className="mb-8 text-lg text-text-secondary">
            Join traders who use data — not instinct — to improve their process.
          </p>
          <Link
            to="/register"
            className="inline-flex items-center gap-2 rounded-xl bg-brand px-8 py-3.5 text-base font-semibold text-white hover:bg-brand-emphasis focus:outline-none focus:ring-2 focus:ring-brand/50"
          >
            Create your free account
            <IconArrowRight />
          </Link>
        </motion.div>
      </section>

      {/* ── Footer ───────────────────────────────────────────── */}
      <footer className="border-t border-border px-6 py-12">
        <div className="mx-auto max-w-6xl">
          <div className="flex flex-col items-start justify-between gap-8 md:flex-row md:items-center">
            <div>
              <span className="text-lg font-extrabold tracking-tight text-brand">TradeForge</span>
              <p className="mt-1 text-sm text-text-muted">Trading intelligence for serious traders.</p>
            </div>
            <div className="flex flex-wrap gap-6 text-sm text-text-muted">
              {[
                { label: 'Sign in', to: '/login' },
                { label: 'Get started', to: '/register' },
              ].map((l) => (
                <Link
                  key={l.label}
                  to={l.to}
                  className="hover:text-text-primary focus:outline-none focus:ring-2 focus:ring-brand/50"
                >
                  {l.label}
                </Link>
              ))}
            </div>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={toggle}
                aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
                className="flex items-center justify-center rounded-lg p-2 text-text-secondary hover:bg-surface-base hover:text-text-primary focus:outline-none focus:ring-2 focus:ring-brand/50"
              >
                <span className={isDark ? 'text-toggle-moon' : 'text-toggle-sun'}>
                  {isDark ? <IconMoon /> : <IconSun />}
                </span>
              </button>
              <span className="text-sm text-text-muted">
                © {new Date().getFullYear()} TradeForge
              </span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  )
}
