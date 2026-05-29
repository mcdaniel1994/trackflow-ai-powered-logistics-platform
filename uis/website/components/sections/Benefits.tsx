import { Globe2, Radar, ShoppingBag, Users } from "lucide-react";
import type { Translation } from "@/content/types";

type BenefitsCopy = Translation["home"]["benefits"];

const benefitIcons = [Globe2, Users, Radar, ShoppingBag];

export function Benefits({ copy }: { copy: BenefitsCopy }) {
  return (
    <section id="benefits" className="bg-white py-20" aria-labelledby="benefits-heading">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-3xl text-center">
          <h2 id="benefits-heading" className="text-3xl font-black text-navy-deep sm:text-4xl">
            {copy.title}
          </h2>
          <p className="mt-4 text-lg leading-8 text-neutral-600">{copy.subtitle}</p>
        </div>
        <div className="mt-14 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {copy.cards.map((benefit, index) => {
            const Icon = benefitIcons[index] ?? Globe2;

            return (
              <article
                key={benefit.title}
                tabIndex={0}
                className="rounded-lg border border-neutral-200 bg-white p-6 text-center shadow-sm transition hover:-translate-y-1 hover:border-teal/60 hover:shadow-soft focus-visible:shadow-soft"
              >
                <div
                  className="mx-auto mb-5 flex h-12 w-12 items-center justify-center rounded-md bg-teal/20 text-navy ring-1 ring-teal/30"
                  aria-hidden="true"
                >
                  <Icon className="h-6 w-6" strokeWidth={2.2} />
                </div>
                <h3 className="text-lg font-black text-navy">{benefit.title}</h3>
                <p className="mt-3 text-sm leading-6 text-neutral-600">{benefit.description}</p>
              </article>
            );
          })}
        </div>
      </div>
    </section>
  );
}
