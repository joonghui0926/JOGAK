CREATE EXTENSION IF NOT EXISTS postgis;

-- Optional PostGIS generated column for production migrations.
-- Keep lat/lon as source-of-truth columns for API portability, then add geom in PostgreSQL.
ALTER TABLE destinations
  ADD COLUMN IF NOT EXISTS geom geography(Point, 4326)
  GENERATED ALWAYS AS (ST_SetSRID(ST_MakePoint(lon, lat), 4326)::geography) STORED;

CREATE INDEX IF NOT EXISTS idx_destinations_geom ON destinations USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_part_assets_destination_slot ON part_assets(destination_id, slot);
CREATE INDEX IF NOT EXISTS idx_editor_layers_session_z ON part_layers(editor_session_id, z_index);
CREATE INDEX IF NOT EXISTS idx_jobs_status_created ON generation_jobs(status, created_at);
