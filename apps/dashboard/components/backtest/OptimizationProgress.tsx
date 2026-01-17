/**
 * 优化进度可视化组件
 */
'use client'

import { useEffect, useState } from 'react'

interface OptimizationProgress {
  completed: number
  total: number
  progress: number
  currentParams?: Record<string, any>
  currentScore?: number
  bestScore?: number
  bestParams?: Record<string, any>
}

interface OptimizationProgressProps {
  jobId: string
  onComplete?: () => void
}

export default function OptimizationProgress({ jobId, onComplete }: OptimizationProgressProps) {
  const [progress, setProgress] = useState<OptimizationProgress>({
    completed: 0,
    total: 100,
    progress: 0,
  })
  const [status, setStatus] = useState<'running' | 'completed' | 'failed'>('running')

  useEffect(() => {
    // TODO: 实现WebSocket连接获取实时进度
    // const ws = new WebSocket(`ws://localhost:8000/ws/optimization/${jobId}`)

    // 模拟进度更新
    const interval = setInterval(() => {
      setProgress((prev) => {
        const newCompleted = Math.min(prev.completed + 1, prev.total)
        const newProgress = newCompleted / prev.total

        if (newCompleted === prev.total) {
          setStatus('completed')
          onComplete?.()
          clearInterval(interval)
        }

        return {
          ...prev,
          completed: newCompleted,
          progress: newProgress,
        }
      })
    }, 1000)

    return () => clearInterval(interval)
  }, [jobId, onComplete])

  return (
    <div className="rounded-lg border border-gray-700 bg-gray-800 p-6">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-lg font-semibold">优化进度</h3>
        <span
          className={`rounded px-2 py-1 text-sm ${
            status === 'running'
              ? 'bg-blue-500/20 text-blue-400'
              : status === 'completed'
              ? 'bg-green-500/20 text-green-400'
              : 'bg-red-500/20 text-red-400'
          }`}
        >
          {status === 'running' ? '运行中' : status === 'completed' ? '已完成' : '失败'}
        </span>
      </div>

      {/* 进度条 */}
      <div className="mb-4">
        <div className="mb-2 flex justify-between text-sm text-gray-400">
          <span>
            {progress.completed} / {progress.total}
          </span>
          <span>{(progress.progress * 100).toFixed(1)}%</span>
        </div>
        <div className="h-2 w-full overflow-hidden rounded-full bg-gray-700">
          <div
            className="h-full bg-blue-500 transition-all duration-300"
            style={{ width: `${progress.progress * 100}%` }}
          />
        </div>
      </div>

      {/* 当前参数 */}
      {progress.currentParams && (
        <div className="mb-4 rounded bg-gray-900 p-3">
          <div className="mb-1 text-sm font-medium text-gray-400">当前参数</div>
          <div className="text-sm">
            {Object.entries(progress.currentParams).map(([key, value]) => (
              <div key={key} className="flex justify-between">
                <span className="text-gray-400">{key}:</span>
                <span className="font-mono">{value}</span>
              </div>
            ))}
          </div>
          {progress.currentScore !== undefined && (
            <div className="mt-2 text-sm">
              <span className="text-gray-400">得分:</span>{' '}
              <span className="font-mono text-blue-400">{progress.currentScore.toFixed(4)}</span>
            </div>
          )}
        </div>
      )}

      {/* 最佳结果 */}
      {progress.bestParams && (
        <div className="rounded bg-green-500/10 p-3">
          <div className="mb-1 text-sm font-medium text-green-400">最佳参数</div>
          <div className="text-sm">
            {Object.entries(progress.bestParams).map(([key, value]) => (
              <div key={key} className="flex justify-between">
                <span className="text-gray-400">{key}:</span>
                <span className="font-mono">{value}</span>
              </div>
            ))}
          </div>
          {progress.bestScore !== undefined && (
            <div className="mt-2 text-sm">
              <span className="text-gray-400">最佳得分:</span>{' '}
              <span className="font-mono text-green-400">{progress.bestScore.toFixed(4)}</span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
