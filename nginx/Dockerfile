# syntax=docker/dockerfile:1
# Ingress image: builds the React SPA and serves it (plus proxy config) via nginx.
# Build context is the repository root so both the frontend sources and this
# nginx config are reachable.

# ---------------------------------------------------------------------------
# Stage 1: build the static SPA assets from services/frontend.
# ---------------------------------------------------------------------------
FROM node:22-alpine AS build
WORKDIR /app

# Install dependencies against the lockfile for reproducible builds.
COPY services/frontend/package.json services/frontend/package-lock.json* ./
RUN npm ci

# Build the production bundle into /app/dist.
COPY services/frontend/ ./
RUN npm run build

# ---------------------------------------------------------------------------
# Stage 2: nginx serving the compiled assets + ingress routing.
# ---------------------------------------------------------------------------
FROM nginx:1.27-alpine AS runtime

# Replace the stock site config with the ingress config.
RUN rm -f /etc/nginx/conf.d/default.conf
COPY nginx/default.conf /etc/nginx/conf.d/default.conf

# Ship the compiled static assets.
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://127.0.0.1/healthz || exit 1

CMD ["nginx", "-g", "daemon off;"]
