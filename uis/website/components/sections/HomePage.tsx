"use client";

import { Benefits } from "./Benefits";
import { ContactCTA } from "./ContactCTA";
import { Coverage } from "./Coverage";
import { FAQ } from "./FAQ";
import { Hero } from "./Hero";
import { Services } from "./Services";
import { useLocale } from "@/components/layout/LocaleProvider";

export function HomePage() {
  const { copy } = useLocale();

  return (
    <>
      <Hero copy={copy.home.hero} />
      <Services copy={copy.home.services} />
      <Coverage copy={copy.home.coverage} />
      <Benefits copy={copy.home.benefits} />
      <FAQ copy={copy.home.faq} />
      <ContactCTA copy={copy.home.contact} />
    </>
  );
}
