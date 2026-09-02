import { AuthGuard } from '@/components/auth/auth-guard'
import { DemoBanner } from '@/components/common/demo-banner'
import { Sidebar } from '@/components/layout/sidebar'
import { TopNav } from '@/components/layout/top-nav'
import { TaskActivitySync } from '@/components/task/task-activity-sync'
import './layout.css'

export default function ProtectedLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <AuthGuard>
      <TaskActivitySync />
      <div className="app-frame">
        <DemoBanner />
        <div className="app-shell">
          <Sidebar />

          <div className="app-main">
            <TopNav />

            <main className="app-content">
              <div className="app-content-inner">
                {children}
              </div>
            </main>
          </div>
        </div>
      </div>
    </AuthGuard>
  )
}
