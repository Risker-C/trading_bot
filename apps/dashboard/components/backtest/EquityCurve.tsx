/**
 * 权益曲线组件 - 使用Lightweight Charts
 */
'use client'

import { useEffect, useRef } from 'react'
import { createChart, IChartApi, ISeriesApi } from 'lightweight-charts'

interface EquityCurveProps {
  data: Array<{ time: number; value: number }>
  initialCapital?: number
}

export default function EquityCurve({ data, initialCapital = 10000 }: EquityCurveProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesRef = useRef<ISeriesApi<'Line'> | null>(null)

  useEffect(() => {
    if (!chartContainerRef.current) return

    // 创建图表
    const chart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height: 400,
      layout: {
        background: { color: '#1a1a1a' },
        textColor: '#d1d4dc',
      },
      grid: {
        vertLines: { color: '#2a2a2a' },
        horzLines: { color: '#2a2a2a' },
      },
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
      },
    })

    // 创建线系列
    const lineSeries = chart.addLineSeries({
      color: '#2962FF',
      lineWidth: 2,
    })

    chartRef.current = chart
    seriesRef.current = lineSeries

    // 响应式调整
    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: chartContainerRef.current.clientWidth,
        })
      }
    }

    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      chart.remove()
    }
  }, [])

  useEffect(() => {
    if (!seriesRef.current || !data.length) return

    // 转换数据格式
    const chartData = data.map((point) => ({
      time: point.time as any,
      value: point.value,
    }))

    seriesRef.current.setData(chartData)
  }, [data])

  return (
    <div className="w-full">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-lg font-semibold">权益曲线</h3>
        <div className="text-sm text-gray-400">
          初始资金: ${initialCapital.toLocaleString()}
        </div>
      </div>
      <div ref={chartContainerRef} className="rounded-lg border border-gray-700" />
    </div>
  )
}
