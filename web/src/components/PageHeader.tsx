import type { ReactNode } from 'react'

type PageHeaderProps = {
  title: string
  description: string
  aside?: ReactNode
}

export function PageHeader({ title, description, aside }: PageHeaderProps) {
  return (
    <section className="page-header">
      <div className="page-header-copy">
        <h2>{title}</h2>
        <p>{description}</p>
      </div>
      {aside ? <div className="page-header-aside">{aside}</div> : null}
    </section>
  )
}
