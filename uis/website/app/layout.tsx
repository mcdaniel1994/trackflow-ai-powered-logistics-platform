import type { Metadata } from "next";
import { LocaleProvider } from "@/components/layout/LocaleProvider";
import { MobileNav } from "@/components/layout/MobileNav";
import { SiteFooter } from "@/components/layout/SiteFooter";
import { SiteHeader } from "@/components/layout/SiteHeader";
import { SkipToContent } from "@/components/layout/SkipToContent";
import { JsonLd } from "@/components/seo/JsonLd";
import { organizationSchema } from "@/content/schema";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL("https://trackflow.com"),
  title: {
    default: "TrackFlow - Warehouse Management & Last-Mile Delivery",
    template: "%s | TrackFlow",
  },
  description:
    "TrackFlow provides warehouse management, last-mile delivery, and reverse logistics for e-commerce brands in the United States and Spain.",
  openGraph: {
    siteName: "TrackFlow",
    images: [
      {
        url: "/images/trackflow-operations-hero.png",
        width: 1200,
        height: 630,
        alt: "TrackFlow warehouse management and last-mile logistics in the US and Spain",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    images: ["/images/trackflow-operations-hero.png"],
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="pb-12 md:pb-0">
        <LocaleProvider>
          <SkipToContent />
          <SiteHeader />
          {children}
          <SiteFooter />
          <MobileNav />
        </LocaleProvider>
        <JsonLd data={organizationSchema()} />
      </body>
    </html>
  );
}
