# Deployment Guide

## Overview

The Build Canada Outcome Tracker is a Next.js application that can be deployed to various platforms. This guide covers deployment options, configuration, and best practices.

## Prerequisites

- Node.js 18.x or higher
- pnpm package manager
- Access to deployment platform
- Environment variables configured

## Build Process

### Local Build
```bash
# Install dependencies
pnpm install

# Build for production
pnpm build

# Test production build locally
pnpm start
```

### Build Output
```
.next/              # Next.js build output
├── cache/          # Build cache
├── server/         # Server-side code
├── static/         # Static assets
└── BUILD_ID        # Unique build identifier
```

## Deployment Platforms

### 1. Vercel (Recommended)

Vercel is the native platform for Next.js applications.

**Automatic Deployment:**
1. Connect GitHub repository to Vercel
2. Configure environment variables
3. Deploy with automatic CI/CD

**Manual Deployment:**
```bash
# Install Vercel CLI
npm i -g vercel

# Deploy
vercel --prod
```

**vercel.json Configuration:**
```json
{
  "framework": "nextjs",
  "buildCommand": "pnpm build",
  "installCommand": "pnpm install",
  "regions": ["iad1"],
  "env": {
    "NEXT_PUBLIC_API_URL": "@api_url"
  }
}
```

### 2. Netlify

**netlify.toml Configuration:**
```toml
[build]
  command = "pnpm build"
  publish = ".next"

[build.environment]
  NEXT_PUBLIC_API_URL = "https://www.buildcanada.com/tracker/api/v1"

[[plugins]]
  package = "@netlify/plugin-nextjs"

[[redirects]]
  from = "/api/*"
  to = "https://www.buildcanada.com/tracker/api/:splat"
  status = 200
```

### 3. Docker Deployment

**Dockerfile:**
```dockerfile
# Build stage
FROM node:18-alpine AS builder
RUN apk add --no-cache libc6-compat
WORKDIR /app

# Install pnpm
RUN npm install -g pnpm

# Copy package files
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

# Copy source code
COPY . .

# Build application
ENV NEXT_TELEMETRY_DISABLED 1
RUN pnpm build

# Production stage
FROM node:18-alpine AS runner
WORKDIR /app

ENV NODE_ENV production
ENV NEXT_TELEMETRY_DISABLED 1

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# Copy built application
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

ENV PORT 3000

CMD ["node", "server.js"]
```

**docker-compose.yml:**
```yaml
version: '3.8'

services:
  web:
    build: .
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=https://www.buildcanada.com/tracker/api/v1
    restart: unless-stopped
```

### 4. Traditional Server (PM2)

**ecosystem.config.js:**
```javascript
module.exports = {
  apps: [{
    name: 'outcome-tracker',
    script: 'npm',
    args: 'start',
    env: {
      NODE_ENV: 'production',
      PORT: 3000,
      NEXT_PUBLIC_API_URL: 'https://www.buildcanada.com/tracker/api/v1'
    },
    instances: 'max',
    exec_mode: 'cluster',
    autorestart: true,
    watch: false,
    max_memory_restart: '1G'
  }]
}
```

**Deployment Steps:**
```bash
# On server
git clone https://github.com/BuildCanada/OutcomeTracker.git
cd OutcomeTracker
pnpm install
pnpm build

# Start with PM2
pm2 start ecosystem.config.js
pm2 save
pm2 startup
```

## Environment Variables

### Required Variables
```env
# API Configuration
NEXT_PUBLIC_API_URL=https://www.buildcanada.com/tracker/api/v1

# Optional Analytics
NEXT_PUBLIC_SIMPLE_ANALYTICS_ID=your-analytics-id
NEXT_PUBLIC_ENABLE_ANALYTICS=true
```

### Platform-Specific Setup

**Vercel:**
- Set in project settings dashboard
- Use secrets for sensitive values

**Netlify:**
- Configure in site settings
- Use environment variables UI

**Docker:**
- Use `.env` file or Docker secrets
- Pass via docker-compose or CLI

## Performance Optimization

### 1. Next.js Optimization
```javascript
// next.config.mjs
const nextConfig = {
  output: 'standalone',
  compress: true,
  poweredByHeader: false,
  reactStrictMode: true,
  images: {
    domains: ['buildcanada.com'],
    formats: ['image/avif', 'image/webp'],
  },
  experimental: {
    optimizeCss: true,
  },
};
```

### 2. CDN Configuration

**CloudFlare:**
```
Page Rules:
- /tracker/api/* → Cache Level: Bypass
- /_next/static/* → Cache Level: Cache Everything, Edge Cache TTL: 1 month
- /fonts/* → Cache Level: Cache Everything, Edge Cache TTL: 1 year
```

