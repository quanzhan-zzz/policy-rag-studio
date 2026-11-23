import { FileUp, RefreshCw, RotateCcw, ShieldCheck, X } from 'lucide-react'
import { useRef } from 'react'

import { PageHeader } from '../components/PageHeader'
import { ErrorState, LoadingState } from '../components/StateBlock'
import {
  useCancelIndexTask,
  useDocuments,
  useReindexDocument,
  useRetryIndexTask,
  useUploadDocument,
} from '../lib/queries'
import type { IndexTaskStatus } from '../types'

const statusLabels: Record<IndexTaskStatus, string> = {
  queued: '等待索引',
  parsing: '解析文档',
  chunking: '生成切片',
  embedding: '写入向量',
  ready: '索引完成',
  failed: '索引失败',
  cancelled: '已取消',
}

const activeStatuses = new Set(['queued', 'parsing', 'chunking', 'embedding'])

export function DocumentsPage() {
  const documents = useDocuments()
  const upload = useUploadDocument()
  const reindex = useReindexDocument()
  const retry = useRetryIndexTask()
  const cancel = useCancelIndexTask()
  const inputRef = useRef<HTMLInputElement>(null)

  const handleUpload = (file: File | undefined) => {
    if (file) upload.mutate(file)
  }

  if (documents.isLoading) return <LoadingState label="正在读取文档目录" />
  if (documents.isError) return <ErrorState message={documents.error.message} />

  return (
    <div className="page-stack">
      <PageHeader
        title="文档与索引"
        description="维护政策文件与索引任务。"
        aside={
          <button
            className="button button-primary"
            disabled={upload.isPending}
            onClick={() => inputRef.current?.click()}
            type="button"
          >
            <FileUp size={16} />
            {upload.isPending ? '正在入队' : '上传政策文件'}
          </button>
        }
      />
      <input
        accept=".pdf,.docx,.txt,.md,.markdown"
        className="sr-only"
        onChange={(event) => handleUpload(event.target.files?.[0])}
        ref={inputRef}
        type="file"
      />

      {upload.isError ? <ErrorState message={upload.error.message} /> : null}
      {reindex.isError ? <ErrorState message={reindex.error.message} /> : null}
      {retry.isError ? <ErrorState message={retry.error.message} /> : null}
      {cancel.isError ? <ErrorState message={cancel.error.message} /> : null}

      <section className="registry-grid">
        <article className="panel registry-panel">
          <div className="panel-heading">
            <div>
              <h3>{documents.data!.length} 份政策材料</h3>
            </div>
            <span className="quiet-chip">PDF · DOCX · MD</span>
          </div>

          <div className="data-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>文档 / 部门</th>
                  <th>生效日期</th>
                  <th>Chunk</th>
                  <th>状态</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {documents.data!.map((document) => (
                  <tr key={document.id}>
                    <td>
                      <div className="document-title">
                        <strong>{document.title}</strong>
                        <span>{document.department}</span>
                        <div className="tag-line">
                          {document.tags.map((tag) => (
                            <span className="micro-tag" key={tag}>
                              {tag}
                            </span>
                          ))}
                        </div>
                      </div>
                    </td>
                    <td className="mono-cell">{document.effective_date}</td>
                    <td className="mono-cell">{document.chunk_count}</td>
                    <td>
                      <div className="document-status-cell">
                        <span className={`status-pill is-${document.status}`}>
                          <span />
                          {statusLabels[document.status as IndexTaskStatus] ?? document.status}
                        </span>
                        {activeStatuses.has(document.status) ? (
                          <div className="document-progress">
                            <span style={{ width: `${document.index_progress}%` }} />
                          </div>
                        ) : null}
                        {document.index_error ? (
                          <p className="document-index-error">{document.index_error}</p>
                        ) : null}
                      </div>
                    </td>
                    <td>
                      {activeStatuses.has(document.status) && document.index_task_id ? (
                        <button
                          aria-label={`取消 ${document.title} 索引`}
                          className="icon-button"
                          disabled={cancel.isPending}
                          onClick={() => cancel.mutate(document.index_task_id!)}
                          title="取消索引"
                          type="button"
                        >
                          <X size={15} />
                        </button>
                      ) : document.status === 'failed' && document.index_task_id ? (
                        <button
                          aria-label={`重试 ${document.title} 索引`}
                          className="icon-button"
                          disabled={retry.isPending}
                          onClick={() => retry.mutate(document.index_task_id!)}
                          title="重试索引"
                          type="button"
                        >
                          <RotateCcw
                            className={
                              retry.isPending && retry.variables === document.index_task_id
                                ? 'spin'
                                : ''
                            }
                            size={15}
                          />
                        </button>
                      ) : (
                        <button
                          aria-label={`重建 ${document.title} 索引`}
                          className="icon-button"
                          disabled={reindex.isPending || activeStatuses.has(document.status)}
                          onClick={() => reindex.mutate(document.id)}
                          title="重建索引"
                          type="button"
                        >
                          <RefreshCw
                            className={
                              reindex.isPending && reindex.variables === document.id
                                ? 'spin'
                                : ''
                            }
                            size={15}
                          />
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>

        <aside className="panel ingestion-panel">
          <h3>解析与安全边界</h3>
          <ul className="rule-list">
            <li>
              <p>只使用公开政策、办事指南和合成材料，不提交真实办件数据。</p>
            </li>
            <li>
              <p>上传文件先解析为文本，再按三种 Chunk profile 建立独立索引。</p>
            </li>
            <li>
              <p>Chunk 可人工修订，修订后应重新跑评测，避免用测试集调参。</p>
            </li>
          </ul>
          <div className="safety-note">
            <ShieldCheck size={18} />
            <div>
              <strong>合规优先</strong>
              <p>GitHub 仓库不上传公司代码、数据库或身份证等敏感信息。</p>
            </div>
          </div>
        </aside>
      </section>
    </div>
  )
}
