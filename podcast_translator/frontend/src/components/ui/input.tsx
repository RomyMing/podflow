'use client'

import React from 'react'
import { cn } from '@/lib/utils'

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
  helpText?: string
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, label, error, helpText, id, ...props }, ref) => {
    const defaultId = React.useId()
    const inputId = id || defaultId
    
    return (
      <div className="w-full flex flex-col gap-1.5">
        {label && (
          <label htmlFor={inputId} className="block text-sm font-medium text-text-primary">
            {label}
          </label>
        )}
        
        <input
          id={inputId}
          ref={ref}
          className={cn(
            "w-full px-3 py-2 bg-bg-primary border rounded-[var(--radius-sm)] text-sm transition-colors",
            "focus:outline-none focus:ring-2 focus:ring-offset-1 placeholder:text-text-tertiary",
            error 
              ? "border-error focus:border-error focus:ring-error text-error" 
              : "border-border focus:border-accent focus:ring-accent-light text-text-primary hover:border-gray-300",
            props.disabled && "bg-bg-tertiary opacity-50 cursor-not-allowed",
            className
          )}
          {...props}
        />
        
        {error && <p className="text-sm text-error mt-1">{error}</p>}
        {helpText && !error && <p className="text-xs text-text-secondary mt-1">{helpText}</p>}
      </div>
    )
  }
)
Input.displayName = 'Input'
