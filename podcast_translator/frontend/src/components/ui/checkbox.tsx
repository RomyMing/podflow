'use client'

import React from 'react'
import { cn } from '@/lib/utils'

interface CheckboxProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string | React.ReactNode
}

export const Checkbox = React.forwardRef<HTMLInputElement, CheckboxProps>(
  ({ className, label, id, ...props }, ref) => {
    const defaultId = React.useId()
    const inputId = id || defaultId
    
    return (
      <div className="flex items-start gap-2">
        <div className="flex items-center h-5 mt-0.5">
          <input
            id={inputId}
            type="checkbox"
            ref={ref}
            className={cn(
              "w-4 h-4 rounded border-border text-accent focus:ring-accent transition-colors cursor-pointer",
              className
            )}
            {...props}
          />
        </div>
        {label && (
          <label htmlFor={inputId} className="text-sm text-text-secondary cursor-pointer select-none leading-relaxed">
            {label}
          </label>
        )}
      </div>
    )
  }
)
Checkbox.displayName = 'Checkbox'
