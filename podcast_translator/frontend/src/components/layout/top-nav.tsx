'use client'

import { AvatarDropdown } from './avatar-dropdown'

export function TopNav() {
  return (
    <header className="app-topnav">
      {/* 通知按钮 */}
      <button className="topnav-btn" aria-label="通知" id="topnav-bell-btn">
        <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
          <path d="M10 2a6 6 0 00-6 6v3.586l-.707.707A1 1 0 004 14h12a1 1 0 00.707-1.707L16 11.586V8a6 6 0 00-6-6zM10 18a3 3 0 01-3-3h6a3 3 0 01-3 3z" />
        </svg>
      </button>

      <div className="topnav-divider" />

      <AvatarDropdown />
    </header>
  )
}
