
/**
 * Configuration interface for Chart.js line chart datasets.
 * 
 * @see {@link https://www.chartjs.org/docs/latest/charts/line.html | Chart.js Line Chart Documentation}
 */
export interface LineChartDataset {
  backgroundColor: string;
  label: string;
  data: (number | null)[];
  borderColor: string;
  tension?: number;
  borderWidth?: number;
  pointRadius?: number;
  pointHoverRadius?: number;
  borderDash?: number[];
  fill?: boolean | string;
  stack?: string;
  order?: number;
  type?: any;
  yAxisID?: string;
  [key: string]: any;
}
