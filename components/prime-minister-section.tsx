import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import MetricChart from "@/components/metric-chart"
import type { PrimeMinister } from "@/lib/types"

interface PrimeMinisterSectionProps {
  primeMinister: PrimeMinister;
}

export default function PrimeMinisterSection({ primeMinister }: PrimeMinisterSectionProps) {
  if (!primeMinister) {
    return <div>Loading Prime Minister's data...</div>;
  }

  return (
    <div className="border border-[#d3c7b9] bg-white p-6">
      <div className="flex items-center gap-6">
        <Avatar className="h-20 w-20 rounded-full border-4 border-[#f5d0a9]">
          <AvatarImage src={primeMinister.avatarUrl || "/placeholder.svg"} alt={primeMinister.name} />
          <AvatarFallback className="bg-[#f5d0a9] text-[#8b2332]">
            {primeMinister.name
              .split(" ")
              .map((n) => n[0])
              .join("")}
          </AvatarFallback>
        </Avatar>

        <div>
          <h2 className="text-2xl font-bold text-[#222222]">{primeMinister.name}</h2>
          <p className="text-[#555555]">{primeMinister.title}</p>
        </div>
      </div>

      {primeMinister.guidingMetrics && primeMinister.guidingMetrics.length > 0 && (
      <div className="mt-10 w-full max-w-md border border-[#d3c7b9] p-4">
        <MetricChart
          title={primeMinister.guidingMetrics[0].title}
          data={primeMinister.guidingMetrics[0].data}
          goal={primeMinister.guidingMetrics[0].goal}
        />
      </div>
      )}
    </div>
  )
}
