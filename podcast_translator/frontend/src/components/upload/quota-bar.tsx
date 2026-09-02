'use client'

import { useEffect, useState } from 'react'
import { UserService } from '@/services/user-service'
import { QuotaResponse } from '@/types/api'

export function QuotaBar() {
  const [quota, setQuota] = useState<QuotaResponse | null>(null)

  useEffect(() => {
    UserService.getQuota().then(setQuota).catch(() => {})
  }, [])

  if (!quota) {
    return null
  }

  const isLow = quota.remaining <= 1

  return (
    <div className="quota-bar" id="quota-bar">
      {isLow ? (
        <div className="quota-bar__low">
          <span className="quota-bar__text quota-bar__text--warning">
            本月剩余额度较低：{quota.remaining} / {quota.total}
          </span>
        </div>
      ) : (
        <p className="quota-bar__text">本月剩余可用额度：{quota.remaining} / {quota.total}</p>
      )}
    </div>
  )
}
