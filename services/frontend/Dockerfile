# ┌──────────────────────────────────────────────────────────────────────────┐
# │ milvus_station                                                           │
# │ Author  : Chun Kang <kurapa@kurapa.com>                                  │
# │ Created : 2026-07-03  (PDT, UTC-07:00)                                   │
# └──────────────────────────────────────────────────────────────────────────┘

# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Stage 1: build the static SPA assets
# ---------------------------------------------------------------------------
FROM node:22-alpine AS build
WORKDIR /app

# Install dependencies against the lockfile for reproducible builds.
COPY package.json package-lock.json* ./
RUN npm ci

# Build the production bundle into /app/dist.
COPY . .
RUN npm run build

# ---------------------------------------------------------------------------
# Stage 2 (export): a minimal stage whose only content is the built assets.
# The root nginx service (built separately by devops) can copy them out via:
#   COPY --from=<frontend-image> /dist /usr/share/nginx/html
# ---------------------------------------------------------------------------
FROM scratch AS assets
COPY --from=build /app/dist /dist

# ---------------------------------------------------------------------------
# Stage 3 (default/runtime): self-contained nginx image serving the SPA.
# Falls back to index.html for client-side routing (e.g. /mysql).
# ---------------------------------------------------------------------------
FROM nginx:1.27-alpine AS runtime

# Replace the default site config with the SPA-aware one.
RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/app.conf

# Ship the compiled static assets.
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://127.0.0.1/healthz || exit 1

CMD ["nginx", "-g", "daemon off;"]
