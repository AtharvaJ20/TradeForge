import { useEffect, useRef } from 'react'

interface Particle {
  x: number
  y: number
  r: number
  vx: number
  vy: number
  alpha: number
}

export function HeroBackground({ className, dark = true }: { className?: string; dark?: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const prefersReduced =
      typeof window.matchMedia === 'function' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches

    let W = 0, H = 0, raf = 0
    const particles: Particle[] = []
    const NUM = 90

    function resize() {
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      const rect = canvas!.getBoundingClientRect()
      W = rect.width
      H = rect.height
      canvas!.width  = W * dpr
      canvas!.height = H * dpr
      ctx.setTransform(1, 0, 0, 1, 0, 0)
      ctx.scale(dpr, dpr)
      initParticles()
    }

    function initParticles() {
      particles.length = 0
      for (let i = 0; i < NUM; i++) {
        particles.push({
          x:     Math.random() * W,
          y:     Math.random() * H,
          r:     1.0 + Math.random() * 2.2,
          vx:    (Math.random() - 0.5) * 0.18,
          vy:    -(0.20 + Math.random() * 0.45),
          alpha: 0.30 + Math.random() * 0.45,
        })
      }
    }

    let t = 0

    function draw() {
      ctx.clearRect(0, 0, W, H)
      t += 0.003

      const s = dark ? 1 : 0.35   // scale blob opacity down in light mode

      // ── Blob 1: upper-right ───────────────────────────────────────────────
      const b1x = W * (0.70 + Math.sin(t * 0.55) * 0.14)
      const b1y = H * (0.20 + Math.cos(t * 0.40) * 0.12)
      const g1  = ctx.createRadialGradient(b1x, b1y, 0, b1x, b1y, W * 0.55)
      g1.addColorStop(0,   `rgba(0,200,70,${0.28 * s})`)
      g1.addColorStop(0.4, `rgba(0,150,50,${0.12 * s})`)
      g1.addColorStop(1,   'rgba(0,0,0,0)')
      ctx.fillStyle = g1
      ctx.fillRect(0, 0, W, H)

      // ── Blob 2: lower-left ───────────────────────────────────────────────
      const b2x = W * (0.15 + Math.cos(t * 0.48) * 0.11)
      const b2y = H * (0.65 + Math.sin(t * 0.62) * 0.13)
      const g2  = ctx.createRadialGradient(b2x, b2y, 0, b2x, b2y, W * 0.45)
      g2.addColorStop(0,   `rgba(0,170,80,${0.20 * s})`)
      g2.addColorStop(0.5, `rgba(0,110,50,${0.08 * s})`)
      g2.addColorStop(1,   'rgba(0,0,0,0)')
      ctx.fillStyle = g2
      ctx.fillRect(0, 0, W, H)

      // ── Blob 3: center, slow pulse ────────────────────────────────────────
      const b3x = W * (0.48 + Math.sin(t * 0.32) * 0.08)
      const b3y = H * (0.42 + Math.cos(t * 0.28) * 0.10)
      const g3  = ctx.createRadialGradient(b3x, b3y, 0, b3x, b3y, W * 0.40)
      g3.addColorStop(0,   `rgba(0,220,90,${0.10 * s})`)
      g3.addColorStop(1,   'rgba(0,0,0,0)')
      ctx.fillStyle = g3
      ctx.fillRect(0, 0, W, H)

      // ── Particles with glow ───────────────────────────────────────────────
      ctx.shadowColor = 'rgba(0,220,90,0.6)'
      ctx.shadowBlur  = 6
      for (const p of particles) {
        p.x += p.vx
        p.y += p.vy

        if (p.y < -6)    { p.y = H + 6; p.x = Math.random() * W }
        if (p.x < -6)      p.x = W + 6
        if (p.x > W + 6)   p.x = -6

        ctx.beginPath()
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
        ctx.fillStyle = `rgba(0,230,100,${p.alpha})`
        ctx.fill()
      }
      ctx.shadowBlur = 0
    }

    function frame() {
      draw()
      raf = requestAnimationFrame(frame)
    }

    resize()

    if (prefersReduced) {
      draw()
    } else {
      raf = requestAnimationFrame(frame)
    }

    const ro = new ResizeObserver(resize)
    ro.observe(canvas)

    return () => {
      cancelAnimationFrame(raf)
      ro.disconnect()
    }
  }, [dark])

  return <canvas ref={canvasRef} className={className} aria-hidden="true" />
}
