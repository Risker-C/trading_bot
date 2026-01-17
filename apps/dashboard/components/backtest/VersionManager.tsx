/**
 * 版本管理组件 - Git-like实验版本管理
 */
'use client'

import { useState } from 'react'

interface ExperimentVersion {
  id: string
  name: string
  params: Record<string, any>
  metrics: {
    total_return: number
    sharpe: number
    max_drawdown: number
  }
  created_at: number
  parent_id?: string
}

interface VersionManagerProps {
  experiments: ExperimentVersion[]
  currentId: string
  onCheckout: (id: string) => void
  onBranch: (id: string, name: string) => void
}

export default function VersionManager({
  experiments,
  currentId,
  onCheckout,
  onBranch,
}: VersionManagerProps) {
  const [showBranchDialog, setShowBranchDialog] = useState(false)
  const [branchName, setBranchName] = useState('')
  const [selectedId, setSelectedId] = useState<string>('')

  const handleBranch = () => {
    if (branchName && selectedId) {
      onBranch(selectedId, branchName)
      setShowBranchDialog(false)
      setBranchName('')
    }
  }

  return (
    <div className="rounded-lg border border-gray-700 bg-gray-800 p-4">
      <h3 className="mb-4 text-lg font-semibold">实验版本</h3>

      {/* 版本树 */}
      <div className="space-y-2">
        {experiments.map((exp) => (
          <div
            key={exp.id}
            className={`rounded border p-3 transition-colors ${
              exp.id === currentId
                ? 'border-blue-500 bg-blue-500/10'
                : 'border-gray-700 bg-gray-900 hover:border-gray-600'
            }`}
          >
            <div className="mb-2 flex items-center justify-between">
              <div className="flex items-center gap-2">
                {exp.parent_id && (
                  <span className="text-gray-500">└─</span>
                )}
                <span className="font-medium">{exp.name}</span>
                {exp.id === currentId && (
                  <span className="rounded bg-blue-500 px-2 py-0.5 text-xs">当前</span>
                )}
              </div>

              <div className="flex gap-2">
                {exp.id !== currentId && (
                  <button
                    onClick={() => onCheckout(exp.id)}
                    className="rounded bg-gray-700 px-3 py-1 text-sm hover:bg-gray-600"
                  >
                    切换
                  </button>
                )}
                <button
                  onClick={() => {
                    setSelectedId(exp.id)
                    setShowBranchDialog(true)
                  }}
                  className="rounded bg-gray-700 px-3 py-1 text-sm hover:bg-gray-600"
                >
                  分叉
                </button>
              </div>
            </div>

            {/* 指标 */}
            <div className="grid grid-cols-3 gap-2 text-sm">
              <div>
                <span className="text-gray-400">收益:</span>{' '}
                <span className={exp.metrics.total_return > 0 ? 'text-green-400' : 'text-red-400'}>
                  {exp.metrics.total_return.toFixed(2)}%
                </span>
              </div>
              <div>
                <span className="text-gray-400">夏普:</span>{' '}
                <span>{exp.metrics.sharpe.toFixed(2)}</span>
              </div>
              <div>
                <span className="text-gray-400">回撤:</span>{' '}
                <span>{(exp.metrics.max_drawdown * 100).toFixed(2)}%</span>
              </div>
            </div>

            {/* 参数预览 */}
            <div className="mt-2 text-xs text-gray-500">
              {Object.entries(exp.params).slice(0, 3).map(([key, value]) => (
                <span key={key} className="mr-2">
                  {key}={String(value)}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* 分叉对话框 */}
      {showBranchDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-96 rounded-lg border border-gray-700 bg-gray-800 p-6">
            <h4 className="mb-4 text-lg font-semibold">创建分叉</h4>

            <input
              type="text"
              value={branchName}
              onChange={(e) => setBranchName(e.target.value)}
              placeholder="输入实验名称"
              className="mb-4 w-full rounded border border-gray-700 bg-gray-900 px-3 py-2"
            />

            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowBranchDialog(false)}
                className="rounded bg-gray-700 px-4 py-2 hover:bg-gray-600"
              >
                取消
              </button>
              <button
                onClick={handleBranch}
                className="rounded bg-blue-500 px-4 py-2 hover:bg-blue-600"
              >
                创建
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
