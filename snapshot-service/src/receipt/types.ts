export interface ReceiptCheckboxResult {
  label: string;
  checked: boolean;
  mean: number;
  threshold: number;
  box: {
    x: number;
    y: number;
    size: number;
  };
}

export interface ReceiptAnalysis {
  status: "ok";
  receipt_id?: string;
  date?: string;
  layout: string;
  items: ReceiptCheckboxResult[];
  warnings: string[];
  debug?: {
    boundingBox: {
      minX: number;
      minY: number;
      maxX: number;
      maxY: number;
      pixelThreshold: number;
    };
    source: {
      width: number;
      height: number;
    };
    scale: {
      x: number;
      y: number;
    };
  };
}

export class ReceiptProcessingError extends Error {
  statusCode: number;

  constructor(message: string, statusCode = 400) {
    super(message);
    this.name = "ReceiptProcessingError";
    this.statusCode = statusCode;
  }
}
