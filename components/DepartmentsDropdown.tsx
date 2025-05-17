"use client";
import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { DepartmentConfig } from "@/lib/types";
import { cn } from "@/lib/utils";

interface DepartmentsDropdownProps {
  departments: DepartmentConfig[];
  onSelectDepartment: (departmentId: string) => void;
  isActive?: boolean;
  className?: string;
}

export default function DepartmentsDropdown({
  departments,
  onSelectDepartment,
  isActive = false,
  className,
}: DepartmentsDropdownProps) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <DropdownMenu open={isOpen} onOpenChange={setIsOpen}>
      <DropdownMenuTrigger asChild>
        <Button
          variant="outline"
          className={cn(
            "border-none px-4 py-3 text-sm uppercase tracking-wider w-full",
            isActive ? "bg-[#8b2332] text-white" : "bg-white text-black",
            className,
          )}
        >
          More{" "}
          {isOpen ? (
            <ChevronUp className="ml-2 h-4 w-4" />
          ) : (
            <ChevronDown className="ml-2 h-4 w-4" />
          )}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-56 bg-white border border-[#d3c7b9] p-0">
        {departments.map((department) => (
          <DropdownMenuItem
            key={department.id}
            className="px-4 py-3 text-sm uppercase tracking-wider hover:bg-background cursor-pointer"
            onClick={() => {
              onSelectDepartment(department.id);
              setIsOpen(false);
            }}
          >
            {department.shortName}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
} 
