import React from "react";

interface ChartWithSourceProps {
  children: React.ReactNode;
  dataSource: string;
  dataSourceUrl?: string;
  targetSource?: string;
  targetSourceUrl?: string;
}

export default function ChartWithSource({
  children,
  dataSource,
  dataSourceUrl,
  targetSource,
  targetSourceUrl,
}: ChartWithSourceProps) {
  return (
    <div className="border mb-8">
      <div className="pt-4 px-4">
        {children}
      </div>
      <div className="px-4 pb-4 text-xs text-gray-500">
        Source:{" "}
        {dataSourceUrl ? (
          <a
            href={dataSourceUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-gray-500 hover:text-gray-800 inline-flex items-center gap-1"
          >
            {dataSource}
          </a>
        ) : (
          dataSource
        )}
        {targetSource && (
          <>
            {" • "}
            Target:{" "}
            {targetSourceUrl ? (
              <a
                href={targetSourceUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-gray-500 hover:text-gray-800 inline-flex items-center gap-1"
              >
                {targetSource}
              </a>
            ) : (
              targetSource
            )}
          </>
        )}
      </div>
    </div>
  );
} 