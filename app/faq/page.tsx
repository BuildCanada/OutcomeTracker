export default function FAQPage() {
  return (
    <div className="max-w-2xl">
      <h2 className="text-3xl font-bold tracking-tight mb-8">
        Frequently Asked Questions
      </h2>
      <div className="space-y-6">
        <div>
          <h3 className="text-lg font-semibold mb-2">
            Why did you build this?
          </h3>
          <p className="text-gray-700">
            We wanted to better understand what is being done in key areas that
            matter to Canadians. We built this tracker to know what key
            commitments have been made, what their progress has been, and how
            they impact outcomes.
          </p>
        </div>

        <div>
          <h3 className="text-lg font-semibold mb-2">
            Where do commitments come from?
          </h3>
          <p className="text-gray-700">
            We have pulled commitments from the Liberal Party&apos;s platform.
            We show the original text and the source in each commitment&apos;s
            details. As new commitments are made, we will add these in.
          </p>
        </div>

        <div>
          <h3 className="text-lg font-semibold mb-2">
            How are the progress, impact, and alignment scores calculated?
          </h3>
          <p className="text-gray-700">
            We use an LLM to score each of these. Our project is open sourced on{" "}
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
