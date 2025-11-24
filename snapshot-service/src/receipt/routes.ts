import type { FastifyInstance } from "fastify";
import multipart from "@fastify/multipart";
import { z } from "zod";

import { analyzeReceiptBuffer } from "./processor.js";
import { renderUploadPage } from "./upload-page.js";
import { ReceiptProcessingError } from "./types.js";
import { ReceiptAnalysisSchema } from "../schema/receipt.js";

const UploadQuerySchema = z.object({
  date: z.string().optional(),
  receipt_id: z.string().optional(),
  items: z.string().optional(),
  layout: z.string().optional()
});

const DEFAULT_ITEMS = ["Breakfast", "Lunch", "Dinner", "Meds AM", "Meds PM", "Hydrate x8", "Exercise", "Notes"];

export async function registerReceiptRoutes(app: FastifyInstance) {
  await app.register(multipart, {
    limits: {
      fileSize: 15 * 1024 * 1024,
      files: 1
    }
  });

  app.get("/receipt/upload", async (request, reply) => {
    const parsed = UploadQuerySchema.safeParse(request.query);
    const items = parseItems(parsed.success ? parsed.data.items : undefined);
    const html = renderUploadPage({
      items,
      date: parsed.success ? parsed.data.date : undefined,
      receiptId: parsed.success ? parsed.data.receipt_id : undefined,
      targetUrl: "/receipt/analyze"
    });
    reply.type("text/html").send(html);
  });

  app.post(
    "/receipt/analyze",
    {
      schema: {
        response: {
          200: ReceiptAnalysisSchema
        }
      }
    },
    async (request, reply) => {
      try {
        const file = await request.file();
        if (!file) {
          throw new ReceiptProcessingError("Missing receipt file upload", 400);
        }
        const fields = file.fields || {};
        const items = parseItems(extractField(fields, "items"));
        const receiptId = extractField(fields, "receipt_id");
        const date = extractField(fields, "date");
        const buffer = await file.toBuffer();
        const result = await analyzeReceiptBuffer(buffer, {
          items,
          receiptId,
          date
        });
        reply.send(result);
      } catch (error) {
        if (error instanceof ReceiptProcessingError) {
          reply.status(error.statusCode).send({ status: "error", message: error.message });
          return;
        }
        request.log.error(error);
        reply.status(500).send({ status: "error", message: "Unexpected error while processing receipt." });
      }
    }
  );
}

function parseItems(raw: string | undefined): string[] {
  if (!raw) return DEFAULT_ITEMS;
  try {
    const decoded = decodeURIComponent(raw);
    const parsed = JSON.parse(decoded);
    if (Array.isArray(parsed)) {
      return parsed.map((value) => String(value)).filter((value) => value.trim().length > 0);
    }
  } catch {
    return DEFAULT_ITEMS;
  }
  return DEFAULT_ITEMS;
}

function extractField(fields: Record<string, unknown>, key: string): string | undefined {
  const entry = fields[key];
  if (!entry) return undefined;
  const value = Array.isArray(entry) ? entry[0] : entry;
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "object" && value !== null && "value" in value) {
    const raw = (value as { value?: unknown }).value;
    if (typeof raw === "string") return raw;
    if (Buffer.isBuffer(raw)) return raw.toString("utf8");
  }
  return undefined;
}
