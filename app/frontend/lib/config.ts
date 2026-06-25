export function getApiBase(): string {
  const configured = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (configured) {
    return configured.replace(/\/$/, "");
  }

  if (typeof window !== "undefined") {
    const { protocol, hostname } = window.location;
    if (
      hostname === "munhuajogak.co.kr" ||
      hostname === "www.munhuajogak.co.kr" ||
      hostname.endsWith(".vercel.app")
    ) {
      return "https://api.munhuajogak.co.kr";
    }
    return `${protocol}//${hostname}:8010`;
  }

  const serverConfigured = process.env.JOGAK_API_URL;
  return (serverConfigured || "https://api.munhuajogak.co.kr").replace(/\/$/, "");
}
