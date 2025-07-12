import { describe, it, expect, vi } from "vitest";
import { calculateLinearTrend } from "./trendCalculator";

describe("calculateLinearTrend", () => {
  it("should calculate linear trend for perfect sequences", () => {
    const ascending = [1, 2, 3, 4, 5];
    const result = calculateLinearTrend(ascending);

    expect(result).toHaveLength(5);
    expect(result[0]).toBeCloseTo(1, 10);
    expect(result[4]).toBeCloseTo(5, 10);
  });

  it("should handle identical values gracefully", () => {
    const identical = [5, 5, 5, 5, 5];
    const result = calculateLinearTrend(identical);

    expect(result).toHaveLength(5);
    expect(result.every((val) => Math.abs(val - 5) < 0.001)).toBe(true);
  });

  it("should work with various data types", () => {
    // Negative values
    const negative = [-3, -1, 1, 3, 5];
    expect(calculateLinearTrend(negative)).toHaveLength(5);

    // Decimal values
    const decimal = [1.5, 2.5, 3.5, 4.5, 5.5];
    expect(calculateLinearTrend(decimal)).toHaveLength(5);

    // Large numbers
    const large = [1000, 2000, 3000, 4000, 5000];
    expect(calculateLinearTrend(large)).toHaveLength(5);
  });

  it("should handle minimum data points", () => {
    const twoPoints = [1, 3];
    const result = calculateLinearTrend(twoPoints);

    expect(result).toHaveLength(2);
    expect(result[0]).toBeCloseTo(1, 10);
    expect(result[1]).toBeCloseTo(3, 10);
  });

  it("should console.error when null values are present", () => {
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    const nullValues = [1, null, 3, null, 5];
    const result = calculateLinearTrend(nullValues as number[]);

    expect(result).toHaveLength(0); // should return empty array
    expect(consoleSpy).toHaveBeenCalled();

    consoleSpy.mockRestore();
  });
});
