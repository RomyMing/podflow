'use client'

export interface FilterTab<T extends string = string> {
  key: T
  label: string
  count?: number
}

interface FilterTabsProps<T extends string = string> {
  tabs: FilterTab<T>[]
  activeKey: T
  onChange: (key: T) => void
  className?: string
}

export function FilterTabs<T extends string = string>({
  tabs,
  activeKey,
  onChange,
  className = '',
}: FilterTabsProps<T>) {
  return (
    <div className={`filter-tabs ${className}`} role="tablist" aria-label="筛选">
      {tabs.map((tab) => (
        <button
          key={tab.key}
          role="tab"
          aria-selected={activeKey === tab.key}
          className={`filter-tab${activeKey === tab.key ? ' filter-tab--active' : ''}`}
          onClick={() => onChange(tab.key)}
          id={`filter-tab-${tab.key}`}
        >
          {tab.label}
          {tab.count !== undefined && (
            <span className="filter-tab__count">{tab.count}</span>
          )}
        </button>
      ))}
    </div>
  )
}
