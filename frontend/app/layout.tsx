import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "The Lenny Growth Assistant",
  description: "Grounded product & growth Q&A over Lenny's Podcast transcripts",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="h-screen overflow-hidden antialiased">{children}</body>
    </html>
  );
}
