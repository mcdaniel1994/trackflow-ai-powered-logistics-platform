// Root layout — wraps every page in <html>/<body>. In the App Router this is the
// one place we own the document shell. globals.css is imported once here so
// Tailwind's base/components/utilities reach every page.

import type { Metadata } from "next";
import "./globals.css";

// `metadata` is read by Next.js at build/render time and turned into <title>/<meta>
// tags. No need for `next/head`.
export const metadata: Metadata = {
  title: "TrackFlow Talent Pipeline Tracker",
  description:
    "Internal candidate management for the Executive Assistant search at Zaragoza HQ.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
