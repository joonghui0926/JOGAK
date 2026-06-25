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
  tourapi_content_id?: string | null;
  representative_image_url?: string | null;
  parts: string[];
};

export type PublicDataSource = {
  id: string;
  provider: string;
  dataset_id: string;
  record_type: string;
  title: string;
  summary?: string | null;
  period?: string | null;
  material?: string | null;
  institution?: string | null;
  image_url?: string | null;
  source_url?: string | null;
  license_note?: string | null;
  starts_at?: string | null;
  ends_at?: string | null;
  relation_type?: string | null;
  verified: boolean;
};

export type DestinationCulture = {
  destination_id: string;
  culture_dna: {
    theme?: string;
    motifs?: Record<string, unknown>;
    style_rules?: Record<string, unknown>;
  };
  destination_sources: PublicDataSource[];
  exhibitions: PublicDataSource[];
  part_sources: Record<string, PublicDataSource[]>;
  sync_enabled: boolean;
  configured_sources: string[];
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
  limited: boolean;
  limited_available: boolean;
  public_sources: PublicDataSource[];
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
