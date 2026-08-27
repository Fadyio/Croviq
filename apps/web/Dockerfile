# Production Dockerfile for Croviq Web
# Stage 1: Build React + Vite production bundle (runs natively on build platform)
FROM --platform=$BUILDPLATFORM node:22-alpine AS builder

WORKDIR /app

# Enable Corepack and activate matching pnpm
RUN corepack enable && corepack prepare pnpm@11.23.0 --activate

# Copy monorepo workspace manifests for layer caching
COPY pnpm-workspace.yaml package.json pnpm-lock.yaml tsconfig.base.json tsconfig.json ./
COPY apps/web/package.json ./apps/web/

# Install dependencies using frozen lockfile
RUN pnpm install --frozen-lockfile

# Copy web application source code
COPY apps/web/ ./apps/web/

# Build configuration arguments for Vite
ARG VITE_FIREBASE_API_KEY=AIzaSyCO3iaT5LpxgAeiJ8oSMgFkXj0zCIIeNM0
ARG VITE_FIREBASE_AUTH_DOMAIN=croviq-506602.firebaseapp.com
ARG VITE_FIREBASE_PROJECT_ID=croviq-506602
ENV VITE_FIREBASE_API_KEY=$VITE_FIREBASE_API_KEY
ENV VITE_FIREBASE_AUTH_DOMAIN=$VITE_FIREBASE_AUTH_DOMAIN
ENV VITE_FIREBASE_PROJECT_ID=$VITE_FIREBASE_PROJECT_ID

# Build production bundle
RUN pnpm --filter @croviq/web build

# -----------------------------------------------------------------------------
# Stage 2: Minimal production HTTP server (Nginx) for target runtime platform
# -----------------------------------------------------------------------------
FROM nginx:1.27-alpine AS runner
ENV PORT=8080


# Remove default Nginx welcome page
RUN rm -rf /usr/share/nginx/html/*

# Copy Nginx configuration template (processed by docker-entrypoint with envsubst)
COPY apps/web/nginx.conf /etc/nginx/templates/default.conf.template

# Copy compiled static assets from builder stage
COPY --from=builder /app/apps/web/dist /usr/share/nginx/html

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
