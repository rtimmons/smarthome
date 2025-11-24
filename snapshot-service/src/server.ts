import Fastify from "fastify";
import fastifyCors from "@fastify/cors";
import { serializerCompiler, validatorCompiler, type ZodTypeProvider } from "fastify-type-provider-zod";

import { snapshotFixture } from "./fixtures/snapshot.js";
import { SnapshotSchema } from "./schema/snapshot.js";
import { registerReceiptRoutes } from "./receipt/routes.js";

const DEFAULT_PORT = 4010;
const DEFAULT_HOST = "0.0.0.0";

export async function buildServer() {
  const app = Fastify({
    logger: {
      level: process.env.LOG_LEVEL || "info"
    }
  }).withTypeProvider<ZodTypeProvider>();

  app.setValidatorCompiler(validatorCompiler);
  app.setSerializerCompiler(serializerCompiler);

  app.register(fastifyCors, {
    origin: true
  });

  app.get("/healthz", async () => ({ status: "ok" }));

  app.get(
    "/snapshot",
    {
      schema: {
        response: {
          200: SnapshotSchema
        }
      }
    },
    async () => snapshotFixture
  );

  await registerReceiptRoutes(app);

  return app;
}

export async function start() {
  const port = Number.parseInt(process.env.PORT || `${DEFAULT_PORT}`, 10);
  const host = process.env.HOST || DEFAULT_HOST;

  const app = await buildServer();
  try {
    await app.listen({ port, host });
    app.log.info({ port, host }, "Snapshot service started");
  } catch (err) {
    app.log.error(err, "Failed to start snapshot service");
    process.exit(1);
  }
}

if (process.env.NODE_ENV !== "test") {
  // eslint-disable-next-line @typescript-eslint/no-floating-promises
  start();
}
