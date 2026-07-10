"use client";

type QrPayload = {
  subject?: string;
  body_copy?: string;
  cta_text?: string;
  poster_title?: string;
  poster_body?: string;
  qr_image_data_url?: string;
  scan_url?: string;
  preview_url?: string;
  placement_context?: string;
  verification_note?: string;
};

export function QrPosterPreview({ payload, compact = false }: { payload: QrPayload; compact?: boolean }) {
  return (
    <div className={compact ? "grid gap-4 md:grid-cols-[150px_1fr]" : "grid gap-5 lg:grid-cols-[320px_1fr]"}>
      <div className="overflow-hidden rounded-lg border border-ink/10 bg-[#f4f1e8] p-4 shadow-card">
        <div className="rounded-md border border-[#22314d]/15 bg-white p-4">
          <div className="flex items-center justify-between border-b border-ink/10 pb-3">
            <div>
              <div className="text-[0.65rem] font-bold uppercase tracking-[0.22em] text-tide">Internal Notice</div>
              <div className="mt-1 text-lg font-extrabold text-ink">Workplace Services</div>
            </div>
            <div className="rounded-md bg-tide/10 px-3 py-1 text-[0.65rem] font-bold uppercase tracking-[0.18em] text-tide">
              QR
            </div>
          </div>

          <div className="py-5 text-center">
            <h3 className="text-2xl font-extrabold leading-tight text-ink">
              {payload.poster_title ?? payload.subject ?? "Secure QR Verification"}
            </h3>
            <p className="mx-auto mt-3 max-w-xs text-sm leading-6 text-slate">
              {payload.poster_body ?? payload.body_copy ?? "Scan to review the pending workplace request."}
            </p>
          </div>

          <div className="mx-auto max-w-[210px] rounded-md border border-ink/10 bg-white p-4 shadow-sm">
            {payload.qr_image_data_url ? (
              <img src={payload.qr_image_data_url} alt="Generated QR code" className="aspect-square w-full rounded-md object-contain" />
            ) : (
              <div className="aspect-square rounded-md bg-slate/10" />
            )}
          </div>

          <div className="mt-5 rounded-md bg-ink px-4 py-3 text-center text-sm font-bold text-white">
            {payload.cta_text ?? "Scan to Continue"}
          </div>
          <div className="mt-4 text-center text-[0.65rem] uppercase tracking-[0.18em] text-slate">
            {payload.placement_context ?? "Office noticeboard or desk card"}
          </div>
        </div>
      </div>

      <div className="space-y-3 text-sm text-slate">
        <div className="rounded-md border border-ink/10 bg-white/80 px-4 py-3">
          <span className="font-semibold text-ink">Scan tracking:</span> opening the QR URL records <span className="font-semibold text-ink">scanned_qr</span>, then redirects to the training page.
        </div>
        <div className="rounded-md border border-ink/10 bg-white/80 px-4 py-3">
          <div className="font-semibold text-ink">Scan URL</div>
          <div className="mt-1 break-all">{payload.scan_url}</div>
        </div>
        <div className="rounded-md border border-ink/10 bg-white/80 px-4 py-3">
          <div className="font-semibold text-ink">Landing URL</div>
          <div className="mt-1 break-all">{payload.preview_url}</div>
        </div>
        <div className="rounded-md border border-ink/10 bg-white/80 px-4 py-3">
          {payload.verification_note ?? "The landing workflow records behavior events only; entered credentials are not stored."}
        </div>
      </div>
    </div>
  );
}
