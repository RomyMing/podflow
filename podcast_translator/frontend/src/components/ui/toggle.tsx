'use client'

interface ToggleProps {
  checked: boolean
  onChange: (checked: boolean) => void
  label?: string
  id?: string
  disabled?: boolean
}

export function Toggle({ checked, onChange, label, id, disabled = false }: ToggleProps) {
  return (
    <label className={`toggle-wrapper${disabled ? ' toggle-wrapper--disabled' : ''}`} htmlFor={id}>
      {label && <span className="toggle-label">{label}</span>}
      <button
        role="switch"
        aria-checked={checked}
        id={id}
        disabled={disabled}
        className={`toggle${checked ? ' toggle--on' : ''}`}
        onClick={() => !disabled && onChange(!checked)}
        type="button"
      >
        <span className="toggle__thumb" />
      </button>
    </label>
  )
}
