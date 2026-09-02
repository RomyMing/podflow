'use client'

import React from 'react'
import { cn } from '@/lib/utils'
import { Loader2 } from 'lucide-react'

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger'
  size?: 'sm' | 'md' | 'lg'
  isLoading?: boolean
  leftIcon?: React.ReactNode
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'primary', size = 'md', isLoading = false, leftIcon, children, disabled, ...props }, ref) => {
    
    const baseStyles = 'inline-flex items-center justify-center font-medium transition-colors focus:ring-2 focus:ring-offset-2 focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed'
    
    const variants = {
      primary: 'bg-accent text-white hover:bg-accent-hover focus:ring-accent border border-transparent',
      secondary: 'bg-bg-tertiary text-text-primary hover:bg-border focus:ring-accent border border-transparent',
      outline: 'bg-bg-primary border border-border text-text-primary hover:bg-bg-secondary focus:ring-accent',
      ghost: 'bg-transparent text-text-secondary hover:bg-bg-tertiary hover:text-text-primary focus:ring-accent border border-transparent',
      danger: 'bg-error text-white hover:bg-red-700 focus:ring-red-600 border border-transparent',
    }

    const sizes = {
      sm: 'px-3 py-1.5 text-xs rounded-[var(--radius-sm)]',
      md: 'px-4 py-2 text-sm rounded-[var(--radius-sm)]',
      lg: 'px-6 py-3 text-base rounded-[var(--radius-md)]',
    }

    return (
      <button
        ref={ref}
        className={cn(baseStyles, variants[variant], sizes[size], className)}
        disabled={isLoading || disabled}
        {...props}
      >
        {isLoading ? (
          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
        ) : leftIcon ? (
          <span className="mr-2">{leftIcon}</span>
        ) : null}
        {children}
      </button>
    )
  }
)
Button.displayName = 'Button'
