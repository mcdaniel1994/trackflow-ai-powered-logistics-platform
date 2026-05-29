import type { Translation } from "@/content/types";

type CoverageCopy = Translation["home"]["coverage"];

export function Coverage({ copy }: { copy: CoverageCopy }) {
  return (
    <section id="coverage" className="bg-ivory py-20" aria-labelledby="coverage-heading">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-3xl text-center">
          <h2 id="coverage-heading" className="text-3xl font-black text-navy-deep sm:text-4xl">
            {copy.title}
          </h2>
          <p className="mt-4 text-lg leading-8 text-neutral-700">{copy.subtitle}</p>
        </div>
        <div className="mt-14 grid grid-cols-1 gap-6 md:grid-cols-2">
          {copy.regions.map((region) => (
            <article
              key={region.market}
              tabIndex={0}
              className="rounded-lg border border-mist bg-white p-8 shadow-sm"
            >
              <h3 className="text-2xl font-black text-navy-deep">{region.market}</h3>
              <p className="mt-1 font-bold text-coral">{region.city}</p>
              <dl className="mt-6 space-y-4 text-neutral-700">
                <div>
                  <dt className="font-black text-navy">{copy.warehouseLabel}</dt>
                  <dd className="mt-1">{region.warehouse}</dd>
                </div>
                <div>
                  <dt className="font-black text-navy">{copy.coverageLabel}</dt>
                  <dd className="mt-1">{region.coverage}</dd>
                </div>
                <div>
                  <dt className="font-black text-navy">{copy.carriersLabel}</dt>
                  <dd className="mt-1">{region.carriers}</dd>
                </div>
              </dl>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
