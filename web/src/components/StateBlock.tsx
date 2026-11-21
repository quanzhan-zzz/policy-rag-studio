import { AlertTriangle, LoaderCircle } from 'lucide-react'

export function LoadingState({ label = '正在读取检索数据' }: { label?: string }) {
  return (
    <div className="state-block">
      <LoaderCircle className="spin" size={18} />
      <span>{label}</span>
    </div>
  )
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div className="state-block is-error">
      <AlertTriangle size={18} />
      <span>{message}</span>
    </div>
  )
}
