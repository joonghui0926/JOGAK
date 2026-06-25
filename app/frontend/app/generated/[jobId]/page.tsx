import { ModelViewer } from "../../../components/ModelViewer";
import { getApiBase } from "../../../lib/config";

type GeneratedJob = {
  id: string;
  status: string;
  current_state: string;
  progress: number;
  error: string | null;
  result: {
    concept_url?: string;
    glb_url?: string;
    figurine_id?: string;
    gpu?: string;
  };
};

const API_BASE = getApiBase();

async function fetchGeneratedJob(jobId: string): Promise<GeneratedJob | null> {
  const response = await fetch(`${API_BASE}/api/jobs/${jobId}`, { cache: "no-store" });
  if (!response.ok) {
    return null;
  }
  return response.json();
}

export default async function GeneratedResultPage({ params }: { params: Promise<{ jobId: string }> }) {
  const { jobId } = await params;
  const job = await fetchGeneratedJob(jobId);
  const conceptUrl = job?.result?.concept_url;
  const glbUrl = job?.result?.glb_url;

  return (
    <main className="generated-page">
      <section className="generated-shell">
        <div className="generated-head">
          <img src="/icons/jogak-transparent.png" alt="조각" />
          <div>
            <span>국립중앙박물관</span>
            <h1>생성된 조각 프리뷰</h1>
          </div>
        </div>

        {!job ? (
          <div className="generated-empty">생성 작업을 찾을 수 없습니다.</div>
        ) : job.status !== "done" ? (
          <div className="generated-empty">
            <strong>{job.current_state}</strong>
            <span>{job.error || `${job.progress}% 진행 중`}</span>
          </div>
        ) : (
          <div className="generated-grid">
            <figure className="generated-panel concept-panel">
              {conceptUrl ? <img src={conceptUrl} alt="OpenAI로 생성한 2D 조각 컨셉" /> : null}
              <figcaption>2D 컨셉</figcaption>
            </figure>
            <figure className="generated-panel model-panel">
              <ModelViewer src={glbUrl} />
              <figcaption>Hunyuan3D 프리뷰 · GPU {job.result.gpu || "7"}</figcaption>
            </figure>
          </div>
        )}
      </section>
    </main>
  );
}
