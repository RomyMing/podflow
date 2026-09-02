'use client'

import { useState, useCallback } from 'react'
import { Link2 } from 'lucide-react'
import { Button } from '@/components/ui/button'

interface UrlInputProps {
  onSubmit: (url: string) => void
  isLoading: boolean
  disabled?: boolean
}

export function UrlInput({ onSubmit, isLoading, disabled }: UrlInputProps) {
  const [url, setUrl] = useState('')

  const handleSubmit = useCallback((e: React.FormEvent) => {
    e.preventDefault()
    if (url.trim()) {
      onSubmit(url.trim())
    }
  }, [url, onSubmit])

  const isValid = url.trim().length > 0

  return (
    <form className="url-input" onSubmit={handleSubmit} id="url-input-form">
      <div className="url-input__field">
        <Link2 className="url-input__icon" />
        <input
          type="url"
          className="url-input__input"
          placeholder="粘贴播客音频 URL..."
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          disabled={isLoading || disabled}
          aria-label="播客音频 URL"
        />
      </div>
      <Button
        type="submit"
        variant="primary"
        size="lg"
        disabled={!isValid || isLoading || disabled}
        isLoading={isLoading}
        className="url-input__button"
      >
        开始翻译
      </Button>
    </form>
  )
}
