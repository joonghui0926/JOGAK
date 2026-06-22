import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  allowedDevOrigins: ["127.0.0.1", "localhost", "143.248.47.23"],
  output: "standalone",
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "**.visitkorea.or.kr" },
      { protocol: "https", hostname: "**.culture.go.kr" },
      { protocol: "https", hostname: "**.openai.com" },
      { protocol: "https", hostname: "**.openstreetmap.org" }
    ]
  }
};

export default nextConfig;
