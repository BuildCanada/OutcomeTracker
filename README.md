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

- Run the Frontend
  ```bash
  pnpm turbo
  ```

## Metrics

Metrics are scraped using github actions which automatically updates the repo with up to date data. 

## Contributing

We would love to have your help! Please fill in our vounteer intake form 
