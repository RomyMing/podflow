import type { Metadata } from 'next'
import { ToastProvider } from '@/components/ui/toast'
import './globals.css'

export const metadata: Metadata = {
  title: '播客翻译 | 英文播客翻译',
  description: '面向内测 MVP 的播客翻译工作台，支持本地音频上传、任务进度跟踪与结果下载。',
  keywords: ['podcast translation', 'podflow', 'audio dubbing', 'ai translation'],
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="zh-CN">
      <body className="font-sans antialiased">
        <ToastProvider>{children}</ToastProvider>
      </body>
    </html>
  )
}
