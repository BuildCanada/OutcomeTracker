export default function Footer() {
  return (
    <footer className="border-t border-canada-red py-6">
      <div className="container mx-auto px-4">
        <div className="flex flex-col items-center justify-between gap-4 md:flex-row">
          <p className="text-sm text-muted-foreground">
            &copy; {new Date().getFullYear()} Canada\'s Promise Tracker. All rights reserved.
          </p>
          <p className="text-sm text-muted-foreground">
            This is a demo application and not affiliated with the Canadian government.
          </p>
        </div>
      </div>
    </footer>
  )
} 