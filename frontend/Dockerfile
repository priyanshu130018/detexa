# ── Stage 1: Frontend Build Environment ───────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies deterministically via lockfile
COPY package.json package-lock.json ./
RUN npm ci

# Copy application source code
COPY . .

# Build Vite production bundle
ARG VITE_API_BASE_URL=http://localhost:8000/api/v1
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

RUN npm run build

# ── Stage 2: Minimal Production Web Server (Nginx Alpine) ─────────────────────
FROM nginx:1.27-alpine AS runner

# Remove default nginx static assets
RUN rm -rf /usr/share/nginx/html/*

# Copy compiled SPA bundle from builder
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy custom Nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -q --spider http://localhost:80/health || exit 1

CMD ["nginx", "-g", "daemon off;"]
