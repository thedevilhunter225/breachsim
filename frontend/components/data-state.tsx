import { AlertCircle, Loader2, RefreshCw } from "lucide-react";

export function DataState({ label, error, onRetry }: { label: string; error?: string | null; onRetry?: () => void }) {
  return (
    <section className="overview-card grid min-h-64 place-items-center p-8 text-center" role={error ? "alert" : "status"}>
      <div className="max-w-sm">
        {error ? <AlertCircle className="mx-auto mb-4 text-breach" size={24} /> : <Loader2 className="mx-auto mb-4 animate-spin text-muted" size={22} />}
        <h1 className="text-lg font-medium">{error ? `${label} is unavailable` : `Loading ${label.toLowerCase()}…`}</h1>
        {error ? <p className="mt-2 text-sm leading-6 text-muted">{error}</p> : <p className="mt-2 text-sm text-muted">Retrieving your workspace records.</p>}
        {error && onRetry ? <button type="button" onClick={onRetry} className="app-secondary-button mt-5"><RefreshCw size={14} />Try again</button> : null}
      </div>
    </section>
  );
}
