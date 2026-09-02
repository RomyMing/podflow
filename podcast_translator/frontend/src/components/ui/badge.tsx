'use client'

import React from 'react'
import { cn } from '@/lib/utils'

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'success' | 'warning' | 'error' | 'info'
}

export function Badge({ className, variant = 'default', children, ...props }: BadgeProps) {
  const variants = {
    default: 'bg-bg-tertiary text-text-secondary',
    success: 'bg-[#16A34A]/10 text-success border-success/20',
    warning: 'bg-[#F59E0B]/10 text-warning border-warning/20',
    error: 'bg-[#DC2626]/10 text-error border-error/20',
    info: 'bg-accent-light text-accent border-accent/20',
  }

  return (
    <span
      className={cn(
        "inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border border-transparent",
        variants[variant],
        className
      )}
      {...props}
    >
      {children}
    </span>
  )
}
