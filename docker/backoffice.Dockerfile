FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
COPY packages/shared/package.json packages/shared/package.json
COPY uis/backoffice/package.json uis/backoffice/package.json
RUN npm ci

FROM deps AS build
COPY packages/shared packages/shared
COPY uis/backoffice uis/backoffice
RUN npm run build --workspace trackflow-backoffice

FROM node:22-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production PORT=3000 HOSTNAME=0.0.0.0
COPY --from=build --chown=node:node /app/uis/backoffice/.next/standalone ./
COPY --from=build --chown=node:node /app/uis/backoffice/.next/static ./uis/backoffice/.next/static
COPY --from=build --chown=node:node /app/uis/backoffice/public ./uis/backoffice/public
USER node
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD ["wget", "-qO-", "http://127.0.0.1:3000/api/health"]
CMD ["node", "uis/backoffice/server.js"]
