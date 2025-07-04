import { Menu } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";

export default function Header() {
  return (
    <header className="border-b-2 border-black font-founders bg-background sticky top-0 z-50">
      <div className="mx-auto grid grid-cols-[160px_1fr] min-h-[72px]">
        <div className="bg-[#932f2f] flex items-center justify-center">
          <a href="/" className="block">
            <img
              src="https://cdn.prod.website-files.com/679d23fc682f2bf860558c9a/679d23fc682f2bf860558cc6_build_canada-wordmark.svg"
              alt="Build Canada"
              className="w-[110px] h-auto p-2"
            />
          </a>
        </div>
        {/* Desktop Navigation */}
        <div className="flex items-center justify-end h-full">
          <nav className="hidden md:flex w-full h-full items-stretch">
            <a
              href="/memos"
              className="flex-1 flex items-center justify-center text-[16px] tracking-wide uppercase hover:bg-[#eae0d8] h-full first:border-l-0 border-l-2 border-black"
            >
              Memos
            </a>
            <a
              href="/projects"
              className="flex-1 flex items-center justify-center text-[16px] tracking-wide uppercase hover:bg-[#eae0d8] h-full first:border-l-0 border-l-2 border-black"
            >
              Projects
            </a>
            <a
              href="/about"
              className="flex-1 flex items-center justify-center text-[16px] tracking-wide uppercase hover:bg-[#eae0d8] h-full first:border-l-0 border-l-2 border-black"
            >
              About
            </a>
            <a
              href="/contact"
              className="flex-1 flex items-center justify-center text-[16px] tracking-wide uppercase hover:bg-[#eae0d8] h-full first:border-l-0 border-l-2 border-black"
            >
              Contact
            </a>
          </nav>

          {/* Mobile Navigation */}
          <div className="flex items-center justify-end mr-3 md:hidden">
            <Sheet>
              <SheetTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-10 w-10 hover:none"
                >
                  <Menu className="h-6 w-6" />
                  <span className="sr-only">Toggle menu</span>
                </Button>
              </SheetTrigger>
              <SheetContent
                side="top"
                className="w-full bg-[#272727] text-white border-none"
              >
                <nav className="flex flex-col space-y-6 mt-8">
                  <a
                    href="/memos"
                    className="text-5xl font-medium tracking-wide hover:bg-black"
                  >
                    Memos
                  </a>
                  <a
                    href="/projects"
                    className="text-5xl font-medium tracking-wide hover:bg-black"
                  >
                    Projects
                  </a>
                  <a
                    href="/about"
                    className="text-5xl font-medium tracking-wide hover:bg-black"
                  >
                    About
                  </a>
                  <a
                    href="/contact"
                    className="text-5xl font-medium tracking-wide hover:bg-black"
                  >
                    Contact
                  </a>
                </nav>
              </SheetContent>
            </Sheet>
          </div>
        </div>
      </div>
    </header>
  );
}
