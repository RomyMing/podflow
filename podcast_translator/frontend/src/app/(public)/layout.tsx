import { DemoBanner } from '@/components/common/demo-banner'

export default function PublicLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="public-shell">
      <DemoBanner />
      <div className="public-shell__content">{children}</div>
    </div>
  )
}
