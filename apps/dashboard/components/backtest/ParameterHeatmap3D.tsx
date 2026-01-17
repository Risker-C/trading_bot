/**
 * 3D参数热力图组件 - 使用React Three Fiber
 */
'use client'

import { useRef, useMemo, useEffect } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { OrbitControls, Text } from '@react-three/drei'
import * as THREE from 'three'

interface HeatmapData {
  x: number[]
  y: number[]
  z: number[]
  param_x: string
  param_y: string
  metric: string
}

interface ParameterHeatmap3DProps {
  data: HeatmapData
  onPointClick?: (params: { x: number; y: number; z: number }) => void
}

function HeatmapSurface({ data, onPointClick }: ParameterHeatmap3DProps) {
  const meshRef = useRef<THREE.Mesh>(null)
  const geometryRef = useRef<THREE.BufferGeometry | null>(null)

  // 创建网格数据
  const { geometry, colors } = useMemo(() => {
    if (!data.x.length) return { geometry: null, colors: null }

    // 找到数据范围
    const xMin = Math.min(...data.x)
    const xMax = Math.max(...data.x)
    const yMin = Math.min(...data.y)
    const yMax = Math.max(...data.y)
    const zMin = Math.min(...data.z)
    const zMax = Math.max(...data.z)

    // 防止除零错误
    const zRange = zMax - zMin || 1

    // 创建网格
    const gridSize = 20
    const vertices: number[] = []
    const colorArray: number[] = []

    for (let i = 0; i < gridSize; i++) {
      for (let j = 0; j < gridSize; j++) {
        const x = xMin + (xMax - xMin) * (i / (gridSize - 1))
        const y = yMin + (yMax - yMin) * (j / (gridSize - 1))

        // 插值计算z值（简单最近邻）
        let z = 0
        let minDist = Infinity

        for (let k = 0; k < data.x.length; k++) {
          const dist = Math.sqrt(
            Math.pow(data.x[k] - x, 2) + Math.pow(data.y[k] - y, 2)
          )
          if (dist < minDist) {
            minDist = dist
            z = data.z[k]
          }
        }

        vertices.push(x, z, y)

        // 颜色映射（蓝色到红色）
        const normalized = (z - zMin) / zRange
        const color = new THREE.Color()
        color.setHSL(0.6 - normalized * 0.6, 1, 0.5)
        colorArray.push(color.r, color.g, color.b)
      }
    }

    const geometry = new THREE.BufferGeometry()
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3))
    geometry.setAttribute('color', new THREE.Float32BufferAttribute(colorArray, 3))

    // 创建索引
    const indices: number[] = []
    for (let i = 0; i < gridSize - 1; i++) {
      for (let j = 0; j < gridSize - 1; j++) {
        const a = i * gridSize + j
        const b = i * gridSize + j + 1
        const c = (i + 1) * gridSize + j
        const d = (i + 1) * gridSize + j + 1

        indices.push(a, b, c)
        indices.push(b, d, c)
      }
    }
    geometry.setIndex(indices)
    geometry.computeVertexNormals()

    return { geometry, colors: colorArray }
  }, [data])

  // 清理旧的几何体以防止内存泄漏
  useEffect(() => {
    // 清理旧的几何体
    if (geometryRef.current) {
      geometryRef.current.dispose()
    }

    // 存储新的几何体
    geometryRef.current = geometry

    // 组件卸载时清理
    return () => {
      if (geometryRef.current) {
        geometryRef.current.dispose()
        geometryRef.current = null
      }
    }
  }, [geometry])

  // 旋转动画
  useFrame(() => {
    if (meshRef.current) {
      meshRef.current.rotation.z += 0.001
    }
  })

  if (!geometry) return null

  return (
    <mesh ref={meshRef} geometry={geometry}>
      <meshStandardMaterial vertexColors side={THREE.DoubleSide} />
    </mesh>
  )
}

export default function ParameterHeatmap3D({ data, onPointClick }: ParameterHeatmap3DProps) {
  return (
    <div className="h-[600px] w-full rounded-lg border border-gray-700 bg-gray-900">
      <div className="mb-2 p-4">
        <h3 className="text-lg font-semibold">3D参数热力图</h3>
        <div className="mt-1 text-sm text-gray-400">
          X轴: {data.param_x} | Y轴: {data.param_y} | Z轴: {data.metric}
        </div>
      </div>

      <Canvas camera={{ position: [5, 5, 5], fov: 50 }}>
        <ambientLight intensity={0.5} />
        <pointLight position={[10, 10, 10]} />
        <HeatmapSurface data={data} onPointClick={onPointClick} />
        <OrbitControls enableDamping dampingFactor={0.05} />
        <gridHelper args={[10, 10]} />
      </Canvas>

      {/* 图例 */}
      <div className="flex items-center justify-center gap-4 p-4">
        <div className="flex items-center gap-2">
          <div className="h-4 w-8 bg-gradient-to-r from-blue-500 to-red-500" />
          <span className="text-xs text-gray-400">低 → 高</span>
        </div>
      </div>
    </div>
  )
}
