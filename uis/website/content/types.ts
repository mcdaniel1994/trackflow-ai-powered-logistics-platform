export type Locale = "en" | "es";

export interface NavItem {
  href: string;
  label: string;
}

export interface FAQItem {
  question: string;
  answer: string;
}

export interface ServiceCard {
  title: string;
  items: string[];
}

export interface CoverageRegion {
  market: string;
  city: string;
  warehouse: string;
  coverage: string;
  carriers: string;
}

export interface BenefitCard {
  title: string;
  description: string;
}

export type OperatingCountry = "" | "us" | "es" | "both" | "other";
export type ProductType = "" | "fashion" | "electronics" | "cosmetics" | "food" | "other";
export type MonthlyVolume = "" | "0-100" | "101-500" | "501-2000" | "2000+" | "not-sure";
export type ServiceInterest = "warehousing" | "last-mile" | "reverse-logistics";
export type Current3PL = "" | "yes" | "no" | "evaluating";

export interface LeadFormData {
  companyName: string;
  contactPerson: string;
  corporateEmail: string;
  phone: string;
  companyWebsite?: string;
  operatingCountry: OperatingCountry;
  productType: ProductType;
  monthlyVolume: MonthlyVolume;
  services: ServiceInterest[];
  current3pl: Current3PL;
  comments?: string;
  privacyPolicy: boolean;
}

export type LeadFormErrors = Partial<Record<keyof LeadFormData, string>>;

export interface LeadFormCopy {
  fieldsets: {
    company: string;
    service: string;
  };
  fields: {
    companyName: FieldCopy;
    contactPerson: FieldCopy;
    corporateEmail: FieldCopy;
    phone: FieldCopy & { hint: string };
    companyWebsite: FieldCopy;
    operatingCountry: FieldCopy;
    productType: FieldCopy;
    monthlyVolume: FieldCopy;
    services: { label: string };
    current3pl: { label: string };
    comments: FieldCopy;
    privacyPolicy: {
      text: string;
      link: string;
    };
  };
  options: {
    countries: Record<Exclude<OperatingCountry, "">, string>;
    products: Record<Exclude<ProductType, "">, string>;
    volumes: Record<Exclude<MonthlyVolume, "">, string>;
    services: Record<ServiceInterest, string>;
    current3pl: Record<Exclude<Current3PL, "">, string>;
  };
  lowVolumeWarning: string;
  remaining: string;
  overLimit: string;
  requiredNote: string;
  submit: string;
  clear: string;
  optional: string;
  success: {
    title: string;
    body: string;
    urgent: string;
  };
  errors: Record<keyof LeadFormData, string>;
}

export interface FieldCopy {
  label: string;
  placeholder: string;
}

export interface Translation {
  common: {
    skipContent: string;
    nav: {
      home: string;
      services: string;
      coverage: string;
      contact: string;
      apply: string;
    };
    language: {
      next: string;
      aria: string;
    };
    footer: {
      copyright: string;
      updated: string;
      privacy: string;
      linkedin: string;
    };
  };
  home: {
    hero: {
      headlineLead: string;
      headlineHighlight: string;
      subheading: string;
      cta: string;
      imageAlt: string;
    };
    services: {
      title: string;
      subtitle: string;
      cards: ServiceCard[];
    };
    coverage: {
      title: string;
      subtitle: string;
      warehouseLabel: string;
      coverageLabel: string;
      carriersLabel: string;
      regions: CoverageRegion[];
    };
    benefits: {
      title: string;
      subtitle: string;
      cards: BenefitCard[];
    };
    faq: {
      title: string;
      subtitle: string;
      items: FAQItem[];
    };
    contact: {
      title: string;
      subtitle: string;
      emailLabel: string;
      losAngelesLabel: string;
      zaragozaLabel: string;
      cta: string;
    };
  };
  application: {
    title: string;
    subtitle: string;
    form: LeadFormCopy;
  };
  privacy: {
    title: string;
    updated: string;
    sections: {
      about: string;
      aboutBody: string;
      data: string;
      dataBody: string;
      dataItems: string[];
      cookies: string;
      cookiesBody: string;
      hosting: string;
      hostingBody: string;
      contact: string;
      contactBody: string;
    };
  };
}

export interface OrganizationSchema {
  "@context": "https://schema.org";
  "@type": "Organization";
  name: string;
  description: string;
  url: string;
  logo: string;
  foundingDate: string;
  foundingLocation: {
    "@type": "Place";
    name: string;
  };
  numberOfEmployees: {
    "@type": "QuantitativeValue";
    value: number;
  };
  address: Array<{
    "@type": "PostalAddress";
    addressCountry: string;
    addressLocality: string;
    addressRegion: string;
  }>;
  contactPoint: {
    "@type": "ContactPoint";
    telephone: string;
    contactType: string;
    availableLanguage: string[];
  };
  sameAs: string[];
  areaServed: Array<{
    "@type": "Country";
    name: string;
  }>;
}

export interface WebPageSchema {
  "@context": "https://schema.org";
  "@type": "WebPage";
  name: string;
  headline: string;
  url: string;
  datePublished: string;
  dateModified: string;
  description: string;
  author: {
    "@type": "Organization";
    name: string;
  };
  publisher: {
    "@type": "Organization";
    name: string;
    url: string;
  };
  image: string;
  inLanguage: string;
}

export interface FAQPageSchema {
  "@context": "https://schema.org";
  "@type": "FAQPage";
  mainEntity: Array<{
    "@type": "Question";
    name: string;
    acceptedAnswer: {
      "@type": "Answer";
      text: string;
    };
  }>;
}

export interface ContactPageSchema {
  "@context": "https://schema.org";
  "@type": "ContactPage";
  name: string;
  headline: string;
  url: string;
  datePublished: string;
  dateModified: string;
  description: string;
  author: {
    "@type": "Organization";
    name: string;
  };
  publisher: {
    "@type": "Organization";
    name: string;
    url: string;
  };
  image: string;
  inLanguage: string;
}

export type JsonLdSchema = OrganizationSchema | WebPageSchema | FAQPageSchema | ContactPageSchema;
