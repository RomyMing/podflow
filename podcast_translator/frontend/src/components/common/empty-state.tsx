'use client'

import Link from 'next/link'

interface EmptyStateProps {
  icon?: string
  title: string
  description?: string
  ctaLabel?: string
  ctaHref?: string
  onCtaClick?: () => void
  className?: string
}

export function EmptyState({
  icon = '📭',
  title,
  description,
  ctaLabel,
  ctaHref,
  onCtaClick,
  className = '',
}: EmptyStateProps) {
  return (
    <div className={`empty-state ${className}`} role="status">
      <div className="empty-state__icon" aria-hidden="true">{icon}</div>
      <p className="empty-state__title">{title}</p>
      {description && (
        <p className="empty-state__desc">{description}</p>
      )}
      {ctaLabel && (
        ctaHref ? (
          <Link href={ctaHref} className="empty-state__cta" id="empty-state-cta">
            {ctaLabel}
          </Link>
        ) : (
          <button className="empty-state__cta" onClick={onCtaClick} id="empty-state-cta">
            {ctaLabel}
          </button>
        )
      )}
    </div>
  )
}
