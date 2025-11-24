import { z } from "zod";

export const ReceiptCheckboxSchema = z.object({
  label: z.string(),
  checked: z.boolean(),
  mean: z.number(),
  threshold: z.number(),
  box: z.object({
    x: z.number(),
    y: z.number(),
    size: z.number()
  })
});

export const ReceiptAnalysisSchema = z.object({
  status: z.literal("ok"),
  receipt_id: z.string().optional(),
  date: z.string().optional(),
  layout: z.string(),
  items: z.array(ReceiptCheckboxSchema),
  warnings: z.array(z.string()),
  debug: z
    .object({
      boundingBox: z.object({
        minX: z.number(),
        minY: z.number(),
        maxX: z.number(),
        maxY: z.number(),
        pixelThreshold: z.number()
      }),
      source: z.object({
        width: z.number(),
        height: z.number()
      }),
      scale: z.object({
        x: z.number(),
        y: z.number()
      })
    })
    .optional()
});

export type ReceiptAnalysis = z.infer<typeof ReceiptAnalysisSchema>;
