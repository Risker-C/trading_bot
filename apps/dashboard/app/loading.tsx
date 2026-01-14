export default function Loading() {
  return (
    <div className="flex min-h-screen flex-col p-8">
      <div className="mb-8">
        <div className="h-9 w-64 mb-2 bg-muted animate-pulse rounded" />
        <div className="h-5 w-48 bg-muted animate-pulse rounded" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-32 bg-muted animate-pulse rounded" />
        ))}
      </div>

      <div className="h-96 bg-muted animate-pulse rounded" />
    </div>
  );
}
