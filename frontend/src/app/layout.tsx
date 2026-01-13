import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Crossfire — Live DDoS Map",
  description: "Real-time DDoS attack visualization",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-zinc-950 antialiased">{children}</body>
    </html>
  );
}
