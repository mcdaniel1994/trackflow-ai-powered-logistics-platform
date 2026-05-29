import type {
  ContactPageSchema,
  FAQItem,
  FAQPageSchema,
  OrganizationSchema,
  WebPageSchema,
} from "./types";

const siteUrl = "https://trackflow.com";
const imageUrl = `${siteUrl}/images/trackflow-operations-hero.png`;

const publisher = {
  "@type": "Organization" as const,
  name: "TrackFlow",
  url: siteUrl,
};

const author = {
  "@type": "Organization" as const,
  name: "TrackFlow",
};

export function organizationSchema(): OrganizationSchema {
  return {
    "@context": "https://schema.org",
    "@type": "Organization",
    name: "TrackFlow",
    description: "Warehouse management and last-mile deliveries for e-commerce",
    url: siteUrl,
    logo: `${siteUrl}/images/trackflow-operations-hero.png`,
    foundingDate: "2009",
    foundingLocation: { "@type": "Place", name: "Los Angeles, California, US" },
    numberOfEmployees: { "@type": "QuantitativeValue", value: 130 },
    address: [
      {
        "@type": "PostalAddress",
        addressCountry: "US",
        addressLocality: "Los Angeles",
        addressRegion: "California",
      },
      {
        "@type": "PostalAddress",
        addressCountry: "ES",
        addressLocality: "Zaragoza",
        addressRegion: "Aragon",
      },
    ],
    contactPoint: {
      "@type": "ContactPoint",
      telephone: "+1-213-555-0147",
      contactType: "sales",
      availableLanguage: ["Spanish", "English"],
    },
    sameAs: ["https://linkedin.com/company/trackflow"],
    areaServed: [
      { "@type": "Country", name: "United States" },
      { "@type": "Country", name: "Spain" },
    ],
  };
}

export function webPageSchema(args: {
  name: string;
  headline: string;
  url: string;
  description: string;
  datePublished?: string;
  dateModified?: string;
}): WebPageSchema {
  return {
    "@context": "https://schema.org",
    "@type": "WebPage",
    name: args.name,
    headline: args.headline,
    url: args.url,
    datePublished: args.datePublished ?? "2024-01-01",
    dateModified: args.dateModified ?? "2026-04-24",
    description: args.description,
    author,
    publisher,
    image: imageUrl,
    inLanguage: "en",
  };
}

export function faqPageSchema(items: FAQItem[]): FAQPageSchema {
  return {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: items.map((item) => ({
      "@type": "Question",
      name: item.question,
      acceptedAnswer: {
        "@type": "Answer",
        text: item.answer,
      },
    })),
  };
}

export function contactPageSchema(): ContactPageSchema {
  return {
    "@context": "https://schema.org",
    "@type": "ContactPage",
    name: "Request Information - TrackFlow Logistics",
    headline: "Request Information",
    url: `${siteUrl}/application`,
    datePublished: "2024-01-01",
    dateModified: "2026-04-24",
    description:
      "Request information about TrackFlow's warehouse management, last-mile delivery, and reverse logistics services for your e-commerce business.",
    author,
    publisher,
    image: imageUrl,
    inLanguage: "en",
  };
}
