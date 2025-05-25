import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import MetricChart from "./MetricChart";
import type { PrimeMinister } from "@/lib/types";
import PopulationChart from "./charts/PopulationChart";

interface PrimeMinisterSectionProps {
  primeMinister: PrimeMinister;
}

export default function PrimeMinisterSection({
  primeMinister,
}: PrimeMinisterSectionProps) {
  if (!primeMinister) {
    return <div>Loading Prime Minister's data...</div>;
  }

  return (
    <div>
      <div className="flex items-center gap-6 mb-8">
        <Avatar className="h-20 w-20">
          <AvatarImage
            src={primeMinister.avatarUrl || "/placeholder.svg"}
            alt={primeMinister.name}
            className="object-cover object-[center_25%]"
          />
          <AvatarFallback className="bg-[#f5d0a9] text-[#8b2332]">
            {primeMinister.name
              .split(" ")
              .map((n) => n[0])
              .join("")}
          </AvatarFallback>
        </Avatar>

        <div>
          <h2 className="text-2xl">
            {primeMinister.name}
          </h2>
          <p className="text-sm font-mono">{primeMinister.title}</p>
        </div>
      </div>

      <div className="border border-[#d3c7b9] bg-white p-6">
        {primeMinister.guidingMetrics &&
          primeMinister.guidingMetrics.length > 0 && (
            <div className="w-full max-w-md border border-[#d3c7b9] p-4">
              <PopulationChart />
              {/* <MetricChart
                title={primeMinister.guidingMetrics[0].title}
                data={primeMinister.guidingMetrics[0].data}
                goal={primeMinister.guidingMetrics[0].goal}
              /> */}
            </div>
          )}
      </div>
    </div>
  );
}
