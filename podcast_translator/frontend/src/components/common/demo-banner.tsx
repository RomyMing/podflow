'use client'

import Link from 'next/link'
import { allowUserUpload, enableSampleTasks, showDemoBanner } from '@/config/app-config'
import { SAMPLE_TASK_ID } from '@/lib/demo-sample-task'

export function DemoBanner() {
  if (!showDemoBanner) {
    return null
  }

  const message = allowUserUpload
    ? '当前为作品集展示环境，可直接上传音频体验完整流程，也可以先查看示例任务。'
    : '当前为作品集展示环境，已切换为示例浏览模式。'

  return (
    <div className="demo-banner" role="note" aria-label="展示环境提示">
      <div className="demo-banner__content">
        <span className="demo-banner__tag">Demo</span>
        <p className="demo-banner__text">{message}</p>
        {enableSampleTasks && (
          <Link href={`/tasks/${SAMPLE_TASK_ID}`} className="demo-banner__link">
            查看示例任务
          </Link>
        )}
      </div>
    </div>
  )
}
