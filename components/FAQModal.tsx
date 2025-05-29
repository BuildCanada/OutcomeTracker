"use client";

import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";

interface FAQModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function FAQModal({ isOpen, onClose }: FAQModalProps) {
  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle className="text-2xl font-bold">Frequently Asked Questions</DialogTitle>
        </DialogHeader>
        <div className="space-y-6 py-4">
          <div>
            <h3 className="text-lg font-semibold mb-2">Why did you build this?</h3>
            <p className="text-gray-700">
              We want to better understand what is being done in key areas that matter to Canadians like us. We want to understand what the government is promising, what progress has been made, and, most importantly, what the outcomes have been.
            </p>
          </div>
          
          <div>
            <h3 className="text-lg font-semibold mb-2">Where do commitments come from?</h3>
            <p className="text-gray-700">
              We have pulled commitments from the Liberal Party's platform. We show the original text of the commitment and its source in each commitment's details. As new commitments are made we will add these in.
            </p>
          </div>

          <div>
            <h3 className="text-lg font-semibold mb-2">How are the progress, impact, and alignment scores calculated?</h3>
            <p className="text-gray-700">
              We use an LLM to score each of these. We are planning to open source our prompts soon.
            </p>
          </div>

          <div>
            <h3 className="text-lg font-semibold mb-2">How can I contribute?</h3>
            <p className="text-gray-700">
              This is a work in progress and we would love help from others. We are planning to open source this project in the near future so that anyone can contribute.
            </p>
          </div>

          <div>
            <h3 className="text-lg font-semibold mb-2">How can I get in contact with you?</h3>
            <p className="text-gray-700">
              You can reach out to us at <a href="mailto:hi@buildcanada.com">hi@buildcanada.com</a>
            </p>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
} 