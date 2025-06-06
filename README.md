# PromiseTracker

A non-partisan platform for tracking government commitments and promise fulfillment in Canada. This system automatically collects evidence from official sources, uses AI to analyze progress, and provides transparent tracking of political promises to Canadian citizens.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Development Setup](#development-setup)
- [Configuration](#configuration)
- [Project Structure](#project-structure)
- [Data Pipeline](#data-pipeline)
- [API Documentation](#api-documentation)
- [Deployment](#deployment)
- [Testing](#testing)
- [Monitoring](#monitoring)
- [Contributing](#contributing)
- [Troubleshooting](#troubleshooting)

## Overview

PromiseTracker provides:

- **Promise Tracking**: Monitor commitments from mandate letters, throne speeches, and election platforms
- **Automated Evidence Collection**: Continuously gather evidence from official sources (bills, news, orders in council)
- **AI-Powered Analysis**: Use LLMs to analyze content and link evidence to promises
- **Public Transparency**: Department-based tracking pages with progress visualization
- **Administrative Tools**: Manage promises, review evidence, and monitor pipeline health

### Key Features

- 🤖 **Intelligent Linking**: Semantic similarity matching + LLM validation for accurate evidence-promise connections
- 🌐 **Bilingual Support**: Full English/French support throughout the platform
- 📊 **Economic Indicators**: Real-time visualization of relevant economic metrics
- 🔄 **Multi-Session Support**: Track promises across parliamentary sessions with department remapping
- 📈 **Progress Scoring**: Automated calculation of promise fulfillment based on linked evidence
- 🔍 **Real-time Monitoring**: Live dashboard for pipeline job status and health metrics

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                           Frontend (Next.js)                         │
├─────────────────────────────────────────────────────────────────────┤
│                          API Routes (Next.js)                        │
├─────────────────────────────────────────────────────────────────────┤
│                      Firebase/Firestore Database                     │
├─────────────────────────────────────────────────────────────────────┤
│                         Data Pipeline (Python)                       │
│  ┌─────────────┐    ┌──────────────┐    ┌────────────────┐        │
│  │  Ingestion  │ => │  Processing  │ => │    Linking     │        │
│  │   Stage     │    │    Stage     │    │     Stage      │        │
│  └─────────────┘    └──────────────┘    └────────────────┘        │
└─────────────────────────────────────────────────────────────────────┘
```

### Tech Stack

- **Frontend**: Next.js 15 (App Router), TypeScript, Tailwind CSS, Radix UI
- **Backend**: Python 3.11, Flask, Gunicorn, Firebase Admin SDK
- **Database**: Cloud Firestore (NoSQL)
- **AI/ML**: Google Gemini (via LangChain), Sentence Transformers
- **Infrastructure**: Google Cloud Run, Cloud Build, Docker
- **Monitoring**: Custom dashboard with real-time metrics

## Quick Start

### Prerequisites

- Node.js 18+ and pnpm
- Python 3.11+
- Firebase project with Firestore enabled
- Google Cloud project (for Gemini API)

### 1. Clone the repository

```bash
git clone https://github.com/BuildCanada/PromiseTracker.git
cd PromiseTracker
```

### 2. Install dependencies

```bash
# Frontend dependencies
pnpm install

# Python dependencies
pip install -r requirements.txt
```

### 3. Set up environment variables

Create `.env.local` in the root directory:

```bash
# Firebase Configuration (Client-side)
NEXT_PUBLIC_FIREBASE_API_KEY=your-api-key
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=your-auth-domain
NEXT_PUBLIC_FIREBASE_PROJECT_ID=promisetrackerapp
NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET=your-storage-bucket
NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=your-sender-id
NEXT_PUBLIC_FIREBASE_APP_ID=your-app-id

# Admin Password (for /admin routes)
NEXT_PUBLIC_ADMIN_PASSWORD=your-secure-password

# Firebase Admin SDK (Server-side)
# Place your service account JSON at ./github-actions-key.json
# Or set GOOGLE_APPLICATION_CREDENTIALS environment variable

# Google AI (Gemini) API Key
GOOGLE_GENAI_API_KEY=your-gemini-api-key
```

### 4. Run the development server

```bash
# Start Next.js development server
pnpm dev

# Or with Turbopack (faster, experimental)
pnpm turbo
```

Visit http://localhost:3000 to see the application.

## Development Setup

### Setting up Firebase

1. Create a Firebase project at https://console.firebase.google.com
2. Enable Firestore Database in production mode
3. Download service account key:
   - Go to Project Settings → Service Accounts
   - Generate new private key
   - Save as `github-actions-key.json` in project root
4. Update Firestore rules:
   ```bash
   firebase deploy --only firestore:rules
   ```

### Setting up Google AI (Gemini)

1. Visit https://makersuite.google.com/app/apikey
2. Create a new API key
3. Add to `.env.local` as `GOOGLE_GENAI_API_KEY`

### Database Schema

See [firestore_schema.md](./firestore_schema.md) for detailed collection structure.

Key collections:
- `promises`: Political commitments to track
- `evidence_items`: Processed evidence from various sources
- `linked_evidence`: Connections between evidence and promises
- `parliament_sessions`: Session metadata and configuration
- `department_config`: Department mapping across sessions

### Running the Data Pipeline

The pipeline consists of three stages that can be run independently:

```bash
# 1. Ingestion - Collect raw data from sources
python -m pipeline.stages.ingestion.canada_news
python -m pipeline.stages.ingestion.legisinfo_bills
python -m pipeline.stages.ingestion.orders_in_council

# 2. Processing - Transform raw data into evidence items
python -m pipeline.stages.processing.canada_news_processor
python -m pipeline.stages.processing.legisinfo_processor

# 3. Linking - Connect evidence to promises
python -m pipeline.stages.linking.semantic_evidence_linker
python -m pipeline.stages.linking.llm_evidence_validator
```

Or use the orchestrator for automated execution:

```bash
python -m pipeline.orchestrator
```

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `NEXT_PUBLIC_FIREBASE_*` | Firebase client configuration | Yes |
| `NEXT_PUBLIC_ADMIN_PASSWORD` | Password for admin interface | Yes |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to Firebase service account | Yes* |
| `GOOGLE_GENAI_API_KEY` | Google AI API key for LLM processing | Yes |
| `PORT` | Server port (default: 3000) | No |

*Can alternatively place `github-actions-key.json` in project root

### Pipeline Configuration

Edit `pipeline/config/jobs.yaml` to configure:
- Job schedules and dependencies
- Processing parameters
- Resource limits
- Retry policies

## Project Structure

```
PromiseTracker/
├── app/                    # Next.js app directory
│   ├── [lang]/            # Internationalized public pages
│   ├── admin/             # Protected admin interface
│   └── api/               # API routes
├── components/            # React components
│   ├── charts/           # Data visualization components
│   └── ui/               # Radix UI components
├── pipeline/              # Python data pipeline
│   ├── stages/           # Pipeline stages (ingestion, processing, linking)
│   ├── core/             # Core pipeline infrastructure
│   └── config/           # Pipeline configuration
├── scripts/               # Utility and migration scripts
├── lib/                   # Shared utilities
├── public/                # Static assets
└── docs/                  # Documentation
```

## Data Pipeline

### Overview

The pipeline automatically:
1. **Ingests** data from multiple sources (RSS feeds, APIs, web scraping)
2. **Processes** raw data using LLMs to extract structured evidence
3. **Links** evidence to promises using semantic similarity and LLM validation

### Data Sources

- **Canada News**: RSS feeds from government departments
- **LEGISinfo**: Parliamentary bills via official API
- **Orders in Council**: Executive orders via web scraping
- **Canada Gazette**: Regulatory changes via RSS feeds

### Pipeline Stages

#### 1. Ingestion Stage
Collects raw data and stores in source-specific collections:
- Handles RSS parsing, API calls, web scraping
- Implements rate limiting and error handling
- Stores raw data for processing

#### 2. Processing Stage
Transforms raw data into standardized evidence items:
- Uses Gemini LLM for content analysis
- Extracts titles, summaries, key dates
- Categorizes evidence types
- Handles bilingual content

#### 3. Linking Stage
Connects evidence to relevant promises:
- Semantic embedding generation
- Cosine similarity matching
- LLM validation of matches
- Progress score calculation

### Running Pipeline Jobs

```bash
# Run specific job
python -m pipeline.stages.ingestion.canada_news --limit 10

# Run with custom session
python -m pipeline.stages.linking.semantic_evidence_linker --session_id 44

# Test mode (uses test collections)
python -m pipeline.stages.processing.legisinfo_processor --test
```

## API Documentation

### Public Endpoints

#### GET /api/minister-info
Fetches minister information from official government API.

Query params:
- `lang`: Language (en/fr)

#### GET /api/evidence
Retrieves evidence items with filtering.

Query params:
- `promiseId`: Filter by promise
- `department`: Filter by department
- `type`: Evidence type filter

### Admin Endpoints (Password Protected)

#### POST /api/admin/auth
Authenticates admin access.

Body:
```json
{
  "password": "admin-password"
}
```

#### GET/POST /api/admin/promises
Manage promises (CRUD operations).

#### POST /api/admin/evidence
Submit manual evidence entries.

#### GET /api/admin/current-session
Get current parliamentary session info.

## Deployment

### Local Development

```bash
# Frontend only
pnpm dev

# Run Storybook for component development
pnpm storybook

# Run pipeline locally
python -m pipeline.orchestrator
```

### Production Deployment (Google Cloud Run)

1. **Automatic Deployment** (via Cloud Build):
   - Push to `main` branch triggers automatic build and deploy
   - Configured in `cloudbuild.yaml`

2. **Manual Deployment**:
   ```bash
   # Build and push Docker image
   docker build -t gcr.io/promisetrackerapp/promise-tracker .
   docker push gcr.io/promisetrackerapp/promise-tracker

   # Deploy to Cloud Run
   gcloud run deploy promise-tracker \
     --image gcr.io/promisetrackerapp/promise-tracker \
     --platform managed \
     --region northamerica-northeast2 \
     --allow-unauthenticated
   ```

3. **Environment Configuration**:
   - Set all environment variables in Cloud Run
   - Upload service account key securely
   - Configure memory (2GB) and CPU (2) for LLM processing

### Infrastructure as Code

Basic Terraform configuration is provided in `infrastructure/` for:
- Cloud Run service
- Firestore indexes
- Monitoring alerts

## Testing

### Frontend Tests

```bash
# Run unit tests
pnpm test

# Run with coverage
pnpm test:coverage

# Component testing with Storybook
pnpm storybook
```

### Pipeline Tests

```bash
# Test individual processors
python -m pipeline.testing.test_legisinfo_pipeline

# Validate pipeline configuration
python -m pipeline.testing.pipeline_validation

# Test evidence linking accuracy
python -m pipeline.testing.test_progress_scorer
```

### Integration Tests

```bash
# Test end-to-end pipeline flow
python scripts/testing/test_end_to_end_pipeline.py

# Test Firebase connectivity
python scripts/test_firebase_connection.py
```

## Monitoring

### Admin Dashboard

Access at `/admin/monitoring` (password protected) to view:
- Pipeline job status and health
- RSS feed monitoring metrics
- Error logs and alerts
- Performance trends

### Key Metrics

- **Job Success Rate**: Percentage of successful pipeline runs
- **Processing Time**: Average time per evidence item
- **Link Accuracy**: Validated evidence-promise matches
- **RSS Feed Health**: Feed availability and response times

### Alerting

The system automatically tracks:
- Consecutive job failures (alerts after 3)
- RSS feed downtime
- Processing errors
- Memory/timeout issues

## Contributing

### Development Workflow

1. Create a feature branch from `main`
2. Make changes following existing code style
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit PR with clear description

### Code Style

- **TypeScript**: Follow Next.js conventions, use strict typing
- **Python**: Follow PEP 8, use type hints
- **Components**: Use functional components with TypeScript
- **Commits**: Use conventional commits (feat:, fix:, docs:, etc.)

### Adding New Data Sources

1. Create ingestion module in `pipeline/stages/ingestion/`
2. Create processor in `pipeline/stages/processing/`
3. Add configuration to `pipeline/config/jobs.yaml`
4. Add tests and documentation

## Troubleshooting

### Common Issues

**Firebase Connection Errors**
- Verify service account key exists at `./github-actions-key.json`
- Check Firebase project ID matches in `.env.local`
- Ensure Firestore is enabled in Firebase console

**LLM API Errors**
- Verify `GOOGLE_GENAI_API_KEY` is set correctly
- Check API quotas in Google Cloud Console
- Monitor rate limiting (default: 60 requests/minute)

**Pipeline Memory Issues**
- Reduce batch sizes in job configuration
- Increase Cloud Run memory allocation
- Enable swap for local development

**Build Failures**
- Clear Next.js cache: `rm -rf .next`
- Reinstall dependencies: `rm -rf node_modules && pnpm install`
- Check Node.js version (requires 18+)

### Debug Mode

Enable detailed logging:

```bash
# Frontend debugging
DEBUG=* pnpm dev

# Pipeline debugging
export PROMISETRACKER_DEBUG=true
python -m pipeline.orchestrator
```

### Getting Help

- Check existing issues at https://github.com/BuildCanada/PromiseTracker/issues
- Review logs in `/debug_output/` directory
- Contact maintainers for infrastructure access

## License

This project is maintained by Build Canada. For licensing information, please contact the maintainers.

---

Built with 🇨🇦 to promote government transparency and accountability.