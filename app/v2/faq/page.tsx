export default function FAQPage() {
  return (
    <div className="max-w-2xl">
      <h2 className="text-3xl font-bold tracking-tight mb-8">
        Frequently Asked Questions
      </h2>
      <div className="space-y-6">
        <div>
          <h3 className="text-lg font-semibold mb-2">What is this?</h3>
          <p className="text-gray-700">
            We are tracking the implementation of every commitment that the
            Carney government has made. We track bills through parliament,
            official press releases and regulatory changes.
          </p>
        </div>

        <div>
          <h3 className="text-lg font-semibold mb-2">
            Where do commitments come from?
          </h3>
          <p className="text-gray-700">
            Commitments are pulled from the Liberal Party&apos;s 2025 election
            platform and the Speech from the Throne. We show the original text
            and source in each commitment&apos;s details. As new commitments are
            made (e.g. in budgets or ministerial mandate letters), we add them.
          </p>
        </div>

        <div>
          <h3 className="text-lg font-semibold mb-2">
            How do you determine if a commitment is completed?
          </h3>
          <p className="text-gray-700">
            Our standard for completion is generous. Our goal is to hold the
            government accountable to what <em>they</em> said they were going to
            do, not what we hoped for them to do. Many commitments will be
            marked as completed once the budget implementation act receives
            royal assent.
          </p>
        </div>

        <div>
          <h3 className="text-lg font-semibold mb-2">
            How are status assessments made?
          </h3>
          <p className="text-gray-700">
            We use an LLM to assess status based on evidence from official
            government sources, parliamentary records, and regulatory changes.
            Our project is open sourced on{" "}
            <a href="https://github.com/BuildCanada" className="underline">
              Github
            </a>
            .
          </p>
        </div>

        <div>
          <h3 className="text-lg font-semibold mb-2">How can I contribute?</h3>
          <p className="text-gray-700">
            This is a work in progress and we would love help from others. Join
            us on{" "}
            <a href="https://discord.gg/VmbBSXKMve" className="underline">
              Discord
            </a>
            .
          </p>
        </div>

        <div>
          <h3 className="text-lg font-semibold mb-2">
            How can I get in touch?
          </h3>
          <p className="text-gray-700">
            You can reach out to us at{" "}
            <a href="mailto:hi@buildcanada.com" className="underline">
              hi@buildcanada.com
            </a>
          </p>
        </div>
      </div>
    </div>
  );
}
