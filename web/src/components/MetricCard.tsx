import type { ReactNode } from 'react'

type MetricCardProps = {
  label: string
  value: string | number
  detail: string
  icon?: ReactNode
  tone?: 'default' | 'blue' | 'green' | 'amber'
}

export function MetricCard({
  label,
  value,
  detail,
  icon,
  tone = 'default',
}: MetricCardProps) {
  return (
    <article className={`metric-card tone-${tone}`}>
      <div className="metric-topline">
        <span>{label}</span>
        {icon}
      </div>
      <strong>{value}</strong>
      <p>{detail}</p>
    </article>
  )
}
