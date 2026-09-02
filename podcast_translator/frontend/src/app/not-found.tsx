import Link from 'next/link'
import './not-found.css'

export default function NotFound() {
  return (
    <div className="not-found-page">
      <p className="not-found__number" aria-hidden="true">404</p>
      <h1 className="not-found__title">页面未找到</h1>
      <p className="not-found__desc">
        你访问的页面不存在或已被移除，请检查链接是否正确。
      </p>
      <Link href="/" className="not-found__cta" id="not-found-home-btn">
        🏠 返回首页
      </Link>
    </div>
  )
}
