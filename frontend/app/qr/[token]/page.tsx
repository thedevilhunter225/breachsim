import { QrScanRedirect } from "@/components/qr-scan-redirect";

export default async function QrScanPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;

  return <QrScanRedirect token={token} />;
}
