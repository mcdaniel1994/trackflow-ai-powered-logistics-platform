import type { Metadata } from "next";
import { CareersPage } from "@/components/careers/CareersPage";
import { JsonLd } from "@/components/seo/JsonLd";
import { webPageSchema } from "@/content/schema";

const title = "Careers at TrackFlow — Portfolio Demo";
const description =
  "Explore illustrative TrackFlow roles and submit a fictional demo application to see our Talent Pipeline Tracker in action. These are not active vacancies.";
const socialImage = {
  url: "/images/trackflow-operations-hero.png",
  width: 1200,
  height: 630,
  alt: "TrackFlow warehouse management and last-mile logistics in the US and Spain",
};
export const metadata: Metadata = {
  title,
  description,
  alternates: { canonical: "/careers" },
  openGraph: { title, description, url: "/careers", type: "website", siteName: "TrackFlow", images: [socialImage] },
  twitter: { title, description, card: "summary_large_image", images: [socialImage.url] },
};
export default function Page() {
  return (
    <main id="main-content">
      <CareersPage />
      <JsonLd
        data={webPageSchema({
          name: title,
          headline: title,
          description,
          url: "https://trackflow.com/careers",
          datePublished: "2026-10-13",
          dateModified: "2026-10-13",
        })}
      />
    </main>
  );
}
