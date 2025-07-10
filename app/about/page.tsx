export default function AboutPage() {
  return (
    <main className="container mx-auto py-8 px-4">
      <div className="max-w-3xl mx-auto">
        <h1 className="text-4xl font-bold mb-6">About Canada&apos;s Promise Tracker</h1>

        <div className="prose dark:prose-invert max-w-none">
          <p>
            Canada&apos;s Promise Tracker is a non-partisan tool designed to help Canadians monitor the progress of the
            federal government&apos;s promises. Our goal is to promote transparency and accountability in government by
            providing clear, accessible information about what the government has committed to do and how those
            commitments are being fulfilled.
          </p>

          <h2>How We Track Promises</h2>
          <p>
            We track promises made in official government documents, campaign platforms, throne speeches, and major
            policy announcements. For each promise, we monitor:
          </p>
          <ul>
            <li>The specific commitment made</li>
            <li>Actions taken to fulfill the promise</li>
            <li>Current status (Not Started, In Progress, Partially Complete, or Complete)</li>
            <li>Timeline of key events related to the promise</li>
          </ul>

          <h2>Our Methodology</h2>
          <p>
            Our team of researchers and policy analysts reviews government announcements, legislation, regulations, and
            other official actions to determine the status of each promise. We use a consistent methodology to evaluate
            progress:
          </p>
          <ul>
            <li>
              <strong>Not Started:</strong> No significant action has been taken to fulfill the promise.
            </li>
            <li>
              <strong>In Progress:</strong> The government has taken concrete steps toward fulfilling the promise, such
              as introducing legislation or allocating funding.
            </li>
            <li>
              <strong>Partially Complete:</strong> The government has fulfilled some aspects of the promise but not
              others, or has made significant progress but has not fully completed the commitment.
            </li>
            <li>
              <strong>Complete:</strong> The government has fully fulfilled the promise as stated.
            </li>
          </ul>

          <h2>About This Demo</h2>
          <p>
            This is a demonstration application showing how the Promise Tracker would work. In a production environment,
            this would be connected to a database with real-time updates on the status of government promises.
          </p>

          <p>
            For the purposes of this demo, promise statuses are randomly generated and do not reflect actual government
            progress.
          </p>
        </div>
      </div>
    </main>
  )
}
