import { PRIMARY_BORDER_COLOR, PRIMARY_BG_COLOR, TARGET_BORDER_COLOR, TARGET_BG_COLOR } from "./constants";
import type { LineChartDataset } from "../types";

/**
 * Get standard styling for primary data series (blue color scheme)
 * @param options - Optional properties to override defaults
 * @returns Style object for primary datasets
 */
export const getPrimaryLineStyling = (options: Partial<LineChartDataset> = {}): Partial<LineChartDataset> => ({
  borderColor: PRIMARY_BORDER_COLOR,
  backgroundColor: PRIMARY_BG_COLOR,
  tension: 0.3,
  ...options,
});

/**
 * Get standard styling for target/reference lines (red color scheme with dashed line)
 * @param options - Optional properties to override defaults
 * @returns Style object for target datasets
 */
export const getTargetLineStyling = (options: Partial<LineChartDataset> = {}): Partial<LineChartDataset> => ({
  borderColor: TARGET_BORDER_COLOR,
  backgroundColor: TARGET_BG_COLOR,
  borderWidth: 2,
  borderDash: [5, 5],
  pointRadius: 0,
  tension: 0,
  ...options,
});

/**
 * Get standard styling for trend/moving average lines (red color scheme)
 * @param options - Optional properties to override defaults
 * @returns Style object for trend datasets
 */
export const getTrendLineStyling = (options: Partial<LineChartDataset> = {}): Partial<LineChartDataset> => ({
  borderColor: TARGET_BORDER_COLOR,
  backgroundColor: TARGET_BG_COLOR,
  borderDash: [5, 5],
  tension: 0.3,
  ...options,
});
