'use client';

import { useState, useEffect } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import axios from 'axios';

interface AIAnalysisProps {
  sessionId: string;
}

interface AIAnalysis {
  report_id: string | null;
  summary: string;
  strengths: string[];
  weaknesses: string[];
  recommendations: string[];
  param_suggestions: Record<string, string>;
}

export default function AIAnalysisPanel({ sessionId }: AIAnalysisProps) {
  const [analysis, setAnalysis] = useState<AIAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  // Auto-load existing analysis on mount
  useEffect(() => {
    loadExistingAnalysis();
  }, [sessionId]);

  const handleAnalyze = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await axios.post(
        `${apiUrl}/api/backtests/sessions/${sessionId}/ai-analysis`
      );

      // 解析AI分析结果
      const data = response.data;

      // 如果summary是JSON字符串，尝试解析
      if (typeof data.summary === 'string' && data.summary.trim().startsWith('{')) {
        try {
          const parsed = JSON.parse(data.summary);
          setAnalysis({
            report_id: data.report_id,
            summary: parsed.summary || data.summary,
            strengths: parsed.strengths || [],
            weaknesses: parsed.weaknesses || [],
            recommendations: parsed.recommendations || [],
            param_suggestions: parsed.param_suggestions || {}
          });
        } catch (e) {
          // 如果解析失败，使用原始数据
          setAnalysis(data);
        }
      } else {
        setAnalysis(data);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'AI 分析失败');
    } finally {
      setLoading(false);
    }
  };

  const loadExistingAnalysis = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await axios.get(
        `${apiUrl}/api/backtests/sessions/${sessionId}/ai-analysis`
      );

      // 解析AI分析结果
      const data = response.data;

      // 如果summary是JSON字符串，尝试解析
      if (typeof data.summary === 'string' && data.summary.trim().startsWith('{')) {
        try {
          const parsed = JSON.parse(data.summary);
          setAnalysis({
            report_id: data.report_id,
            summary: parsed.summary || data.summary,
            strengths: parsed.strengths || [],
            weaknesses: parsed.weaknesses || [],
            recommendations: parsed.recommendations || [],
            param_suggestions: parsed.param_suggestions || {}
          });
        } catch (e) {
          // 如果解析失败，使用原始数据
          setAnalysis(data);
        }
      } else {
        setAnalysis(data);
      }
    } catch (err: any) {
      if (err.response?.status === 404) {
        setError('暂无 AI 分析报告，请点击"开始分析"生成');
      } else {
        setError(err.response?.data?.detail || err.message || '加载失败');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card className="p-6">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-xl font-semibold">AI 分析</h2>
        <div className="space-x-2">
          <Button onClick={loadExistingAnalysis} variant="outline" disabled={loading}>
            查看历史分析
          </Button>
          <Button onClick={handleAnalyze} disabled={loading}>
            {loading ? '分析中...' : '开始分析'}
          </Button>
        </div>
      </div>

      {loading && (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
        </div>
      )}

      {error && !loading && (
        <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded p-4 text-yellow-800 dark:text-yellow-200">
          {error}
        </div>
      )}

      {analysis && !loading && (
        <div className="space-y-6">
          {/* Summary */}
          <div>
            <h3 className="font-semibold text-lg mb-2">整体评价</h3>
            <p className="text-foreground">{analysis.summary}</p>
          </div>

          {/* Strengths */}
          {analysis.strengths && analysis.strengths.length > 0 && (
            <div>
              <h3 className="font-semibold text-lg mb-2 text-green-600 dark:text-green-400">优势</h3>
              <ul className="list-disc list-inside space-y-1">
                {analysis.strengths.map((strength, index) => (
                  <li key={index} className="text-foreground">{strength}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Weaknesses */}
          {analysis.weaknesses && analysis.weaknesses.length > 0 && (
            <div>
              <h3 className="font-semibold text-lg mb-2 text-red-600 dark:text-red-400">劣势</h3>
              <ul className="list-disc list-inside space-y-1">
                {analysis.weaknesses.map((weakness, index) => (
                  <li key={index} className="text-foreground">{weakness}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Recommendations */}
          {analysis.recommendations && analysis.recommendations.length > 0 && (
            <div>
              <h3 className="font-semibold text-lg mb-2 text-blue-600 dark:text-blue-400">优化建议</h3>
              <ul className="list-disc list-inside space-y-1">
                {analysis.recommendations.map((rec, index) => (
                  <li key={index} className="text-foreground">{rec}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Parameter Suggestions */}
          {analysis.param_suggestions && Object.keys(analysis.param_suggestions).length > 0 && (
            <div>
              <h3 className="font-semibold text-lg mb-2">参数建议</h3>
              <div className="bg-muted/50 rounded p-4">
                <table className="w-full">
                  <tbody>
                    {Object.entries(analysis.param_suggestions).map(([key, value]) => (
                      <tr key={key} className="border-b border-border last:border-b-0">
                        <td className="py-2 font-medium text-foreground">{key}</td>
                        <td className="py-2 text-muted-foreground">{value}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
