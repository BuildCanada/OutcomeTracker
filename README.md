<div align="center">

# 🏗️ Build Canada 🇨🇦

### Outcome Tracker
*Transparency in Government Promises*

<br/>

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Next.js](https://img.shields.io/badge/Next.js-15.2.4-black)](https://nextjs.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.x-blue)](https://www.typescriptlang.org)

</div>

---

A non-partisan platform for tracking the progress of key commitments made during the 45th Parliament of Canada. This application provides transparency and accountability by monitoring government promises across all departments.

## 🎯 Overview

The Outcome Tracker monitors promises from:
- 2021 Mandate Letters
- 2025 Liberal Party Platform
- Throne speeches
- Major policy announcements

Each promise is tracked with:
- Progress scores and summaries
- Evidence of actions taken
- Timeline of key events
- Impact assessments
- Department assignments

## 🚀 Quick Start

```bash
# Clone the repository
git clone https://github.com/BuildCanada/OutcomeTracker.git
cd OutcomeTracker

# Install dependencies
pnpm install

# Set up environment variables
# Create a .env file in the root directory with:
echo "NEXT_PUBLIC_API_URL=https://www.buildcanada.com/tracker/api/v1" > .env

# Run development server
pnpm turbo
```

Visit [http://localhost:4444/tracker](http://localhost:4444/tracker) to see your local instance.

## 📚 Documentation

Detailed documentation is available in the [`/docs`](./docs) directory:

- [**Architecture Overview**](./docs/ARCHITECTURE.md) - System design and technical stack
- [**Development Guide**](./docs/DEVELOPMENT.md) - Setup, coding standards, and workflows
- [**Data & Metrics**](./docs/DATA_METRICS.md) - Data sources and metric calculations
- [**Components Guide**](./docs/COMPONENTS.md) - UI component documentation
- [**API Integration**](./docs/API_INTEGRATION.md) - Backend API usage
- [**Deployment**](./docs/DEPLOYMENT.md) - Production deployment guide

## 🏗️ Tech Stack

- **Frontend**: Next.js 15.2.4 with TypeScript
- **Styling**: Tailwind CSS with shadcn/ui components
- **Charts**: Chart.js with react-chartjs-2
- **State Management**: SWR for data fetching
- **Testing**: Vitest with Storybook
- **Analytics**: Simple Analytics

## 📊 Key Features

- **Department Dashboard**: Track promises by government department
- **Progress Visualization**: Real-time progress scores and timelines
- **Economic Metrics**: Interactive charts for GDP, housing, population, and more
- **Evidence Tracking**: Links to bills, news, and official documents
- **Responsive Design**: Mobile-first approach with modern UI

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](./docs/CONTRIBUTING.md) for details.

### Getting Involved
1. Fill out our [volunteer intake form](https://5nneq7.share-na3.hsforms.com/2l9iIH2gFSomphjDe-ci5OQ)
2. Join our community discussions
3. Check open issues for ways to help

## 📄 License

This project is open source and available under the [MIT License](LICENSE).

## 🔗 Related Resources

- **Production Site**: [buildcanada.com/tracker](https://www.buildcanada.com/tracker)
- **API Repository**: [OutcomeTrackerAPI](https://github.com/BuildCanada/OutcomeTrackerAPI)
- **Main Website**: [buildcanada.com](https://www.buildcanada.com)

---

<div align="center">
Built with ❤️ by Build Canada volunteers 🏗️🇨🇦
</div>
