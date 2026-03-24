"use client";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface FAQModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function FAQModal({ isOpen, onClose }: FAQModalProps) {
  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle className="text-2xl font-bold">
            Frequently Asked Questions
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-6 py-4">
          <div>
            <h3 className="text-lg font-semibold mb-2">
              How do you evaluate the government&apos;s progress?
            </h3>
            <div className="text-gray-700 space-y-4">
              <p>We mark commitments as one of four statuses:</p>
              <ul className="list-disc pl-6 space-y-1">
                <li>
                  <strong>Not Started</strong>: we do not yet show meaningful
                  movement on the commitment.
                </li>
                <li>
                  <strong>In Progress</strong>: the page shows concrete movement
                  connected to the commitment.
                </li>
                <li>
                  <strong>Completed</strong>: the commitment appears to have
                  been substantially delivered based on what is shown.
                </li>
                <li>
                  <strong>Broken</strong>: the commitment no longer appears
                  achievable as promised, or later action clearly moved away
                  from it. Some commitments have specific dates attached to
                  them. If that date passes without the commitment being
                  completed, even if the government is still working on it, it
                  is broken.
                </li>
              </ul>
              <p>
                Because we use the Budget as a source of commitments, new
                commitments made in the budget are not shown as having any
                progress at the moment they are added.
              </p>
            </div>
          </div>

          <div>
            <h3 className="text-lg font-semibold mb-2">How does this work?</h3>
            <div className="text-gray-700 space-y-4">
              <p>
                We proactively source public announcements by the government,
                bill status updates as they work their way through parliament,
                regulation changes through the Canada Gazette, and StatsCan data
                releases.
              </p>
              <p>
                When something new happens on those feeds, we use AI to match it
                to commitments and evaluate it against the above rubric.
              </p>
              <p>
                Additionally, on a weekly basis, we have the same AI agent
                proactively search <code>canada.ca</code> domains and{" "}
                <code>*.gc.ca</code> domains to see if we missed anything that
                was not in the feeds we track.
              </p>
            </div>
          </div>

          <div>
            <h3 className="text-lg font-semibold mb-2">
              Why did you build this?
            </h3>
            <p className="text-gray-700">
              We wanted to better understand what is being done in key areas
              that matter to Canadians. We built this tracker to know what key
              commitments have been made, what their progress has been, and how
              they impact outcomes.
            </p>
          </div>

          <div>
            <h3 className="text-lg font-semibold mb-2">
              Where do commitments come from?
            </h3>
            <p className="text-gray-700">
              We have sourced commitments from the Liberal 2025 Election
              Platform, the Speech from the Throne, and the Fall Budget. We are
              exploring sourcing commitments from other public communications.
            </p>
          </div>

          <div>
            <h3 className="text-lg font-semibold mb-2">
              How are statuses and criteria assessments determined?
            </h3>
            <p className="text-gray-700">
              The visible status, criteria assessment, and activity timeline on
              each commitment page are based on the evidence attached to that
              commitment. Our project is open sourced on{" "}
              <a href="https://github.com/BuildCanada" className="underline">
                Github
              </a>
              .
            </p>
          </div>

          <div>
            <h3 className="text-lg font-semibold mb-2">
              How can I contribute?
            </h3>
            <p className="text-gray-700">
              This is a work in progress and we would love help from others.
              Join us on{" "}
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
      </DialogContent>
    </Dialog>
  );
}
