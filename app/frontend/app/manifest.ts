import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "조각 JOGAK",
    short_name: "조각",
    description: "여행지를 사진이 아니라 손에 잡히는 문화 피규어로 남기는 PWA",
    start_url: "/",
    scope: "/",
    display: "standalone",
    background_color: "#fbfaf7",
    theme_color: "#111111",
    orientation: "portrait",
    icons: [
      {
        src: "/icons/jogak-transparent.png",
        sizes: "426x373",
        type: "image/png",
        purpose: "any"
      },
      {
        src: "/icons/jogak-logo.png",
        sizes: "1254x1254",
        type: "image/png",
        purpose: "maskable"
      }
    ],
    shortcuts: [
      {
        name: "관광지 탐색",
        short_name: "탐색",
        url: "/?screen=explore",
        icons: [{ src: "/icons/jogak-transparent.png", sizes: "426x373" }]
      },
      {
        name: "장소 해금",
        short_name: "해금",
        url: "/?screen=unlock",
        icons: [{ src: "/icons/jogak-transparent.png", sizes: "426x373" }]
      }
    ]
  };
}
