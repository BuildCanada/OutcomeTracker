"use client";

import React from "react";
import CFTAExceptionsChart from "@/components/charts/CFTAExceptionsChart";

export default function CFTADemoPage() {
  return (
    <div className="container mx-auto px-4 py-8">
      <div className="max-w-6xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-4">
            CFTA Exceptions Demo
          </h1>
          <p className="text-lg text-gray-600 mb-6">
            This chart shows the number of exceptions to the Canadian Free Trade Agreement (CFTA) 
            by province and territory from 2022 to 2024. The data is sourced from the Canadian 
            Federation of Independent Business (CFIB).
          </p>
        </div>

        <div className="bg-white border border-gray-200 rounded-lg shadow-sm p-6 mb-8">
          <CFTAExceptionsChart
            title="Canadian Free Trade Agreement Exceptions by Province/Territory"
            showLegend={true}
            height={500}
          />
        </div>

        <div className="grid md:grid-cols-2 gap-6">
          <div className="bg-white border border-gray-200 rounded-lg shadow-sm p-6">
            <h3 className="text-xl font-semibold mb-4">Key Insights</h3>
            <ul className="space-y-2 text-gray-700">
              <li>• Quebec has consistently had the highest number of exceptions (35-36)</li>
              <li>• New Brunswick shows an increasing trend (29 → 31)</li>
              <li>• Federal exceptions decreased significantly from 29 to 21 in 2024</li>
              <li>• Alberta has the fewest exceptions, increasing from 6 to 8</li>
              <li>• Yukon showed improvement, dropping from 33 to 29 exceptions</li>
            </ul>
          </div>

          <div className="bg-white border border-gray-200 rounded-lg shadow-sm p-6">
            <h3 className="text-xl font-semibold mb-4">About CFTA</h3>
            <p className="text-gray-700 mb-3">
              The Canadian Free Trade Agreement (CFTA) aims to reduce and eliminate barriers 
              to the free movement of persons, goods, services and investments within Canada.
            </p>
            <p className="text-gray-700">
              Exceptions represent areas where provinces and territories maintain trade 
              barriers that restrict interprovincial commerce.
            </p>
          </div>
        </div>

        <div className="mt-8 bg-white border border-gray-200 rounded-lg shadow-sm p-6">
          <CFTAExceptionsChart
            title="CFTA Exceptions - Compact View"
            showLegend={false}
            height={300}
          />
        </div>
      </div>
    </div>
  );
}