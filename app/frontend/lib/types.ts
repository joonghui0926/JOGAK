export type Screen =
  | "login"
  | "home"
  | "explore"
  | "destination"
  | "maker"
  | "prepreview"
  | "parts"
  | "unlock"
  | "customize"
  | "generate"
  | "editor"
  | "preview"
  | "story"
  | "print"
  | "shipping"
  | "profile";

export type Destination = {
  id: string;
  no: number;
  region: string;
  name: string;
  dna: string;
  lat: number;
  lon: number;
  radius_m: number;
  summary: string;
  parts: string[];
};

export type PartAsset = {
  id: string;
  destination_id: string;
  slot: string;
  name: string;
  image_path?: string | null;
  image_url?: string | null;
  mask_path?: string | null;
  mask_url?: string | null;
  default_anchor: Record<string, unknown>;
  allowed_transform: Record<string, unknown>;
  prompt_hint?: string | null;
  source_note?: string | null;
  unlocked: boolean;
};

export type EditorLayer = {
  id: string;
  partAssetId?: string;
  label: string;
  slot: string;
  x: number;
  y: number;
  scale: number;
  rotation: number;
  z: number;
  color: string;
  imageUrl?: string | null;
};

export type JobStatus = {
  id: string;
  status: string;
  type: string;
  progress: number;
  current_state?: string;
  result?: Record<string, unknown>;
  error?: string | null;
};
