import { Braces, Check, FileText, RefreshCw, Save } from 'lucide-react'
import { useMemo, useState } from 'react'

import { PageHeader } from '../components/PageHeader'
import { ErrorState, LoadingState } from '../components/StateBlock'
import { useChunks, useDocuments, useUpdateChunk } from '../lib/queries'
import type { ChunkStrategy } from '../types'

const strategies: { value: ChunkStrategy; label: string; note: string }[] = [
  { value: 'heading', label: '标题层级', note: '保留条款边界' },
  { value: 'recursive', label: '递归切片', note: '段落优先' },
  { value: 'fixed', label: '固定长度', note: '实验中立基线' },
]

export function ChunkLabPage() {
  const documents = useDocuments()
  const [documentId, setDocumentId] = useState('')
  const [strategy, setStrategy] = useState<ChunkStrategy>('heading')
  const [selectedChunkId, setSelectedChunkId] = useState('')
  const [draftState, setDraftState] = useState<{ chunkId: string; text: string } | null>(null)
  const updateChunk = useUpdateChunk()

  const activeDocumentId = documentId || documents.data?.[0]?.id || ''
  const activeChunks = useChunks(activeDocumentId, strategy)
  const selectedChunk = useMemo(
    () => activeChunks.data?.find((chunk) => chunk.id === selectedChunkId) ?? activeChunks.data?.[0],
    [activeChunks.data, selectedChunkId],
  )
  const draft =
    draftState && draftState.chunkId === selectedChunk?.id
      ? draftState.text
      : selectedChunk?.text ?? ''

  if (documents.isLoading) return <LoadingState label="正在打开 Chunk Laboratory" />
  if (documents.isError) return <ErrorState message={documents.error.message} />

  const currentDocument = documents.data!.find((document) => document.id === activeDocumentId)
  const dirty = Boolean(selectedChunk && draft !== selectedChunk.text)
  const averageTokens = activeChunks.data?.length
    ? Math.round(activeChunks.data.reduce((sum, chunk) => sum + chunk.tokens, 0) / activeChunks.data.length)
    : 0

  return (
    <div className="page-stack chunk-page">
      <PageHeader
        marker="FIELD NOTE / 03"
        title="切片不是预处理，是检索设计"
        description="在原文、Chunk 边界和元数据之间反复校准。当前工作区允许直接修订 Chunk，之后应重新索引并跑同一批评测问题。"
        aside={
          <div className="lab-stats">
            <div>
              <span>CHUNKS</span>
              <strong>{activeChunks.data?.length ?? 0}</strong>
            </div>
            <div>
              <span>AVG TOKENS</span>
              <strong>{averageTokens}</strong>
            </div>
          </div>
        }
      />

      <div className="strategy-switch" role="tablist" aria-label="Chunk 策略">
        {strategies.map((item) => (
          <button
            aria-selected={strategy === item.value}
            className={strategy === item.value ? 'is-active' : ''}
            key={item.value}
            onClick={() => {
              setStrategy(item.value)
              setSelectedChunkId('')
              setDraftState(null)
            }}
            role="tab"
            type="button"
          >
            <span>{item.label}</span>
            <small>{item.note}</small>
          </button>
        ))}
      </div>

      <section className="chunk-workbench">
        <aside className="panel chunk-document-rail">
          <span className="panel-index">A / SOURCE DOCUMENTS</span>
          <div className="document-picker">
            {documents.data!.map((document) => (
              <button
                className={document.id === activeDocumentId ? 'is-selected' : ''}
                key={document.id}
                onClick={() => {
                  setDocumentId(document.id)
                  setSelectedChunkId('')
                  setDraftState(null)
                }}
                type="button"
              >
                <FileText size={15} />
                <span>
                  <strong>{document.title}</strong>
                  <small>{document.department}</small>
                </span>
              </button>
            ))}
          </div>
          <div className="chunk-source-meta">
            <span>ACTIVE FILE</span>
            <strong>{currentDocument?.file_name}</strong>
            <small>{currentDocument?.effective_date} · {currentDocument?.status}</small>
          </div>
        </aside>

        <section className="panel chunk-list-panel">
          <div className="panel-heading compact">
            <div>
              <span className="panel-index">B / CHUNK MAP</span>
              <h3>{activeChunks.data?.length ?? 0} 个检索单元</h3>
            </div>
            <Braces size={17} />
          </div>
          {activeChunks.isLoading ? <LoadingState label="正在生成 Chunk" /> : null}
          {activeChunks.isError ? <ErrorState message={activeChunks.error.message} /> : null}
          <div className="chunk-list">
            {activeChunks.data?.map((chunk, index) => (
              <button
                className={chunk.id === selectedChunk?.id ? 'is-selected' : ''}
                key={chunk.id}
                onClick={() => {
                  setSelectedChunkId(chunk.id)
                  setDraftState({ chunkId: chunk.id, text: chunk.text })
                }}
                type="button"
              >
                <span className="chunk-order">{String(index + 1).padStart(2, '0')}</span>
                <span className="chunk-copy">
                  <strong>{chunk.heading_path}</strong>
                  <p>{chunk.text.replace(/\s+/g, ' ').slice(0, 90)}</p>
                </span>
                <span className="chunk-token">{chunk.tokens}t</span>
              </button>
            ))}
          </div>
        </section>

        <section className="panel chunk-editor-panel">
          <div className="panel-heading compact">
            <div>
              <span className="panel-index">C / BOUNDARY EDITOR</span>
              <h3>{selectedChunk?.heading_path ?? '选择一个 Chunk'}</h3>
            </div>
            {selectedChunk ? (
              <span className="quiet-chip">P.{selectedChunk.page} / {selectedChunk.tokens} tokens</span>
            ) : null}
          </div>
          {selectedChunk ? (
            <>
              <div className="editor-meta">
                <span>{selectedChunk.id}</span>
                <span>{strategy}</span>
              </div>
              <textarea
                aria-label="Chunk 内容编辑器"
                className="chunk-editor"
                onChange={(event) =>
                  setDraftState({ chunkId: selectedChunk.id, text: event.target.value })
                }
                spellCheck={false}
                value={draft}
              />
              <div className="editor-footer">
                <span className={dirty ? 'dirty-indicator is-dirty' : 'dirty-indicator'}>
                  {dirty ? 'UNSAVED CHANGES' : 'SAVED / IN SYNC'}
                </span>
                <div className="editor-actions">
                  <button
                    className="button button-ghost"
                    disabled={!dirty}
                    onClick={() => setDraftState({ chunkId: selectedChunk.id, text: selectedChunk.text })}
                    type="button"
                  >
                    <RefreshCw size={14} />
                    还原
                  </button>
                  <button
                    className="button button-primary"
                    disabled={!dirty || updateChunk.isPending}
                    onClick={() =>
                      updateChunk.mutate(
                        { chunkId: selectedChunk.id, text: draft },
                        { onSuccess: (updatedChunk) =>
                          setDraftState({ chunkId: updatedChunk.id, text: updatedChunk.text })
                        },
                      )
                    }
                    type="button"
                  >
                    {updateChunk.isSuccess && !dirty ? <Check size={14} /> : <Save size={14} />}
                    保存 Chunk
                  </button>
                </div>
              </div>
              {updateChunk.isError ? <ErrorState message={updateChunk.error.message} /> : null}
            </>
          ) : (
            <div className="editor-empty">
              <p>从中间列表选择一个 Chunk，查看切片边界并编辑。</p>
            </div>
          )}
        </section>
      </section>
    </div>
  )
}
