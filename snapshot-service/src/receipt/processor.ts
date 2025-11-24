import sharp from "sharp";

import { RECEIPT_LAYOUT, RECEIPT_LAYOUT_ID } from "./layout.js";
import { type ReceiptAnalysis, type ReceiptCheckboxResult, ReceiptProcessingError } from "./types.js";

const BBOX_PIXEL_THRESHOLD = 240;
const CHECKED_PIXEL_THRESHOLD = 170;
const MIN_BBOX_AREA = 5000;

type RawImage = {
  data: Buffer;
  width: number;
  height: number;
};

function isPortrait(width: number, height: number) {
  return height >= width;
}

async function loadGrayscale(buffer: Buffer): Promise<RawImage> {
  const rotated = sharp(buffer, { failOnError: false }).rotate();
  const meta = await rotated.metadata();
  let working = rotated;
  if (meta.width && meta.height && !isPortrait(meta.width, meta.height)) {
    working = rotated.rotate(90);
  }
  const { data, info } = await working.greyscale().raw().toBuffer({ resolveWithObject: true });
  return { data, width: info.width, height: info.height };
}

function findBoundingBox(image: RawImage) {
  let minX = image.width;
  let minY = image.height;
  let maxX = 0;
  let maxY = 0;
  const { data, width, height } = image;

  for (let y = 0; y < height; y += 1) {
    const rowStart = y * width;
    for (let x = 0; x < width; x += 1) {
      const value = data[rowStart + x];
      if (value < BBOX_PIXEL_THRESHOLD) {
        if (x < minX) minX = x;
        if (y < minY) minY = y;
        if (x > maxX) maxX = x;
        if (y > maxY) maxY = y;
      }
    }
  }
  if (minX > maxX || minY > maxY) {
    throw new ReceiptProcessingError("Could not detect the receipt in the photo. Try retaking closer and flatter.");
  }
  const area = (maxX - minX) * (maxY - minY);
  if (area < MIN_BBOX_AREA) {
    throw new ReceiptProcessingError("Receipt area too small to analyze. Move closer and ensure the receipt fills the frame.");
  }
  return { minX, minY, maxX, maxY };
}

function sampleMean(image: RawImage, x: number, y: number, size: number) {
  const { data, width, height } = image;
  const clampedSize = Math.max(1, Math.floor(size));
  let total = 0;
  let count = 0;
  const startX = Math.max(0, Math.floor(x));
  const startY = Math.max(0, Math.floor(y));
  const endX = Math.min(width - 1, startX + clampedSize);
  const endY = Math.min(height - 1, startY + clampedSize);

  for (let yy = startY; yy <= endY; yy += 1) {
    const rowStart = yy * width;
    for (let xx = startX; xx <= endX; xx += 1) {
      total += data[rowStart + xx];
      count += 1;
    }
  }
  return count > 0 ? total / count : 255;
}

type AnalysisOptions = {
  items: string[];
  receiptId?: string;
  date?: string;
};

export async function analyzeReceiptBuffer(buffer: Buffer, options: AnalysisOptions): Promise<ReceiptAnalysis> {
  const raw = await loadGrayscale(buffer);
  const bbox = findBoundingBox(raw);
  const bboxWidth = bbox.maxX - bbox.minX;
  const bboxHeight = bbox.maxY - bbox.minY;

  const scaleX = bboxWidth / RECEIPT_LAYOUT.widthPx;
  const scaleY = bboxHeight / RECEIPT_LAYOUT.heightPx;
  const results: ReceiptCheckboxResult[] = [];

  const items = options.items.slice(0, RECEIPT_LAYOUT.maxItems);
  for (let i = 0; i < items.length; i += 1) {
    const label = items[i];
    const targetTop = RECEIPT_LAYOUT.checkboxTop + i * RECEIPT_LAYOUT.checkboxSpacing;
    const sampleSize = RECEIPT_LAYOUT.checkboxSize * 0.6;
    const centerX = bbox.minX + (RECEIPT_LAYOUT.checkboxLeft + RECEIPT_LAYOUT.checkboxSize / 2) * scaleX;
    const centerY = bbox.minY + (targetTop + RECEIPT_LAYOUT.checkboxSize / 2) * scaleY;

    const mean = sampleMean(raw, centerX - sampleSize / 2, centerY - sampleSize / 2, sampleSize);
    const checked = mean < CHECKED_PIXEL_THRESHOLD;
    results.push({
      label,
      checked,
      mean: Math.round(mean),
      threshold: CHECKED_PIXEL_THRESHOLD,
      box: {
        x: Math.round(centerX - sampleSize / 2),
        y: Math.round(centerY - sampleSize / 2),
        size: Math.round(sampleSize)
      }
    });
  }

  return {
    status: "ok",
    receipt_id: options.receiptId,
    date: options.date,
    layout: RECEIPT_LAYOUT_ID,
    items: results,
    warnings: [],
    debug: {
      boundingBox: { ...bbox, pixelThreshold: BBOX_PIXEL_THRESHOLD },
      source: { width: raw.width, height: raw.height },
      scale: { x: scaleX, y: scaleY }
    }
  };
}
