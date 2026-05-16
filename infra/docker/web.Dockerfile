# Next.js frontend
# Build context: repo root.
# Build: docker build -f infra/docker/web.Dockerfile -t vidplatform-web .

FROM node:20-alpine AS deps
WORKDIR /app
COPY apps/web/package.json apps/web/package-lock.json* ./
RUN npm install --no-audit --no-fund

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY apps/web ./
ENV NEXT_TELEMETRY_DISABLED=1
ARG API_BASE_URL=http://api:8000
ENV API_BASE_URL=${API_BASE_URL}
# NEXT_PUBLIC_* vars are inlined into the client bundle at build time, so
# they MUST be present during `next build`. If this is omitted, the browser
# falls back to /api-proxy, which makes the Next.js rewrite buffer SSE
# responses — EventSource connects but never receives events.
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000
COPY --from=builder /app/.next ./.next
RUN mkdir -p ./public
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json
EXPOSE 3000
CMD ["npm", "run", "start"]
