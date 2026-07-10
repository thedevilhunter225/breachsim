import { TrainingSimulator } from "@/components/training-simulator";
import { getTrainingToken } from "@/lib/api";

export default async function TrainingPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  const landing = await getTrainingToken(token);

  return (
    <main className="min-h-screen bg-[#eef2f6] px-4 py-8 text-[#111827] md:px-6">
      <div className="mx-auto max-w-6xl">
        <TrainingSimulator token={token} landing={landing} />
      </div>
    </main>
  );
}
