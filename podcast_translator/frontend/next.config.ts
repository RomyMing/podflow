import type { NextConfig } from 'next'

const proxyTarget = process.env.PCT_FRONTEND_PROXY_TARGET || 'http://127.0.0.1:8000'

const nextConfig: NextConfig = {
  experimental: {
    // Large multipart uploads hit Next's 10MB proxy buffer before they reach
    // the backend when we use same-origin /api rewrites in local dev.
    middlewareClientMaxBodySize: '256mb',
  },
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${proxyTarget}/api/:path*`,
      },
    ]
  },
}

export default nextConfig
