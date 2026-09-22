import { useEffect, useRef } from 'react'

// Normalised (0–1) equity curve path: x = time progress, y = portfolio value (0=top, 1=bottom)
const POINTS = [
  { x: 0.00, y: 0.78 },
  { x: 0.07, y: 0.74 },
  { x: 0.13, y: 0.80 },
  { x: 0.20, y: 0.68 },
  { x: 0.27, y: 0.72 },
  { x: 0.33, y: 0.60 },
  { x: 0.40, y: 0.63 },
  { x: 0.47, y: 0.50 },
  { x: 0.53, y: 0.54 },
  { x: 0.60, y: 0.42 },
  { x: 0.67, y: 0.38 },
  { x: 0.73, y: 0.44 },
  { x: 0.80, y: 0.30 },
  { x: 0.87, y: 0.26 },
  { x: 0.93, y: 0.32 },
  { x: 1.00, y: 0.18 },
]

function easeInOutCubic(t: number) {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2
}

function drawFrame(
  ctx: CanvasRenderingContext2D,
  progress: number,
  w: number,
  h: number,
  lineColor: string,
  fillColor: string,
) {
  ctx.clearRect(0, 0, w, h)

  const total = POINTS.length - 1
  const rawIdx = progress * total
  const floorIdx = Math.floor(rawIdx)
  const frac = rawIdx - floorIdx
  const drawCount = Math.min(floorIdx, total - 1)

  if (progress <= 0) return

  // Compute all drawable points
  const pts: { x: number; y: number }[] = []
  for (let i = 0; i <= drawCount; i++) {
    pts.push({ x: POINTS[i].x * w, y: POINTS[i].y * h })
  }
  // Partial last segment
  if (floorIdx < total) {
    const a = POINTS[floorIdx]
    const b = POINTS[floorIdx + 1]
    pts.push({
      x: (a.x + (b.x - a.x) * frac) * w,
      y: (a.y + (b.y - a.y) * frac) * h,
    })
  }

  if (pts.length < 2) return

  const lastPt = pts[pts.length - 1]

  // Filled area under the curve
  ctx.beginPath()
  ctx.moveTo(pts[0].x, pts[0].y)
  for (let i = 1; i < pts.length; i++) {
    const prev = pts[i - 1]
    const curr = pts[i]
    const cpx = (prev.x + curr.x) / 2
    ctx.bezierCurveTo(cpx, prev.y, cpx, curr.y, curr.x, curr.y)
  }
  ctx.lineTo(lastPt.x, h)
  ctx.lineTo(pts[0].x, h)
  ctx.closePath()

  const grad = ctx.createLinearGradient(0, 0, 0, h)
  grad.addColorStop(0, fillColor)
  grad.addColorStop(1, 'transparent')
  ctx.fillStyle = grad
  ctx.fill()

  // The line itself
  ctx.beginPath()
  ctx.moveTo(pts[0].x, pts[0].y)
  for (let i = 1; i < pts.length; i++) {
    const prev = pts[i - 1]
    const curr = pts[i]
    const cpx = (prev.x + curr.x) / 2
    ctx.bezierCurveTo(cpx, prev.y, cpx, curr.y, curr.x, curr.y)
  }
  ctx.strokeStyle = lineColor
  ctx.lineWidth = 2
  ctx.lineJoin = 'round'
  ctx.lineCap = 'round'
  ctx.stroke()

  // Live dot at the cursor
  if (progress < 1) {
    ctx.beginPath()
    ctx.arc(lastPt.x, lastPt.y, 4, 0, Math.PI * 2)
    ctx.fillStyle = lineColor
    ctx.fill()
  }
}

interface EquityCurveCanvasProps {
  className?: string
  lineColor?: string
  fillColor?: string
  durationMs?: number
}

export function EquityCurveCanvas({
  className,
  lineColor = '#16DBA1',
  fillColor = 'rgba(22,219,161,0.09)',
  durationMs = 2200,
}: EquityCurveCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const prefersReduced =
      typeof window.matchMedia === 'function'
        ? window.matchMedia('(prefers-reduced-motion: reduce)').matches
        : false

    let raf: number
    const startTime = performance.now()

    function resize() {
      if (!canvas) return
      const dpr = window.devicePixelRatio || 1
      const { width, height } = canvas.getBoundingClientRect()
      canvas.width = width * dpr
      canvas.height = height * dpr
      ctx!.scale(dpr, dpr)
    }

    resize()

    if (prefersReduced) {
      drawFrame(ctx, 1, canvas.getBoundingClientRect().width, canvas.getBoundingClientRect().height, lineColor, fillColor)
      return
    }

    function tick(now: number) {
      const raw = (now - startTime) / durationMs
      const progress = easeInOutCubic(Math.min(raw, 1))
      const { width, height } = canvas!.getBoundingClientRect()
      drawFrame(ctx!, progress, width, height, lineColor, fillColor)
      if (raw < 1) {
        raf = requestAnimationFrame(tick)
      }
    }

    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [lineColor, fillColor, durationMs])

  return <canvas ref={canvasRef} className={className} aria-hidden="true" />
}
