'use client'

import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { Headphones } from 'lucide-react'
import { FilterTabs } from '@/components/ui/filter-tabs'
import { Pagination } from '@/components/ui/pagination'
import { TaskCard } from '@/components/task/task-card'
import { useTaskStore } from '@/stores/task-store'
import { TaskStatus } from '@/types/api'
import './tasks.css'

const PAGE_SIZE = 10

type FilterKey = 'all' | TaskStatus
type SortKey = 'newest' | 'oldest'

const FILTER_TABS = [
  { key: 'all' as FilterKey, label: '全部' },
  { key: 'processing' as FilterKey, label: '处理中' },
  { key: 'paused' as FilterKey, label: '已暂停' },
  { key: 'completed' as FilterKey, label: '已完成' },
  { key: 'failed' as FilterKey, label: '失败' },
]

export default function TasksPage() {
  const { tasks, isLoading: loading, fetchTasks } = useTaskStore()
  const [filterKey, setFilterKey] = useState<FilterKey>('all')
  const [sortKey, setSortKey] = useState<SortKey>('newest')
  const [page, setPage] = useState(1)

  useEffect(() => {
    void fetchTasks(0, 100)
  }, [fetchTasks])

  const filtered = useMemo(() => {
    let list = filterKey === 'all' ? tasks : tasks.filter((task) => task.status === filterKey)
    list = [...list].sort((a, b) => {
      const aTime = new Date(a.created_at).getTime()
      const bTime = new Date(b.created_at).getTime()
      return sortKey === 'newest' ? bTime - aTime : aTime - bTime
    })
    return list
  }, [filterKey, sortKey, tasks])

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const paged = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  function handleFilterChange(key: FilterKey) {
    setFilterKey(key)
    setPage(1)
  }

  const tabsWithCount = FILTER_TABS.map((tab) => ({
    ...tab,
    count: tab.key === 'all' ? tasks.length : tasks.filter((task) => task.status === tab.key).length,
  }))

  return (
    <main className="tasks-page">
      <div className="tasks-header">
        <div className="tasks-header__left">
          <h1 className="tasks-title">任务历史</h1>
          {!loading && <p className="tasks-count">共 {filtered.length} 条记录</p>}
        </div>

        <div className="tasks-header__right">
          <select
            className="tasks-sort-select"
            value={sortKey}
            onChange={(event) => {
              setSortKey(event.target.value as SortKey)
              setPage(1)
            }}
            aria-label="排序方式"
            id="tasks-sort-select"
          >
            <option value="newest">最新优先</option>
            <option value="oldest">最早优先</option>
          </select>
        </div>
      </div>

      <FilterTabs
        tabs={tabsWithCount}
        activeKey={filterKey}
        onChange={handleFilterChange}
      />

      {loading ? (
        <div className="tasks-skeleton">
          {Array.from({ length: 5 }).map((_, index) => (
            <div key={index} className="tasks-skeleton-item" />
          ))}
        </div>
      ) : paged.length === 0 ? (
        <div className="tasks-empty">
          <div className="tasks-empty__icon" aria-hidden="true">
            <div className="tasks-empty__icon-shell">
              <Headphones className="tasks-empty__icon-svg" />
            </div>
          </div>
          <p className="tasks-empty__title">
            {filterKey === 'all' ? '暂无任务记录' : `暂无${FILTER_TABS.find((tab) => tab.key === filterKey)?.label}任务`}
          </p>
          <p className="tasks-empty__desc">
            {filterKey === 'all'
              ? '上传你的第一段音频，开始体验完整的播客翻译流程。'
              : '可以切换筛选条件，或者回到首页继续上传。'}
          </p>
          <Link href="/" className="tasks-empty__cta" id="tasks-empty-upload-cta">
            去上传
          </Link>
        </div>
      ) : (
        <>
          <div className="tasks-list">
            {paged.map((task) => (
              <TaskCard key={task.id} task={task} variant="detailed" />
            ))}
          </div>

          {totalPages > 1 && (
            <Pagination
              page={page}
              totalPages={totalPages}
              onPrev={() => setPage((current) => current - 1)}
              onNext={() => setPage((current) => current + 1)}
            />
          )}
        </>
      )}
    </main>
  )
}
