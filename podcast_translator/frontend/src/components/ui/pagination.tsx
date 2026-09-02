'use client'

interface PaginationProps {
  page: number
  totalPages: number
  onPrev: () => void
  onNext: () => void
  className?: string
}

export function Pagination({
  page,
  totalPages,
  onPrev,
  onNext,
  className = '',
}: PaginationProps) {
  return (
    <div className={`pagination ${className}`} role="navigation" aria-label="分页">
      <button
        className="pagination__btn"
        onClick={onPrev}
        disabled={page <= 1}
        id="pagination-prev"
        aria-label="上一页"
      >
        ← 上一页
      </button>

      <span className="pagination__info">
        第 <strong>{page}</strong> / {totalPages} 页
      </span>

      <button
        className="pagination__btn"
        onClick={onNext}
        disabled={page >= totalPages}
        id="pagination-next"
        aria-label="下一页"
      >
        下一页 →
      </button>
    </div>
  )
}
