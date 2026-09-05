"use client";

import { CheckCircle2, Mail, QrCode, ShieldCheck } from "lucide-react";

type QrPayload = {
  subject?: string;
  body_copy?: string;
  email_subject?: string;
  email_body?: string;
  cta_text?: string;
  poster_title?: string;
  poster_body?: string;
  qr_image_data_url?: string;
  scan_url?: string;
  preview_url?: string;
  placement_context?: string;
  verification_note?: string;
  sender_name?: string;
  from_email?: string;
  recipient?: string;
  delivery_format?: string;
};

export function QrPosterPreview({ payload, compact = false }: { payload: QrPayload; compact?: boolean }) {
  const subject = payload.email_subject ?? payload.poster_title ?? payload.subject ?? "Security policy review required";
  const body = payload.email_body ?? payload.poster_body ?? payload.body_copy ?? "Please review the pending security notice for your account.";
  const senderName = payload.sender_name ?? "Security Operations";

  return (
    <div className={compact ? "space-y-3" : "grid gap-5 lg:grid-cols-[minmax(0,1fr)_260px]"}>
      <div className="overflow-hidden rounded-xl border border-ink/10 bg-[#eef1f5] shadow-card">
        <div className="flex items-center gap-2 border-b border-ink/10 bg-white px-4 py-3 text-[0.72rem] text-slate">
          <Mail size={14} className="text-tide" />
          <span className="font-bold uppercase tracking-[0.15em] text-ink">Email preview</span>
          <span className="ml-auto inline-flex items-center gap-1.5 rounded-full bg-safe/10 px-2.5 py-1 font-semibold text-safe">
            <CheckCircle2 size={12} /> Inline QR
          </span>
        </div>

        <div className="border-b border-ink/10 bg-white px-5 py-4 text-[0.76rem] leading-5 text-slate">
          <div><span className="inline-block w-14 text-subtle">From</span><span className="font-medium text-ink">{senderName}</span> &lt;{payload.from_email ?? "security@example.com"}&gt;</div>
          <div><span className="inline-block w-14 text-subtle">To</span>{payload.recipient ?? "Employee recipient"}</div>
          <div><span className="inline-block w-14 text-subtle">Subject</span><span className="font-semibold text-ink">{subject}</span></div>
        </div>

        <div className={compact ? "bg-white px-5 py-7" : "bg-white px-7 py-9 sm:px-10"}>
          <div className="mx-auto max-w-[620px] font-sans text-[0.88rem] leading-6 text-[#202124]">
            <div className="border-b border-[#e6e9ee] pb-4 text-center">
              <div className="text-[0.64rem] font-bold uppercase tracking-[0.2em] text-[#667085]">
                Security notice
              </div>
              <h3 className="mt-2 text-xl font-bold leading-7 text-[#173b73]">{subject}</h3>
            </div>

            <div className="pt-6">
              <p>Dear User,</p>
              <p className="mt-4 whitespace-pre-line">{body}</p>
              <p className="mt-4 font-semibold">Scan the QR code below with your phone camera to continue.</p>

              <div className="mt-5 w-fit border border-[#d8dde5] bg-white p-3">
                {payload.qr_image_data_url ? (
                  <img
                    src={payload.qr_image_data_url}
                    alt="QR code embedded in the email"
                    className={compact ? "h-40 w-40 object-contain" : "h-52 w-52 object-contain"}
                  />
                ) : (
                  <div className="flex h-44 w-44 items-center justify-center bg-[#f4f6f8] text-[#667085]">
                    <QrCode size={58} strokeWidth={1.4} />
                  </div>
                )}
              </div>

              <ol className="mt-6 list-decimal space-y-1.5 pl-5 text-[#344054]">
                <li>Open the camera on your mobile device.</li>
                <li>Point it at the QR code in this email.</li>
                <li>Review the destination before completing any requested action.</li>
              </ol>

              <div className="mt-7 border-t border-[#e6e9ee] bg-[#f8fafc] px-4 py-3 text-[0.7rem] leading-5 text-[#667085]">
                This automated notice was sent by {senderName}. Please follow your organization&apos;s security and privacy policy.
              </div>
            </div>
          </div>
        </div>
      </div>

      {!compact ? (
        <div className="space-y-3 text-sm text-slate">
          <div className="rounded-lg border border-safe/20 bg-safe/8 px-4 py-3">
            <div className="flex items-center gap-2 font-semibold text-ink"><Mail size={15} /> Email delivery</div>
            <p className="mt-1.5 text-xs leading-5">The delivered QR is referenced as a remote HTTPS image in the email body, so it remains visually inline without a MIME attachment.</p>
          </div>
          <div className="rounded-lg border border-ink/10 bg-white/80 px-4 py-3">
            <div className="flex items-center gap-2 font-semibold text-ink"><ShieldCheck size={15} /> Unique tracking</div>
            <p className="mt-1.5 text-xs leading-5">Each recipient gets a unique scan token before redirecting to the training page.</p>
          </div>
          {payload.scan_url ? <div className="rounded-lg border border-ink/10 bg-white/80 px-4 py-3">
            <div className="font-semibold text-ink">Scan URL</div>
            <div className="mt-1 break-all text-xs leading-5">{payload.scan_url}</div>
          </div> : null}
          {payload.preview_url ? <div className="rounded-lg border border-ink/10 bg-white/80 px-4 py-3">
            <div className="font-semibold text-ink">Landing URL</div>
            <div className="mt-1 break-all text-xs leading-5">{payload.preview_url}</div>
          </div> : null}
          <div className="rounded-lg border border-ink/10 bg-white/80 px-4 py-3 text-xs leading-5">
            {payload.verification_note ?? "The landing workflow records behavior events only; entered credentials are not stored."}
          </div>
        </div>
      ) : null}
    </div>
  );
}
