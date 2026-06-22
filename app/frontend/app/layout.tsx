import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "조각 JOGAK",
  description: "여행지를 조각하는 AI 문화관광 PWA",
  icons: {
    icon: "/favicon.png",
    apple: "/icons/jogak-transparent.png"
  },
  appleWebApp: {
    capable: true,
    title: "조각",
    statusBarStyle: "default"
  }
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  themeColor: "#111111",
  viewportFit: "cover"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
