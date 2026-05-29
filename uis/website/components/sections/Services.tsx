import { CheckCircle2 } from "lucide-react";
import type { Translation } from "@/content/types";

type ServicesCopy = Translation["home"]["services"];

export function Services({ copy }: { copy: ServicesCopy }) {
  return (
    <section id="services" className="bg-white py-20" aria-labelledby="services-heading">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-3xl text-center">
          <h2 id="services-heading" className="text-3xl font-black text-navy-deep sm:text-4xl">
            {copy.title}
          </h2>
          <p className="mt-4 text-lg leading-8 text-neutral-600">{copy.subtitle}</p>
        </div>
        <div className="mt-14 grid grid-cols-1 gap-6 md:grid-cols-3">
          {copy.cards.map((service) => (
            <article
              key={service.title}
              tabIndex={0}
              className="rounded-lg border border-neutral-200 bg-white p-7 shadow-sm transition hover:-translate-y-1 hover:border-teal/60 hover:shadow-soft focus-visible:shadow-soft"
            >
              <h3 className="text-xl font-black text-navy">{service.title}</h3>
              <ul className="mt-6 space-y-4 text-neutral-700">
                {service.items.map((item) => (
                  <li key={item} className="flex gap-3">
                    <span
                      aria-hidden="true"
                      className="mt-0.5 flex h-6 w-6 flex-none items-center justify-center rounded-md bg-coral/10 text-coral ring-1 ring-coral/20"
                    >
                      <CheckCircle2 className="h-4 w-4" strokeWidth={2.4} />
                    </span>
                    <span className="leading-7">{item}</span>
                  </li>
                ))}
              </ul>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
