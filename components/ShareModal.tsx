"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/use-toast";
import { CopyIcon } from "lucide-react";

interface ShareModalProps {
  isOpen: boolean;
  onClose: () => void;
  shareUrl: string;
  promiseTitle: string;
}

export default function ShareModal({
  isOpen,
  onClose,
  shareUrl,
  promiseTitle,
}: ShareModalProps) {
  const [isCopying, setIsCopying] = useState(false);
  const { toast } = useToast();

  // Create a short snippet of the promise title for social media
  const promiseSnippet =
    promiseTitle.length > 100
      ? promiseTitle.substring(0, 97) + "..."
      : promiseTitle;

  const handleCopyLink = async () => {
    if (!shareUrl) return;

    setIsCopying(true);
    try {
      await navigator.clipboard.writeText(shareUrl);
      toast({
        title: "Link copied!",
        description: "The promise link has been copied to your clipboard.",
      });
    } catch (error) {
      console.error("Failed to copy link:", error);
      toast({
        title: "Copy failed",
        description: "Failed to copy the link. Please try again.",
        variant: "destructive",
      });
    } finally {
      setIsCopying(false);
    }
  };

  const handleSocialShare = (platform: "twitter" | "facebook" | "linkedin") => {
    if (!shareUrl) return;

    const encodedUrl = encodeURIComponent(shareUrl);
    const encodedText = encodeURIComponent(
      `Check out this promise: ${promiseSnippet}`,
    );

    let shareLink = "";

    switch (platform) {
      case "twitter":
        shareLink = `https://twitter.com/intent/tweet?url=${encodedUrl}&text=${encodedText}`;
        break;
      case "facebook":
        // Facebook sharing - use the sharer.php endpoint with URL and quote parameter for text
        shareLink = `https://www.facebook.com/sharer/sharer.php?u=${encodedUrl}&quote=${encodedText}`;
        break;
      case "linkedin": {
        // LinkedIn sharing - use the sharing/share-offsite endpoint with title and summary
        const encodedTitle = encodeURIComponent(
          `Government Promise: ${promiseSnippet}`,
        );
        shareLink = `https://www.linkedin.com/sharing/share-offsite/?url=${encodedUrl}&title=${encodedTitle}&summary=${encodedText}`;
        break;
      }
    }

    if (shareLink) {
      window.open(shareLink, "_blank", "noopener,noreferrer");
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader className="relative">
          <DialogTitle className="text-lg font-semibold text-center">
            Share to
          </DialogTitle>
          <DialogDescription className="text-sm text-gray-600 text-center">
            Share this promise on social media or copy the link
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 pt-2">
          {/* Social Media Buttons */}
          <div className="grid grid-cols-3 gap-4">
            {/* Twitter/X Button */}
            <button
              onClick={() => handleSocialShare("twitter")}
              className="flex flex-col items-center p-6 space-y-3 hover:bg-gray-50 rounded-lg transition-colors"
            >
              <div className="w-12 h-12 bg-black rounded-full flex items-center justify-center">
                <svg
                  className="w-6 h-6 text-white"
                  viewBox="0 0 24 24"
                  fill="currentColor"
                >
                  <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
                </svg>
              </div>
              <span className="text-sm font-medium">X</span>
            </button>

            {/* Facebook Button */}
            <button
              onClick={() => handleSocialShare("facebook")}
              className="flex flex-col items-center p-6 space-y-3 hover:bg-gray-50 rounded-lg transition-colors"
            >
              <div className="w-12 h-12 bg-[#1877F2] rounded-full flex items-center justify-center">
                <svg
                  className="w-6 h-6 text-white"
                  viewBox="0 0 24 24"
                  fill="currentColor"
                >
                  <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z" />
                </svg>
              </div>
              <span className="text-sm font-medium">Facebook</span>
            </button>

            {/* LinkedIn Button */}
            <button
              onClick={() => handleSocialShare("linkedin")}
              className="flex flex-col items-center p-6 space-y-3 hover:bg-gray-50 rounded-lg transition-colors"
            >
              <div className="w-12 h-12 bg-[#0A66C2] rounded-full flex items-center justify-center">
                <svg
                  className="w-6 h-6 text-white"
                  viewBox="0 0 24 24"
                  fill="currentColor"
                >
                  <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
                </svg>
              </div>
              <span className="text-sm font-medium">LinkedIn</span>
            </button>
          </div>

          {/* Copy Link Section */}
          <div className="space-y-3">
            <h3 className="text-sm font-medium text-gray-700">Copy link</h3>
            <div className="flex space-x-2">
              <Input
                value={shareUrl}
                readOnly
                className="flex-1 text-sm bg-gray-50 border-gray-200"
                placeholder="Loading..."
              />
              <Button
                onClick={handleCopyLink}
                disabled={isCopying || !shareUrl}
                variant="outline"
                size="sm"
                className="flex-shrink-0 px-3"
              >
                <CopyIcon className="w-4 h-4" />
              </Button>
            </div>
          </div>

          {/* Share This Button */}
          <div className="flex justify-center pt-2">
            <Button
              onClick={onClose}
              className="w-full bg-gray-100 hover:bg-gray-200 text-gray-700 border-0"
              variant="outline"
            >
              Close
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
