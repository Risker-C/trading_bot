'use client';

export function FullPageLoader() {
  return (
    <div className="fixed inset-0 flex items-center justify-center bg-background" role="status" aria-live="polite">
      <div className="flex flex-col items-center gap-4">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" aria-hidden="true" />
        <p className="text-sm text-muted-foreground">加载中...</p>
      </div>
    </div>
  );
}
