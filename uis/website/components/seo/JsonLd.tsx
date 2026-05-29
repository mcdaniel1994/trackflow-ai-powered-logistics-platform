import type { JsonLdSchema } from "@/content/types";

interface JsonLdProps<TSchema extends JsonLdSchema> {
  data: TSchema;
}

export function JsonLd<TSchema extends JsonLdSchema>({ data }: JsonLdProps<TSchema>) {
  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{
        __html: JSON.stringify(data).replace(/</g, "\\u003c"),
      }}
    />
  );
}
