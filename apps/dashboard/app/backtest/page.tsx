'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function BacktestPage() {
  const router = useRouter();

  useEffect(() => {
    // 重定向到新建回测页面
    router.replace('/backtest/new');
  }, [router]);

  return (
    <div className="flex items-center justify-center h-full">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto"></div>
        <p className="mt-4 text-gray-600">正在跳转...</p>
      </div>
    </div>
  );
}
