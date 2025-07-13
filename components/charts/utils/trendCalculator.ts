/**
 * Calculate linear regression trend line for a series of data points
 * @param data - Array of numeric values (must not contain null/NaN values)
 * @returns Array of trend values with same length as input data
 */
export function calculateLinearTrend(data: number[]): number[] {
  // check if all values are valid numbers
  if (data.some((value) => isNaN(value) || value === null)) {
    const invalidCount = data.filter((value) => isNaN(value) || value === null).length;
    const totalCount = data.length;
    console.error(
      `calculateLinearTrend: Data contains ${invalidCount}/${totalCount} invalid values (NaN or null). ` +
        `Linear regression requires continuous numeric data. ` +
        `Consider filtering out null values before calling this function. ` +
        `Returning empty array to prevent chart errors.`
    );
    return [];
  }

  // Calculate linear regression using least squares method
  const n = data.length;
  const sumX = data.reduce((sum, _, index) => sum + index, 0);
  const sumY = data.reduce((sum, value) => sum + value, 0);
  const sumXY = data.reduce((sum, value, index) => sum + index * value, 0);
  const sumX2 = data.reduce((sum, _, index) => sum + index * index, 0);

  const slope = (n * sumXY - sumX * sumY) / (n * sumX2 - sumX * sumX);
  const intercept = (sumY - slope * sumX) / n;

  // Generate trend values for all data points
  return data.map((_, index) => intercept + slope * index);
}

/**
 * Calculate moving average for a series of data points
 * @param data - Array of numeric values
 * @param period - Number of periods for the moving average (e.g., 4 for quarterly, 12 for monthly)
 * @returns Array of moving average values with same length as input data (null for incomplete periods)
 */
export function calculateMovingAverage(data: number[], period: number): (number | null)[] {
  if (period <= 0 || period > data.length) {
    console.error(
      `calculateMovingAverage: Invalid period ${period}. Period must be > 0 and <= data length (${data.length}). ` +
        `Returning empty array to prevent chart errors.`
    );
    return [];
  }

  return data.map((_: number, index: number, array: number[]) => {
    if (index < period - 1) return null;

    let sum = 0;
    for (let i = 0; i < period; i++) {
      sum += array[index - i];
    }
    return sum / period;
  });
}
