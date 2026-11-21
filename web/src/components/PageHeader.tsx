import type { ReactNode } from 'react'

type PageHeaderProps = {
  marker: string
  title: string
  description: string
  aside?: ReactNode
}

export function PageHeader({ marker, title, description, aside }: PageHeaderProps) {
  return (
    <section className="page-header">
      <div className="page-header-copy">
        <span className="folio">{marker}</span>
        <h2>{title}</h2>
        <p>{description}</p>
      </div>
      {aside ? <div className="page-header-aside">{aside}</div> : null}
    </section>
  )
}
