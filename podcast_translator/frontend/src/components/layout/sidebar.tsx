'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useAuthStore } from '@/stores/auth-store'

const navItems = [
  {
    label: '首页',
    href: '/',
    icon: (
      <svg className="sidebar-nav-icon" viewBox="0 0 20 20" fill="currentColor">
        <path d="M10.707 2.293a1 1 0 00-1.414 0l-7 7a1 1 0 001.414 1.414L4 10.414V17a1 1 0 001 1h2a1 1 0 001-1v-2a1 1 0 011-1h2a1 1 0 011 1v2a1 1 0 001 1h2a1 1 0 001-1v-6.586l.293.293a1 1 0 001.414-1.414l-7-7z" />
      </svg>
    ),
  },
  {
    label: '任务历史',
    href: '/tasks',
    icon: (
      <svg className="sidebar-nav-icon" viewBox="0 0 20 20" fill="currentColor">
        <path fillRule="evenodd" d="M3 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1z" clipRule="evenodd" />
      </svg>
    ),
  },
  {
    label: '个人中心',
    href: '/profile',
    icon: (
      <svg className="sidebar-nav-icon" viewBox="0 0 20 20" fill="currentColor">
        <path fillRule="evenodd" d="M11.49 3.17c-.38-1.56-2.6-1.56-2.98 0a1.532 1.532 0 01-2.286.948c-1.372-.836-2.942.734-2.106 2.106.54.886.061 2.042-.947 2.287-1.561.379-1.561 2.6 0 2.978a1.532 1.532 0 01.947 2.287c-.836 1.372.734 2.942 2.106 2.106a1.532 1.532 0 012.287.947c.379 1.561 2.6 1.561 2.978 0a1.533 1.533 0 012.287-.947c1.372.836 2.942-.734 2.106-2.106a1.533 1.533 0 01.947-2.287c1.561-.379 1.561-2.6 0-2.978a1.532 1.532 0 01-.947-2.287c.836-1.372-.734-2.942-2.106-2.106a1.532 1.532 0 01-2.287-.947zM10 13a3 3 0 100-6 3 3 0 000 6z" clipRule="evenodd" />
      </svg>
    ),
  },
]

export function Sidebar() {
  const pathname = usePathname()
  const { user } = useAuthStore()
  const used = user?.monthly_used ?? 0
  const quota = user?.monthly_quota ?? 5
  const pct = quota > 0 ? Math.min((used / quota) * 100, 100) : 0
  const isWarning = pct >= 80

  return (
    <aside className="app-sidebar">
      <Link href="/" className="sidebar-logo" aria-label="播客翻译">
        <span>播客翻译</span>
      </Link>

      <nav className="sidebar-nav" aria-label="主导航">
        {navItems.map((item) => {
          const isActive = item.href === '/' ? pathname === '/' : pathname.startsWith(item.href)

          return (
            <Link
              key={item.href}
              href={item.href}
              className={`sidebar-nav-item${isActive ? ' sidebar-nav-item--active' : ''}`}
              aria-current={isActive ? 'page' : undefined}
            >
              {item.icon}
              {item.label}
            </Link>
          )
        })}
      </nav>

      <div className="sidebar-footer">
        <div className="sidebar-quota-label">
          <span>本月剩余额度</span>
          <span className="sidebar-quota-value">{Math.max(quota - used, 0)} / {quota}</span>
        </div>
        <div className="sidebar-quota-track">
          <div
            className={`sidebar-quota-fill${isWarning ? ' sidebar-quota-fill--warning' : ''}`}
            style={{ width: `${pct}%` }}
          />
        </div>
        <p className="sidebar-upgrade-link">内测阶段仅开放基础额度和核心主链路能力。</p>
      </div>
    </aside>
  )
}
