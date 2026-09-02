'use client'

interface ProgressBarProps {
  value: number   // 0–100
  variant?: 'accent' | 'warning' | 'success'
  showLabel?: boolean
  className?: string
}

export function ProgressBar({
  value,
  variant = 'accent',
  showLabel = false,
  className = '',
}: ProgressBarProps) {
  const clampedValue = Math.min(100, Math.max(0, value))

  return (
    <div className={`progress-bar ${className}`} role="progressbar" aria-valuenow={clampedValue} aria-valuemin={0} aria-valuemax={100}>
      <div className="progress-bar__track">
        <div
          className={`progress-bar__fill progress-bar__fill--${variant}`}
          style={{ width: `${clampedValue}%` }}
        />
      </div>
      {showLabel && (
        <span className="progress-bar__label">{clampedValue}%</span>
      )}
    </div>
  )
}
