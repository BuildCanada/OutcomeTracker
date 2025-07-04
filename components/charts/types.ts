
// https://www.chartjs.org/docs/latest/charts/line.html
export interface LineLineChartDataset {
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