# Outcome Tracker

Source code for the frontend of the [Build Canada Outcome Tracker](https://www.buildcanada.com/tracker). The API repo is [OutcomeTrackerAPI](https://github.com/BuildCanada/OutcomeTrackerAPI).

## Getting Started

- Fork the repo, clone it, and install dependencies:
  ```bash
  git clone https://github.com/BuildCanada/OutcomeTracker.git
  cd OutcomeTracker
  pnpm install
  ```

- Copy .env.example to .env
  - If you're using the production API, set NEXT_PUBLIC_API_URL=https://www.buildcanada.com/tracker/api/v1
  - If you're running the API locally, set NEXT_PUBLIC_API_URL=http://localhost:3000/

- Run the Frontend and enable git hooks
  ```bash
  pnpm turbo
  npx simple-git-hooks
  ```
- 🎉 **Time to explore!** Head over to [http://localhost:4444/tracker](http://localhost:4444/tracker) to see your local instance in action!

## Linting

This project uses ESLint with Next.js configuration. Run linting with:

```bash
pnpm lint          # Check for linting issues
pnpm lint:fix      # Auto-fix auto-fixable issues
```

The linting configuration enforces TypeScript best practices, React rules, and Next.js optimizations while keeping most issues as warnings (temporarily) to avoid blocking development.

## Git Hooks Setup

This project uses `simple-git-hooks` to automatically run linting checks before each commit. To enable in your local environment, run (this is only needed once):

```bash
npx simple-git-hooks
```

The pre-commit hook will run `npm run lint` before each commit. If linting fails, the commit will be blocked until the issues are resolved. Refer to [simple-git-hooks](https://github.com/toplenboren/simple-git-hooks) for more information.

## Metrics

Metrics are scraped using github actions which automatically updates the repo with up to date data. 

## Contributing

We would love to have your help! Please fill in our volunteer [intake form](https://5nneq7.share-na3.hsforms.com/2l9iIH2gFSomphjDe-ci5OQ). 
