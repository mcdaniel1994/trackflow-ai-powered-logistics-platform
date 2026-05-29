import type { Metadata } from "next";
import { HomePage } from "@/components/sections/HomePage";
import { JsonLd } from "@/components/seo/JsonLd";
import { faqPageSchema, webPageSchema } from "@/content/schema";
import { en } from "@/content/site.en";

export const metadata: Metadata = {
  title: "TrackFlow - Warehouse Management & Last-Mile Delivery | US & Spain",
  description:
    "TrackFlow provides warehouse management, last-mile delivery, and reverse logistics for e-commerce brands in the United States and Spain.",
  alternates: {
    canonical: "/",
  },
  openGraph: {
    title: "TrackFlow - Logistics that scales with your e-commerce",
    description:
      "Warehouse management, last-mile deliveries, and reverse logistics in the US and Spain.",
    url: "/",
    type: "website",
  },
  twitter: {
    title: "TrackFlow - Warehouse Management & Last-Mile Delivery | US & Spain",
    description:
      "Warehouse management, last-mile delivery, and reverse logistics for e-commerce brands in the US and Spain.",
  },
};

export default function Page() {
  return (
    <main id="main-content">
      <HomePage />
      <JsonLd
        data={webPageSchema({
          name: "TrackFlow - Warehouse Management & Last-Mile Delivery | US & Spain",
          headline: "Logistics that scales with your e-commerce",
          url: "https://trackflow.com/",
          description:
            "TrackFlow provides warehouse management, last-mile delivery, and reverse logistics for e-commerce brands in the United States and Spain.",
        })}
      />
      <JsonLd data={faqPageSchema(en.home.faq.items)} />
    </main>
  );
}
