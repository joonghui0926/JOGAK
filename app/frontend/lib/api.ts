import type { Destination, DestinationCulture, EditorLayer, JobStatus, PartAsset } from "./types";
import { getApiBase } from "./config";

const API_BASE = getApiBase();

let authToken = typeof window !== "undefined" ? window.localStorage.getItem("jogak_access_token") : null;

export function setAuthToken(token: string) {
  authToken = token;
  if (typeof window !== "undefined") {
    window.localStorage.setItem("jogak_access_token", token);
  }
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
      ...(init?.headers || {})
    }
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export async function fetchDestinations(query = ""): Promise<Destination[]> {
  const params = query ? `?q=${encodeURIComponent(query)}` : "";
  return apiFetch<Destination[]>(`/api/destinations${params}`);
}

export async function fetchDestinationParts(destinationId: string): Promise<PartAsset[]> {
  return apiFetch<PartAsset[]>(`/api/destinations/${destinationId}/parts`);
}

export async function fetchDestinationCulture(destinationId: string): Promise<DestinationCulture> {
  return apiFetch<DestinationCulture>(`/api/destinations/${destinationId}/culture`);
}

export type AuthUser = { id: string; email?: string | null; display_name: string; is_guest: boolean; role?: string };

export async function fetchMe() {
  return apiFetch<AuthUser>("/auth/me");
}

export async function createGuestSession() {
  return apiFetch<{ access_token: string; user: AuthUser }>(
    "/auth/guest",
    { method: "POST" }
  );
}

export async function startEmailLogin(email: string) {
  return apiFetch<{
    ok: boolean;
    message: string;
    access_token?: string;
    user?: AuthUser;
  }>("/auth/email/start", {
    method: "POST",
    body: JSON.stringify({ email })
  });
}

export async function createPretravelConcept(form: FormData) {
  return apiFetch<{ figurine_id: string; job_id: string; status: string }>("/api/prefigurines/concept", {
    method: "POST",
    body: form
  });
}

export async function checkVisit(destinationId: string, lat: number, lon: number, accuracyM = 30, reviewBypass = false) {
  return apiFetch<{ verified: boolean; unlocked_parts: string[]; distance_m: number }>("/api/visits/check", {
    method: "POST",
    body: JSON.stringify({ destination_id: destinationId, lat, lon, accuracy_m: accuracyM, dwell_seconds: 180, review_bypass: reviewBypass })
  });
}

export async function fetchJob(jobId: string): Promise<JobStatus> {
  return apiFetch<JobStatus>(`/api/jobs/${jobId}`);
}

export async function createEditorSession(destinationId: string, figurineId?: string | null) {
  return apiFetch<{ id: string; destination_id: string; figurine_id: string | null; state: string; composition_json: Record<string, unknown> }>(
    "/api/editor/sessions",
    {
      method: "POST",
      body: JSON.stringify({ destination_id: destinationId, figurine_id: figurineId || null, composition_json: {} })
    }
  );
}

export async function patchEditorLayers(sessionId: string, layers: EditorLayer[]) {
  return apiFetch<{ id: string; destination_id: string; figurine_id: string | null; state: string; composition_json: Record<string, unknown> }>(
    `/api/editor/sessions/${sessionId}/layers`,
    {
      method: "PATCH",
      body: JSON.stringify({
        layers: layers.map((layer) => ({
          part_asset_id: layer.partAssetId || null,
          x: layer.x,
          y: layer.y,
          scale: layer.scale,
          rotation: layer.rotation,
          opacity: 1,
          z_index: layer.z,
          visible: true
        })),
        composition_json: {
          stage_width: 312,
          stage_height: 288,
          source: "mobile_editor"
        }
      })
    }
  );
}

export async function finalizeEditor3D(sessionId: string, compositionImage?: Blob | null) {
  const form = new FormData();
  if (compositionImage) {
    form.append("composition_image", compositionImage, "composition.png");
  }
  return apiFetch<{ job_id: string; status: string }>(`/api/editor/sessions/${sessionId}/finalize-3d`, {
    method: "POST",
    body: form
  });
}

export async function refineEditor2D(sessionId: string, compositionImage?: Blob | null) {
  const form = new FormData();
  if (compositionImage) {
    form.append("composition_image", compositionImage, "composition.png");
  }
  return apiFetch<{ job_id: string; status: string }>(`/api/editor/sessions/${sessionId}/refine-2d`, {
    method: "POST",
    body: form
  });
}
