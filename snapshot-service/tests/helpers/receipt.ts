import sharp from "sharp";

import { RECEIPT_LAYOUT } from "../../src/receipt/layout.js";

export function drawRect(buffer: Uint8Array, width: number, x: number, y: number, w: number, h: number, value: number) {
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

export async function syntheticReceiptPng(checkedIndexes: number[] = []): Promise<Buffer> {
  const { widthPx, heightPx, checkboxLeft, checkboxTop, checkboxSize, checkboxSpacing, maxItems } = RECEIPT_LAYOUT;
  const pixels = new Uint8Array(widthPx * heightPx);
  pixels.fill(255);

  // Outer border for bbox detection.
  drawRect(pixels, widthPx, 0, 0, widthPx, 4, 0);
  drawRect(pixels, widthPx, 0, heightPx - 4, widthPx, 4, 0);
  drawRect(pixels, widthPx, 0, 0, 4, heightPx, 0);
  drawRect(pixels, widthPx, widthPx - 4, 0, 4, heightPx, 0);

  // Fiducial-like ticks.
  const guideLength = 48;
  const guideThickness = 10;
  const edge = 4;
  drawRect(pixels, widthPx, edge, heightPx / 2 - guideLength / 2, guideThickness, guideLength, 0);
  drawRect(pixels, widthPx, widthPx - edge - guideThickness, heightPx / 2 - guideLength / 2, guideThickness, guideLength, 0);
  drawRect(pixels, widthPx, widthPx / 2 - guideLength / 2, edge, guideLength, guideThickness, 0);
  drawRect(pixels, widthPx, widthPx / 2 - guideLength / 2, heightPx - edge - guideThickness, guideLength, guideThickness, 0);

  for (let i = 0; i < maxItems; i += 1) {
    if (!checkedIndexes.includes(i)) continue;
    const top = checkboxTop + i * checkboxSpacing;
    drawRect(pixels, widthPx, checkboxLeft, top, checkboxSize, checkboxSize, 0);
  }

  return sharp(Buffer.from(pixels), { raw: { width: widthPx, height: heightPx, channels: 1 } })
    .png()
    .toBuffer();
}
