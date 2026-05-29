import type { Metadata } from "next";
import { PrivacyPage } from "@/components/sections/PrivacyPage";
import { JsonLd } from "@/components/seo/JsonLd";
import { webPageSchema } from "@/content/schema";

export const metadata: Metadata = {
  title: "Privacy Policy - TrackFlow Logistics",
  description:
    "TrackFlow's privacy policy. Learn how information submitted through the contact form is handled.",
  alternates: {
    canonical: "/privacy",
  },
  openGraph: {
    title: "Privacy Policy - TrackFlow Logistics",
    description:
      "TrackFlow's privacy policy. Learn how information submitted through the contact form is handled.",
    url: "/privacy",
    type: "website",
  },
  twitter: {
    title: "Privacy Policy - TrackFlow Logistics",
    description:
      "TrackFlow's privacy policy. Learn how information submitted through the contact form is handled.",
  },
};

export default function Page() {
  return (
    <main id="main-content">
      <PrivacyPage />
      <JsonLd
        data={webPageSchema({
          name: "Privacy Policy - TrackFlow Logistics",
          headline: "Privacy Policy",
          url: "https://trackflow.com/privacy",
          description:
            "TrackFlow's privacy policy covering data handling for form submissions on this site.",
          datePublished: "2026-04-24",
          dateModified: "2026-04-24",
        })}
      />
    </main>
  );
}
