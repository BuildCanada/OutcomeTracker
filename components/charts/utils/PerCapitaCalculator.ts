/**
 * Utility functions for calculating per capita metrics from different data sources
 * Supports linear interpolation for mismatched time granularities
 */

export interface TimeSeriesDataPoint {
  date: string;  // Format: "YYYY-MM"
  value: number;
}

/**
 * Parse a date string in "YYYY-MM" format to a Date object
 */
export function parseDate(dateStr: string): Date {
  const [year, month] = dateStr.split('-').map(Number);
  return new Date(year, month - 1);  // JS months are 0-indexed
}

/**
 * Format a Date object to "YYYY-MM" string
 */
export function formatDate(date: Date): string {
  const year = date.getFullYear();
  const month = date.getMonth() + 1;  // Convert from 0-indexed to 1-indexed
  return `${year}-${month.toString().padStart(2, '0')}`;
}

/**
 * Linearly interpolate between two data points
 */
export function interpolate(
  date: Date,
  beforeDate: Date,
  afterDate: Date,
  beforeValue: number,
  afterValue: number
): number {
  const totalTimeDiff = afterDate.getTime() - beforeDate.getTime();
  const targetTimeDiff = date.getTime() - beforeDate.getTime();
  const ratio = targetTimeDiff / totalTimeDiff;
  return beforeValue + (afterValue - beforeValue) * ratio;
}

/**
 * Find the closest data points before and after a target date
 */
export function findClosestPoints(
  targetDate: Date, 
  data: TimeSeriesDataPoint[]
): { before: TimeSeriesDataPoint | null; after: TimeSeriesDataPoint | null } {
  let before: TimeSeriesDataPoint | null = null;
  let after: TimeSeriesDataPoint | null = null;
  
  const sortedData = [...data].sort((a, b) => 
    parseDate(a.date).getTime() - parseDate(b.date).getTime()
  );
  
  for (const point of sortedData) {
    const pointDate = parseDate(point.date);
    
    if (pointDate.getTime() <= targetDate.getTime()) {
      // This point is before or at the target date
      if (!before || parseDate(before.date).getTime() < pointDate.getTime()) {
        before = point;
      }
    } else {
      // This point is after the target date
      if (!after || parseDate(after.date).getTime() > pointDate.getTime()) {
        after = point;
      }
    }
  }
  
  return { before, after };
}

/**
 * Get interpolated value for a specific date
 */
export function getInterpolatedValue(
  targetDate: Date,
  data: TimeSeriesDataPoint[]
): number | null {
  const { before, after } = findClosestPoints(targetDate, data);
  
  // Exact match
  if (before && formatDate(targetDate) === before.date) {
    return before.value;
  }
  
  // Need to interpolate
  if (before && after) {
    return interpolate(
      targetDate,
      parseDate(before.date),
      parseDate(after.date),
      before.value,
      after.value
    );
  }
  
  // Can't interpolate - return the closest value if available
  if (before) return before.value;
  if (after) return after.value;
  
  return null;
}

/**
 * Convert raw data arrays from StatsCanada format to TimeSeriesDataPoint format
 */
export function convertRawData(data: [string, number][]): TimeSeriesDataPoint[] {
  return data.map(([date, value]) => ({ date, value }));
}

/**
 * Calculate per capita values by dividing metric data by population data
 * Will interpolate population data if needed
 */
export function calculatePerCapitaValues(
  metricData: TimeSeriesDataPoint[],
  populationData: TimeSeriesDataPoint[]
): TimeSeriesDataPoint[] {
  return metricData.map(metricPoint => {
    const date = parseDate(metricPoint.date);
    const populationValue = getInterpolatedValue(date, populationData);
    
    if (populationValue === null || populationValue === 0) {
      return { date: metricPoint.date, value: null as unknown as number };
    }
    
    const perCapitaValue = metricPoint.value / populationValue;
    return { date: metricPoint.date, value: perCapitaValue };
  }).filter(point => point.value !== null);
}

/**
 * Main function to calculate per capita values from raw StatsCanada data
 */
export function calculatePerCapita(
  metricRawData: [string, number][],
  populationRawData: [string, number][],
  multiplier: number = 1  // Optional multiplier (e.g. for per 1000 people)
): TimeSeriesDataPoint[] {
  const metricData = convertRawData(metricRawData);
  const populationData = convertRawData(populationRawData);
  
  const perCapitaData = calculatePerCapitaValues(metricData, populationData);
  
  // Apply multiplier if provided
  if (multiplier !== 1) {
    return perCapitaData.map(point => ({
      date: point.date,
      value: point.value * multiplier
    }));
  }
  
  return perCapitaData;
}