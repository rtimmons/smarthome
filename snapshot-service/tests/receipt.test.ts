import { describe, expect, it } from "vitest";
import sharp from "sharp";

import { analyzeReceiptBuffer } from "../src/receipt/processor.js";
import { RECEIPT_LAYOUT } from "../src/receipt/layout.js";
import { ReceiptProcessingError } from "../src/receipt/types.js";
import { syntheticReceiptPng } from "./helpers/receipt.js";

function drawRect(buffer: Uint8Array, width: number, x: number, y: number, w: number, h: number, value: number) {
  const startX = Math.max(0, Math.floor(x));
  const startY = Math.max(0, Math.floor(y));
  const endX = Math.min(width - 1, Math.floor(x + w));
  const height = Math.floor(buffer.length / width);
  const endY = Math.min(height - 1, Math.floor(y + h));
  for (let yy = startY; yy <= endY; yy += 1) {
    const rowStart = yy * width;
    for (let xx = startX; xx <= endX; xx += 1) {
      buffer[rowStart + xx] = value;
    }
  }
}

function sampleMeanFromPng(buffer: Buffer, x: number, y: number, size: number): Promise<number> {
  return sharp(buffer)
    .raw()
    .toBuffer({ resolveWithObject: true })
    .then(({ data, info }) => {
      const clampedSize = Math.max(1, Math.floor(size));
      let total = 0;
      let count = 0;
      const startX = Math.max(0, Math.floor(x));
      const startY = Math.max(0, Math.floor(y));
      const endX = Math.min(info.width - 1, startX + clampedSize);
      const endY = Math.min(info.height - 1, startY + clampedSize);
      const stride = info.width * info.channels;
      for (let yy = startY; yy <= endY; yy += 1) {
        const rowStart = yy * stride;
        for (let xx = startX; xx <= endX; xx += 1) {
          total += data[rowStart + xx * info.channels];
          count += 1;
        }
      }
      return count > 0 ? total / count : 255;
    });
}

describe("analyzeReceiptBuffer", () => {
  it("marks intended checkboxes as checked", async () => {
    const buffer = await syntheticReceiptPng([0, 2, 5]);
    const items = ["Breakfast", "Lunch", "Dinner", "Meds AM", "Meds PM", "Hydrate x8", "Exercise", "Notes"];

    // Sanity check the synthetic image has dark boxes where expected.
    const centerX = RECEIPT_LAYOUT.checkboxLeft + RECEIPT_LAYOUT.checkboxSize / 2;
    const baseY = RECEIPT_LAYOUT.checkboxTop + RECEIPT_LAYOUT.checkboxSize / 2;
    const sampleSize = RECEIPT_LAYOUT.checkboxSize * 0.6;
    const rawMean = await sampleMeanFromPng(buffer, centerX, baseY, sampleSize);
    expect(rawMean).toBeLessThan(100);

    const result = await analyzeReceiptBuffer(buffer, { items });

    expect(result.items).toHaveLength(items.length);
    const checked = result.items.filter((item) => item.checked).map((item) => item.label);
    // Debug aids if this ever fails in CI.
    if (checked.length === 0) {
      // eslint-disable-next-line no-console
      console.error("Receipt means:", result.items.map((item) => item.mean));
    }
    expect(checked).toEqual(["Breakfast", "Dinner", "Hydrate x8"]);
  });

  it("throws when no receipt is visible", async () => {
    const { widthPx, heightPx } = RECEIPT_LAYOUT;
    const blank = await sharp(Buffer.alloc(widthPx * heightPx, 255), {
      raw: { width: widthPx, height: heightPx, channels: 1 }
    })
      .png()
      .toBuffer();
    await expect(analyzeReceiptBuffer(blank, { items: ["A", "B"] })).rejects.toBeInstanceOf(ReceiptProcessingError);
  });
});
