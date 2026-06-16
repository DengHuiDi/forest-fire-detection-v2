import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "VIGILANT-OS V2.4",
  description: "Sentient Guardian — Forest Fire Detection & Monitoring Dashboard",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body className="h-full antialiased">{children}</body>
    </html>
  );
}
