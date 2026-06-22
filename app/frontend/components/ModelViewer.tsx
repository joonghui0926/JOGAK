"use client";

import React from "react";
import { useEffect } from "react";

export function ModelViewer({ src }: { src?: string }) {
  useEffect(() => {
    import("@google/model-viewer").catch(() => undefined);
  }, []);

  if (!src) {
    return (
      <div className="model-fallback" aria-label="3D 조각 미리보기">
        <span>생성된 3D 파일이 아직 없습니다.</span>
      </div>
    );
  }

  return React.createElement("model-viewer", {
    src,
    "camera-controls": true,
    "auto-rotate": true,
    "interaction-prompt": "none",
    "shadow-intensity": "0.45",
    exposure: "0.92",
    ar: true,
    class: "model-viewer"
  });
}
