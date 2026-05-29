import { ChevronDown } from "lucide-react";
import type { Translation } from "@/content/types";

type FAQCopy = Translation["home"]["faq"];

export function FAQ({ copy }: { copy: FAQCopy }) {
  return (
    <section id="faq" className="bg-mist py-20" aria-labelledby="faq-heading">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-3xl text-center">
          <h2 id="faq-heading" className="text-3xl font-black text-navy-deep sm:text-4xl">
            {copy.title}
          </h2>
          <p className="mt-4 text-lg leading-8 text-neutral-700">{copy.subtitle}</p>
        </div>
        <div className="mx-auto mt-12 max-w-3xl space-y-3">
          {copy.items.map((item, index) => (
            <details
              key={item.question}
              className="group rounded-lg border border-neutral-200 bg-white shadow-sm transition hover:border-teal/60 hover:shadow-soft open:border-teal/70 open:bg-white"
              open={index === 0}
            >
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-6 py-5 text-lg font-black text-navy transition hover:text-navy-deep [&::-webkit-details-marker]:hidden">
                <span>{item.question}</span>
                <ChevronDown
                  className="h-5 w-5 flex-none text-coral transition-transform duration-200 group-open:rotate-180"
                  strokeWidth={2.4}
                  aria-hidden="true"
                />
              </summary>
              <div className="px-6 pb-6">
                <p className="border-t border-neutral-100 pt-4 leading-7 text-neutral-700">
                  {item.answer}
                </p>
              </div>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}
