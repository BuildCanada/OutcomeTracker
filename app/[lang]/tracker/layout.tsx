import { Sidebar } from "@/components/HomePageClient";
import { DEPARTMENTS } from "./_constants";
import Link from "next/link";

export default function Layout({
  children,
  params: { department },
}: Readonly<{
  children: React.ReactNode;
  params: { lang: string; department?: string };
}>) {
  return (
    <div className="min-h-screen">
      <div className="container px-4 py-12">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          <Sidebar pageTitle="Outcomes Tracker" />
          <div className="col-span-3">
            <DepartmentPillLinks currentDepartmentSlug={department} />
            {children}
          </div>
        </div>
      </div>
    </div>
  );
}

function DepartmentPillLinks({
  currentDepartmentSlug,
}: {
  currentDepartmentSlug?: string;
}) {
  // const { data: departments } = useSWR<DepartmentListing[]>(
  //   "/api/v1/departments",
  // );

  // const filteredDepartments = departments
  //   ?.filter((department) => DEPARTMENT_DISPLAY_ORDER[department.slug] != null)
  //   ?.sort(
  //     (a, b) =>
  //       DEPARTMENT_DISPLAY_ORDER[a.slug] - DEPARTMENT_DISPLAY_ORDER[b.slug],
  //   );

  // const params = useParams<{ lang: string; department: string }>();

  // const activeTabId = currentDepartmentSlug;

  return (
    <div className="flex flex-wrap gap-2 mb-8">
      {DEPARTMENTS.map(({ slug, name }) => {
        return (
          <Link
            key={slug}
            href={`/en/tracker/${slug}`}
            className={`px-4 py-2 text-sm font-mono transition-colors
                        ${
                          currentDepartmentSlug == slug
                            ? "bg-[#8b2332] text-white"
                            : "bg-white text-[#222222] border border-[#d3c7b9] hover:bg-gray-50"
                        }`}
          >
            {name}
          </Link>
        );
      })}
    </div>
  );
}
