import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"

interface OtherDepartmentSectionProps {
  departmentName: string
}

export default function OtherDepartmentSection({ departmentName }: OtherDepartmentSectionProps) {
  // This would typically fetch data for the specific department
  // For now, we'll use placeholder data
  const minister = {
    name: `Minister of ${departmentName}`,
    title: `Minister of ${departmentName}`,
    avatarUrl: "/placeholder.svg?height=200&width=200",
  }

  return (
    <div>
      <div className="flex items-center gap-6">
        <Avatar className="h-20 w-20 rounded-full border-4 border-[#a9d0f5]">
          <AvatarImage src={minister.avatarUrl || "/placeholder.svg"} alt={minister.name} />
          <AvatarFallback className="bg-[#a9d0f5] text-[#2332a9]">
            {departmentName.substring(0, 2).toUpperCase()}
          </AvatarFallback>
        </Avatar>

        <div>
          <h2 className="text-2xl font-bold text-[#222222]">{minister.name}</h2>
          <p className="text-[#555555]">{minister.title}</p>
        </div>
      </div>

      <div className="mt-8 p-6 border border-[#d3c7b9] bg-[#f8f2ea]">
        <h3 className="text-xl font-bold text-[#222222] mb-4">Department Overview</h3>
        <p className="text-[#333333]">
          The Department of {departmentName} is responsible for developing and implementing policies and programs
          related to {departmentName.toLowerCase()} in Canada. The department works closely with provincial and
          territorial governments, as well as with stakeholders and international partners.
        </p>

        <div className="mt-6 p-4 bg-white border border-[#d3c7b9]">
          <p className="text-[#8b2332] font-medium">Key Initiatives Coming Soon</p>
          <p className="text-sm text-[#555555] mt-2">
            Detailed information about the {departmentName} department's initiatives, metrics, and progress will be
            available in future updates.
          </p>
        </div>
      </div>
    </div>
  )
}