**Cache Headers:**
```javascript
// next.config.mjs
async headers() {
  return [
    {
      source: '/:all*(svg|jpg|jpeg|png|gif|ico|webp|avif)',
      headers: [
        {
          key: 'Cache-Control',
          value: 'public, max-age=31536000, immutable',
        },
      ],
    },
    {
      source: '/_next/static/:path*',
      headers: [
        {
          key: 'Cache-Control',
          value: 'public, max-age=31536000, immutable',
        },
      ],
    },
  ];
}
```

### 3. Database Optimization
- Enable SWR caching
- Implement API response caching
- Use CDN for static metric files

## Monitoring & Logging

### 1. Application Monitoring

**Sentry Integration:**
```javascript
// sentry.client.config.js
import * as Sentry from '@sentry/nextjs';

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  environment: process.env.NODE_ENV,
  tracesSampleRate: 0.1,
  debug: false,
});
```

### 2. Performance Monitoring

**Web Vitals:**
```javascript
// app/layout.tsx
export function reportWebVitals(metric) {
  if (metric.label === 'web-vital') {
    console.log(metric);
    // Send to analytics
  }
}
```

### 3. Error Tracking
```javascript
// lib/error-tracking.ts
export function trackError(error: Error, context?: any) {
  console.error('Application Error:', error);
  
  if (process.env.NODE_ENV === 'production') {
    // Send to error tracking service
    Sentry.captureException(error, { extra: context });
  }
}
```

## Security Checklist

### Headers Configuration
```javascript
// next.config.mjs
async headers() {
  return [
    {
      source: '/:path*',
      headers: [
        {
          key: 'X-DNS-Prefetch-Control',
          value: 'on'
        },
        {
          key: 'X-XSS-Protection',
          value: '1; mode=block'
        },
        {
          key: 'X-Frame-Options',
          value: 'SAMEORIGIN'
        },
        {
          key: 'X-Content-Type-Options',
          value: 'nosniff'
        },
        {
          key: 'Referrer-Policy',
          value: 'origin-when-cross-origin'
        },
        {
          key: 'Permissions-Policy',
          value: 'camera=(), microphone=(), geolocation=()'
        }
      ]
    }
  ];
}
```

### Content Security Policy
```javascript
const ContentSecurityPolicy = `
  default-src 'self';
  script-src 'self' 'unsafe-eval' 'unsafe-inline' *.buildcanada.com;
  style-src 'self' 'unsafe-inline';
  img-src 'self' blob: data: *.buildcanada.com;
  font-src 'self';
  connect-src 'self' *.buildcanada.com;
`;
```

## Deployment Checklist

### Pre-Deployment
- [ ] Run production build locally
- [ ] Test all environment variables
- [ ] Verify API connectivity
- [ ] Check TypeScript errors
- [ ] Run linting checks
- [ ] Test on multiple browsers

### Deployment
- [ ] Set environment variables
- [ ] Configure domain/subdomain
- [ ] Set up SSL certificates
- [ ] Configure CDN if applicable
- [ ] Set up monitoring
- [ ] Configure backups

### Post-Deployment
- [ ] Verify all pages load
- [ ] Test API endpoints
- [ ] Check analytics tracking
- [ ] Monitor error logs
- [ ] Test performance metrics
- [ ] Verify SEO tags

## Rollback Strategy

### Vercel
```bash
# List deployments
vercel ls

# Rollback to previous
vercel rollback [deployment-url]
```

### Docker
```bash
# Tag releases
docker tag outcome-tracker:latest outcome-tracker:backup
docker tag outcome-tracker:new outcome-tracker:latest

# Rollback
docker tag outcome-tracker:backup outcome-tracker:latest
docker-compose up -d
```

### Git-based
```bash
# Tag releases
git tag -a v1.0.0 -m "Release version 1.0.0"
git push origin v1.0.0

# Rollback
git checkout v0.9.0
pnpm install
pnpm build
pm2 restart outcome-tracker
```

## Troubleshooting

### Common Issues

1. **Build Failures**
   ```bash
   # Clear cache
   rm -rf .next node_modules
   pnpm install
   pnpm build
   ```

2. **API Connection Issues**
   - Verify NEXT_PUBLIC_API_URL
   - Check CORS settings
   - Test API endpoints directly

3. **Memory Issues**
   ```javascript
   // Increase Node memory
   NODE_OPTIONS="--max-old-space-size=4096" pnpm build
   ```

4. **Port Conflicts**
   ```bash
   # Change port
   PORT=3001 pnpm start
   ``` 