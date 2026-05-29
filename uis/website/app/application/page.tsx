import type { Metadata } from "next";
import { ApplicationPage } from "@/components/forms/ApplicationPage";
import { JsonLd } from "@/components/seo/JsonLd";
import { contactPageSchema } from "@/content/schema";

export const metadata: Metadata = {
  title: "Request Information - TrackFlow Logistics",
  description:
    "Request information about TrackFlow's warehouse management, last-mile delivery, and reverse logistics services for your e-commerce business in the US and Spain.",
  alternates: {
    canonical: "/application",
  },
  openGraph: {
    title: "Request Information - TrackFlow Logistics",
    description:
      "Tell us about your company and logistics needs. Our commercial team will contact you within 24-48 hours.",
    url: "/application",
    type: "website",
  },
  twitter: {
    title: "Request Information - TrackFlow Logistics",
    description:
      "Tell us about your company and logistics needs. Our commercial team will contact you within 24-48 hours.",
  },
};

export default function Page() {
  return (
    <main id="main-content">
      <ApplicationPage />
      <JsonLd data={contactPageSchema()} />
    </main>
  );
}
