
import type { ChartDataset } from "chart.js";

/**
 * Configuration type for Chart.js line chart datasets.
 * 
 * @see {@link https://www.chartjs.org/docs/latest/charts/line.html | Chart.js Line Chart Documentation}
 */
export type LineChartDataset = ChartDataset<"line", (number | null)[]>;
