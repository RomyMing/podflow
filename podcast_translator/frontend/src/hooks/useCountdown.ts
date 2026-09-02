import { useState, useEffect, useCallback } from 'react'

export function useCountdown(initialSeconds: number = 60) {
  const [seconds, setSeconds] = useState(0)

  useEffect(() => {
    if (seconds <= 0) return
    const timer = setInterval(() => {
      setSeconds(prev => Math.max(0, prev - 1))
    }, 1000)
    return () => clearInterval(timer)
  }, [seconds])

  const start = useCallback(() => {
    setSeconds(initialSeconds)
  }, [initialSeconds])

  return {
    seconds,
    isActive: seconds > 0,
    start
  }
}
