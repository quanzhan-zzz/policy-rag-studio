import { lazy, Suspense } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'

import { AppShell } from './components/AppShell'
import { LoadingState } from './components/StateBlock'

const OverviewPage = lazy(() =>
  import('./pages/OverviewPage').then((module) => ({ default: module.OverviewPage })),
)
const DocumentsPage = lazy(() =>
  import('./pages/DocumentsPage').then((module) => ({ default: module.DocumentsPage })),
)
const ChunkLabPage = lazy(() =>
  import('./pages/ChunkLabPage').then((module) => ({ default: module.ChunkLabPage })),
)
const RetrievalPage = lazy(() =>
  import('./pages/RetrievalPage').then((module) => ({ default: module.RetrievalPage })),
)
const EvaluationPage = lazy(() =>
  import('./pages/EvaluationPage').then((module) => ({ default: module.EvaluationPage })),
)
const TracePage = lazy(() =>
  import('./pages/TracePage').then((module) => ({ default: module.TracePage })),
)

export default function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<LoadingState label="正在加载研究工作台" />}>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<OverviewPage />} />
            <Route element={<DocumentsPage />} path="documents" />
            <Route element={<ChunkLabPage />} path="chunk-lab" />
            <Route element={<RetrievalPage />} path="retrieval" />
            <Route element={<EvaluationPage />} path="evaluation" />
            <Route element={<TracePage />} path="trace" />
            <Route element={<TracePage />} path="traces/:traceId" />
          </Route>
        </Routes>
      </Suspense>
    </BrowserRouter>
  )
}
