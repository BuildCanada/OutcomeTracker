"use client";
import { useState } from "react";

import FAQModal from "@/components/FAQModal";

export const Sidebar = ({ pageTitle }: { pageTitle: string }) => {
  const [isFAQModalOpen, setIsFAQModalOpen] = useState(false);

  return (
    <div className="col-span-1">
      <div className="mb-6">
        <a href="/" className="block">
          <img
            src="https://cdn.prod.website-files.com/679d23fc682f2bf860558c9a/679d23fc682f2bf860558cc6_build_canada-wordmark.svg"
            alt="Build Canada"
            className="bg-[#932f2f] h-12 w-auto p-3"
          />
        </a>
      </div>
      <h1 className="text-4xl lg:text-5xl font-bold mb-8">{pageTitle}</h1>
      <div className="mb-8">
        <p className="text-gray-900 mb-6">
          A non-partisan platform tracking progress of key commitments during
          the 45th Parliament of Canada.
        </p>
        <button
          onClick={() => setIsFAQModalOpen(true)}
          className="font-mono text-sm text-[#8b2332] hover:text-[#721c28] transition-colors"
        >
          FAQ
        </button>
      </div>
      <FAQModal
        isOpen={isFAQModalOpen}
        onClose={() => setIsFAQModalOpen(false)}
      />
    </div>
  );
};
