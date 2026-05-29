import type { LeadFormCopy, LeadFormData, LeadFormErrors } from "@/content/types";

export function createEmptyLeadFormData(): LeadFormData {
  return {
    companyName: "",
    contactPerson: "",
    corporateEmail: "",
    phone: "",
    companyWebsite: "",
    operatingCountry: "",
    productType: "",
    monthlyVolume: "",
    services: [],
    current3pl: "",
    comments: "",
    privacyPolicy: false,
  };
}

export function validateLeadField(
  field: keyof LeadFormData,
  data: LeadFormData,
  copy: LeadFormCopy,
): string | null {
  switch (field) {
    case "companyName": {
      const value = data.companyName.trim();
      if (!value || value.length < 2) return copy.errors.companyName;
      if (/\d/.test(value)) return copy.errors.companyName;
      return null;
    }
    case "contactPerson": {
      const value = data.contactPerson.trim();
      const parts = value.split(/\s+/).filter(Boolean);
      if (!value || parts.length < 2) return copy.errors.contactPerson;
      return null;
    }
    case "corporateEmail": {
      const value = data.corporateEmail.trim();
      if (!value || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
        return copy.errors.corporateEmail;
      }
      return null;
    }
    case "phone": {
      const value = data.phone.trim();
      if (!value || !/^\+\d[\d\s\-().]{5,}$/.test(value)) return copy.errors.phone;
      return null;
    }
    case "companyWebsite": {
      const value = data.companyWebsite?.trim() ?? "";
      if (!value) return null;
      try {
        const url = new URL(value);
        if (url.protocol !== "http:" && url.protocol !== "https:") {
          return copy.errors.companyWebsite;
        }
        return null;
      } catch {
        return copy.errors.companyWebsite;
      }
    }
    case "operatingCountry":
      return data.operatingCountry ? null : copy.errors.operatingCountry;
    case "productType":
      return data.productType ? null : copy.errors.productType;
    case "monthlyVolume":
      return data.monthlyVolume ? null : copy.errors.monthlyVolume;
    case "services":
      return data.services.length > 0 ? null : copy.errors.services;
    case "current3pl":
      return data.current3pl ? null : copy.errors.current3pl;
    case "comments": {
      const value = data.comments ?? "";
      if (value.length > 500) {
        return `${copy.errors.comments} (${value.length - 500} ${copy.overLimit})`;
      }
      return null;
    }
    case "privacyPolicy":
      return data.privacyPolicy ? null : copy.errors.privacyPolicy;
    default:
      return null;
  }
}

export function validateLeadForm(data: LeadFormData, copy: LeadFormCopy): LeadFormErrors {
  const fields: Array<keyof LeadFormData> = [
    "companyName",
    "contactPerson",
    "corporateEmail",
    "phone",
    "companyWebsite",
    "operatingCountry",
    "productType",
    "monthlyVolume",
    "services",
    "current3pl",
    "comments",
    "privacyPolicy",
  ];

  return fields.reduce<LeadFormErrors>((errors, field) => {
    const error = validateLeadField(field, data, copy);
    if (error) {
      errors[field] = error;
    }
    return errors;
  }, {});
}
