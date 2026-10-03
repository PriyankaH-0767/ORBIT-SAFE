import React from 'react'
import { Header } from './components/common/Header'
import { PlannerPage } from './pages/PlannerPage'
import { ResultsPage } from './pages/ResultsPage'
import { useAppRoute } from './utils/router'

export const App: React.FC = () => {
  const { route } = useAppRoute()

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      <Header />
      <div className="flex-1">
        {route.name === 'results' ? (
          <ResultsPage runId={route.runId} />
        ) : (
          <PlannerPage />
        )}
      </div>
      <footer className="border-t border-slate-900 bg-slate-950/80 py-4 text-center text-xs text-slate-500 font-mono">
        D-DATO Debris-Aware Orbit &bull; Smart India Hackathon 2026 (Problem Statement 26209)
      </footer>
    </div>
  )
}

export default App
