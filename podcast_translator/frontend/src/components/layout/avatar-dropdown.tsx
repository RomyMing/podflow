'use client'

import { useState, useRef, useEffect } from 'react'
import Link from 'next/link'
import Image from 'next/image'
import { useAuthStore } from '@/stores/auth-store'

export function AvatarDropdown() {
  const { user, logout } = useAuthStore()
  const [isOpen, setIsOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  // 点击外部关闭
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  if (!user) return null

  const displayName = user.nickname || user.phone || 'User'
  const initial = displayName.charAt(0).toUpperCase()

  return (
    <div style={{ position: 'relative' }} ref={dropdownRef}>
      {/* 触发按钮 */}
      <button
        className="avatar-trigger"
        onClick={() => setIsOpen(!isOpen)}
        aria-haspopup="true"
        aria-expanded={isOpen}
        id="avatar-btn"
      >
        <div className="avatar-circle">
          {user.avatar_url ? (
            <Image
              src={user.avatar_url}
              alt={displayName}
              width={32}
              height={32}
              style={{ borderRadius: '50%', objectFit: 'cover' }}
              unoptimized
            />
          ) : (
            initial
          )}
        </div>
        <span className="avatar-name">{displayName}</span>
        {/* 小箭头 */}
        <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor" style={{ color: '#9CA3AF', flexShrink: 0 }}>
          <path d="M2.5 4.5l3.5 3.5 3.5-3.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" fill="none" />
        </svg>
      </button>

      {/* 下拉菜单 */}
      {isOpen && (
        <div className="avatar-dropdown" role="menu">
          {/* 用户信息 */}
          <div style={{ padding: '10px 14px 8px', borderBottom: '1px solid #E5E7EB' }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: '#1A1A1A', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {displayName}
            </div>
            {user.phone && (
              <div style={{ fontSize: 12, color: '#9CA3AF', marginTop: 2 }}>
                {user.phone.replace(/(\d{3})\d{4}(\d{4})/, '$1****$2')}
              </div>
            )}
          </div>

          <div style={{ padding: '4px 0' }}>
            <Link
              href="/profile"
              className="avatar-dropdown-item"
              onClick={() => setIsOpen(false)}
              role="menuitem"
            >
              {/* Person icon */}
              <svg className="avatar-dropdown-icon" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M10 9a3 3 0 100-6 3 3 0 000 6zm-7 9a7 7 0 1114 0H3z" clipRule="evenodd" />
              </svg>
              个人中心
            </Link>
          </div>

          <div className="avatar-dropdown-separator" />

          <div style={{ padding: '4px 0' }}>
            <button
              className="avatar-dropdown-item avatar-dropdown-item--danger"
              onClick={() => {
                setIsOpen(false)
                logout()
              }}
              role="menuitem"
            >
              {/* Logout icon */}
              <svg className="avatar-dropdown-icon" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M3 3a1 1 0 00-1 1v12a1 1 0 102 0V4a1 1 0 00-1-1zm10.293 9.293a1 1 0 001.414 1.414l3-3a1 1 0 000-1.414l-3-3a1 1 0 10-1.414 1.414L14.586 9H7a1 1 0 100 2h7.586l-1.293 1.293z" clipRule="evenodd" />
              </svg>
              退出登录
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
