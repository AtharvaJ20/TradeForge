import { useEffect, useRef, useState } from 'react'
import { animate } from 'framer-motion'

function formatINR(value: number) {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(Math.round(value))
}

interface PnLCounterProps {
  className?: string
}

const BASE = 247850

export function PnLCounter({ className }: PnLCounterProps) {
  const [display, setDisplay] = useState(formatINR(BASE))
  const currentRef = useRef(BASE)
  const stopRef = useRef<(() => void) | null>(null)

  useEffect(() => {
    const prefersReduced =
      typeof window.matchMedia === 'function'
        ? window.matchMedia('(prefers-reduced-motion: reduce)').matches
        : false

    if (prefersReduced) {
      setDisplay(formatINR(BASE))
      return
    }

    function tick() {
      const prev = currentRef.current
      const delta = (Math.random() - 0.42) * 5500 // slight upward bias
      const next = Math.max(215000, Math.min(292000, prev + delta))
      currentRef.current = next

      if (stopRef.current) stopRef.current()
      const controls = animate(prev, next, {
        duration: 1.1,
        ease: 'easeOut',
        onUpdate: (v) => setDisplay(formatINR(v)),
      })
      stopRef.current = () => controls.stop()
    }

    tick()
    const id = setInterval(tick, 2400)
    return () => {
      clearInterval(id)
      stopRef.current?.()
    }
  }, [])

  return (
    <span className={className} aria-live="polite" aria-label={display}>
      {display}
    </span>
  )
}
