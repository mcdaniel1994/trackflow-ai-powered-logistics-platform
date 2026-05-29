import type { Translation } from "./types";

export const en: Translation = {
  common: {
    skipContent: "Skip to content",
    nav: {
      home: "Home",
      services: "Services",
      coverage: "Coverage",
      contact: "Contact",
      apply: "Apply",
    },
    language: {
      next: "ES",
      aria: "Switch to Spanish",
    },
    footer: {
      copyright: "© 2026 TrackFlow. All rights reserved.",
      updated: "Last updated: April 2026",
      privacy: "Privacy Policy",
      linkedin: "LinkedIn",
    },
  },
  home: {
    hero: {
      headlineLead: "Logistics that scales with your",
      headlineHighlight: "e-commerce",
      subheading:
        "Warehouse management, last-mile deliveries, and reverse logistics in the United States and Spain. Over 15 years helping fashion, electronics, and cosmetics brands grow without worrying about operations.",
      cta: "Request information",
      imageAlt:
        "Modern warehouse dispatch area with parcels moving from storage to a delivery van",
    },
    services: {
      title: "Our Services",
      subtitle:
        "End-to-end logistics solutions for e-commerce brands operating in the United States and Spain.",
      cards: [
        {
          title: "Warehouse Management",
          items: [
            "Storage, picking and packing",
            "Real-time inventory",
            "Warehouses in Los Angeles and Zaragoza",
          ],
        },
        {
          title: "Last-Mile Deliveries",
          items: [
            "Certified carrier network in both countries",
            "Unified shipment tracking",
            "Incident and returns management",
          ],
        },
        {
          title: "Reverse Logistics",
          items: [
            "Complete returns management",
            "Inspection and reconditioning",
            "Integration with your sales platform",
          ],
        },
      ],
    },
    coverage: {
      title: "Our Coverage",
      subtitle:
        "Own infrastructure in two markets - the only logistics operator with warehouses in both the United States and Spain.",
      warehouseLabel: "Warehouse",
      coverageLabel: "Coverage",
      carriersLabel: "Carriers",
      regions: [
        {
          market: "United States",
          city: "Los Angeles, California",
          warehouse: "Los Angeles - main facility",
          coverage: "National coverage across the United States",
          carriers: "UPS, FedEx, DHL",
        },
        {
          market: "Spain",
          city: "Zaragoza, Aragon",
          warehouse: "Zaragoza - main facility",
          coverage: "Peninsular and island coverage",
          carriers: "MRW, SEUR, DHL",
        },
      ],
    },
    benefits: {
      title: "Why TrackFlow",
      subtitle:
        "Founded in 2009. Trusted by leading e-commerce brands across two continents.",
      cards: [
        {
          title: "Binational Operation",
          description:
            "The only operator with own infrastructure in the United States and Spain",
        },
        {
          title: "130+ Professionals",
          description: "Dedicated to your logistics across both countries",
        },
        {
          title: "Own Technology",
          description:
            "Total visibility of your inventory with our proprietary platform",
        },
        {
          title: "E-commerce Specialization",
          description:
            "Fashion, electronics, and cosmetics brands trust us",
        },
      ],
    },
    faq: {
      title: "Frequently Asked Questions",
      subtitle: "Answers to common questions about TrackFlow's logistics services.",
      items: [
        {
          question: "What is TrackFlow?",
          answer:
            "TrackFlow is a third-party logistics provider founded in 2009, specializing in warehouse management, last-mile delivery, and reverse logistics for e-commerce brands in the United States and Spain. We operate two warehouse facilities - Los Angeles, California and Zaragoza, Spain - staffed by over 130 logistics professionals.",
        },
        {
          question: "What markets does TrackFlow serve?",
          answer:
            "TrackFlow operates in the United States and Spain. Our Los Angeles warehouse provides national US coverage through UPS, FedEx, and DHL. Our Zaragoza warehouse delivers peninsular and island coverage across Spain through MRW, SEUR, and DHL.",
        },
        {
          question: "What shipping volume does TrackFlow require?",
          answer:
            "TrackFlow is designed for e-commerce businesses shipping 100 or more orders per month. For brands under that threshold, our full-service 3PL model may not be the most cost-effective option; we will tell you directly during the initial consultation.",
        },
        {
          question: "What product categories does TrackFlow specialize in?",
          answer:
            "TrackFlow specializes in fashion, electronics, and cosmetics. These categories require specific handling - climate control, secure packaging, and precise inventory tracking - which our facilities are equipped to provide.",
        },
        {
          question: "How quickly does TrackFlow respond to information requests?",
          answer:
            "Our commercial team reviews every request and responds within 24-48 business hours. We then schedule a discovery call to understand your volume, product type, and operational needs before proposing a service agreement.",
        },
      ],
    },
    contact: {
      title: "Contact Us",
      subtitle:
        "Our commercial team is ready to help you scale your logistics operations.",
      emailLabel: "Email",
      losAngelesLabel: "Los Angeles",
      zaragozaLabel: "Zaragoza",
      cta: "Request information",
    },
  },
  application: {
    title: "Request Information",
    subtitle:
      "Tell us about your company and logistics needs. Our commercial team will contact you within 24-48 hours.",
    form: {
      fieldsets: {
        company: "Company Information",
        service: "Service Information",
      },
      fields: {
        companyName: { label: "Company name", placeholder: "Acme Corp" },
        contactPerson: { label: "Contact person", placeholder: "Jane Smith" },
        corporateEmail: {
          label: "Corporate email",
          placeholder: "name@company.com",
        },
        phone: {
          label: "Phone",
          placeholder: "+1 213 555 0147",
          hint: "Include country code, e.g. +1 213 555 0147",
        },
        companyWebsite: {
          label: "Company website",
          placeholder: "https://yourcompany.com",
        },
        operatingCountry: {
          label: "Main operating country",
          placeholder: "Select a country",
        },
        productType: {
          label: "Product type",
          placeholder: "Select product type",
        },
        monthlyVolume: {
          label: "Estimated monthly shipping volume",
          placeholder: "Select volume range",
        },
        services: { label: "Services of interest" },
        current3pl: { label: "Do you currently work with another 3PL?" },
        comments: {
          label: "Comments or specific needs",
          placeholder:
            "Tell us about your specific needs or any questions you have...",
        },
        privacyPolicy: {
          text: "I accept the",
          link: "privacy policy",
        },
      },
      options: {
        countries: {
          us: "United States",
          es: "Spain",
          both: "Both",
          other: "Other",
        },
        products: {
          fashion: "Fashion",
          electronics: "Electronics",
          cosmetics: "Cosmetics",
          food: "Food",
          other: "Other",
        },
        volumes: {
          "0-100": "0-100 shipments/month",
          "101-500": "101-500 shipments/month",
          "501-2000": "501-2,000 shipments/month",
          "2000+": "2,000+ shipments/month",
          "not-sure": "Not sure",
        },
        services: {
          warehousing: "Warehousing",
          "last-mile": "Last mile",
          "reverse-logistics": "Reverse logistics",
        },
        current3pl: {
          yes: "Yes",
          no: "No",
          evaluating: "Evaluating options",
        },
      },
      lowVolumeWarning:
        "For volumes under 100 monthly shipments, our services might not be the most efficient solution. Are you sure you want to continue?",
      remaining: "remaining",
      overLimit: "over limit",
      requiredNote: "Required fields",
      submit: "Send request",
      clear: "Clear form",
      optional: "(optional)",
      success: {
        title: "Thank you for your interest in TrackFlow!",
        body:
          "We have received your request. Our commercial team will review your information and contact you within the next 24-48 hours to schedule a call and learn about your logistics needs in detail.",
        urgent: "If you have any urgent inquiry, write to us directly at",
      },
      errors: {
        companyName: "Company name must have at least 2 characters",
        contactPerson: "Enter first and last name of contact",
        corporateEmail:
          "Enter a valid corporate email (example: name@company.com)",
        phone: "Phone must include country code (example: +1 213 555 0147)",
        companyWebsite: "If you include website, it must be a valid URL",
        operatingCountry: "Select main operating country",
        productType: "Select the type of product you handle",
        monthlyVolume: "Select estimated monthly volume",
        services: "Select at least one service of interest",
        current3pl:
          "Indicate if you currently work with another logistics provider",
        comments: "Comment exceeds the 500-character limit",
        privacyPolicy: "You must accept the privacy policy to continue",
      },
    },
  },
  privacy: {
    title: "Privacy Policy",
    updated: "Last updated: April 24, 2026",
    sections: {
      about: "About This Site",
      aboutBody:
        "TrackFlow is a portfolio project built as part of an AI Engineering program at 4Geeks Academy. The company scenario, services, and operational details are realistic and representative of a professional logistics operation, but TrackFlow is not a commercially active business.",
      data: "Information Submitted Through the Form",
      dataBody:
        "collects company name, contact name, email address, phone number, and logistics requirements. Because TrackFlow is a portfolio project:",
      dataItems: [
        "Form submissions are not processed commercially.",
        "No submitted data is stored in a production database or shared with third parties.",
        "The form exists to demonstrate a complete, production-quality lead capture flow.",
      ],
      cookies: "Cookies and Local Storage",
      cookiesBody:
        "This site uses browser localStorage to remember your language preference between visits. No tracking cookies, analytics cookies, or third-party cookies are set.",
      hosting: "Hosting",
      hostingBody:
        "This site is hosted on Vercel. Vercel may collect standard server logs such as IP address, browser type, and pages visited as part of normal hosting infrastructure.",
      contact: "Contact",
      contactBody:
        "Questions about this privacy policy can be directed to comercial@trackflow.com.",
    },
  },
};
