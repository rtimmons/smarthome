import path from "node:path";

import fastifyCors from "@fastify/cors";
import fastifyStatic from "@fastify/static";
import Fastify, { type FastifyReply } from "fastify";
import {
  serializerCompiler,
  validatorCompiler,
  type ZodTypeProvider,
} from "fastify-type-provider-zod";
import { z } from "zod";

import { loadConfig } from "./config.js";
import { slugRegex } from "./slug.js";
import { MongoTinyUrlStore } from "./stores/mongoStore.js";
import { TinyUrl, TinyUrlStore } from "./types.js";

const RESERVED_SLUGS = new Set(["api", "healthz", "favicon.ico"]);

const TinyUrlResponseSchema = z.object({
  slug: z.string(),
  target: z.string().url(),
  visitCount: z.number().nonnegative(),
  visits: z.array(z.string().datetime()),
  lastVisitedAt: z.string().datetime().optional(),
  createdAt: z.string().datetime(),
  updatedAt: z.string().datetime(),
});

const TinyUrlListResponseSchema = z.array(TinyUrlResponseSchema);
const ErrorResponseSchema = z.object({ error: z.string() });

export interface BuildOptions {
  store?: TinyUrlStore;
  configOverrides?: Partial<ReturnType<typeof loadConfig>>;
}

const MONGO_HOST_FALLBACKS = ["addon_local_mongodb", "addon_mongodb", "mongodb"];

function toResponse(entry: TinyUrl) {
  return {
    slug: entry.slug,
    target: entry.target,
    visitCount: entry.visitCount,
    visits: entry.visits.map((v) => v.toISOString()),
    lastVisitedAt: entry.lastVisitedAt ? entry.lastVisitedAt.toISOString() : undefined,
    createdAt: entry.createdAt.toISOString(),
    updatedAt: entry.updatedAt.toISOString(),
  };
}

export async function buildServer(options?: BuildOptions) {
  const config = { ...loadConfig(), ...(options?.configOverrides || {}) };
  const fastify = Fastify({
    logger: {
      level: process.env.LOG_LEVEL || "info",
    },
    ignoreTrailingSlash: true,
    rewriteUrl: (req) => {
      const rawUrl = req.url || "";
      const [pathOnly, search = ""] = rawUrl.split("?", 2);
      const normalizedPath = pathOnly.replace(/\/{2,}/g, "/");
      return `${normalizedPath}${search ? `?${search}` : ""}`;
    },
  }).withTypeProvider<ZodTypeProvider>();

  fastify.setValidatorCompiler(validatorCompiler);
  fastify.setSerializerCompiler(serializerCompiler);

  void fastify.register(fastifyCors, {
    origin: true,
  });

  const { store, isMongo } = options?.store
    ? { store: options.store, isMongo: false }
    : await createStoreWithRetry(config, fastify.log);

  if (isMongo) {
    fastify.addHook("onClose", async () => {
      if (store instanceof MongoTinyUrlStore) {
        await store.close();
      }
    });
  }

  void fastify.register(fastifyStatic, {
    root: path.join(process.cwd(), "public"),
    prefix: "/assets/",
  });

  fastify.get("/", async (_, reply) => reply.sendFile("index.html"));

  fastify.get("/favicon.ico", async (_, reply) => reply.code(204).send());

  fastify.get("/healthz", async () => ({ status: "ok" }));

  fastify.get("/assets/app-config.js", async (request, reply) => {
    const baseUrl = config.publicBaseUrl || "";
    const payload = {
      baseUrl,
      port: config.port,
    };
    const js = `window.__TINYURL_CONFIG__ = ${JSON.stringify(payload)};`;
    return reply.type("application/javascript").send(js);
  });

  fastify.get(
    "/api/urls",
    {
      schema: {
        response: {
          200: TinyUrlListResponseSchema,
        },
      },
    },
    async () => {
      const urls = await store.list();
      return urls.map(toResponse);
    },
  );

  fastify.post(
    "/api/urls",
    {
      schema: {
        body: z.object({
          url: z.string().url(),
        }),
        response: {
          200: TinyUrlResponseSchema,
          201: TinyUrlResponseSchema,
        },
      },
    },
    async (request, reply) => {
      const { url } = request.body;
      const existing = await store.getByTarget(url);
      if (existing) {
        return reply.code(200).send(toResponse(existing));
      }
      const created = await store.create(url);
      return reply.code(201).send(toResponse(created));
    },
  );

  fastify.post(
    "/api/urls/:slug/reset",
    {
      schema: {
        params: z.object({ slug: z.string().regex(slugRegex) }),
        response: {
          200: TinyUrlResponseSchema,
          404: ErrorResponseSchema,
        },
      },
    },
    async (request, reply) => {
      const { slug } = request.params;
      const reset = await store.reset(slug);
      if (!reset) {
        return reply.code(404).send({ error: "Not found" });
      }
      return reply.send(toResponse(reset));
    },
  );

  fastify.delete(
    "/api/urls/:slug",
    {
      schema: {
        params: z.object({ slug: z.string().regex(slugRegex) }),
        response: {
          204: z.undefined(),
          404: ErrorResponseSchema,
        },
      },
    },
    async (request, reply) => {
      const { slug } = request.params;
      const deleted = await store.delete(slug);
      if (!deleted) {
        return reply.code(404).send({ error: "Not found" });
      }
      return reply.code(204).send();
    },
  );

  fastify.get("/:slug", async (request, reply) => {
    const slug = String((request.params as { slug?: string }).slug || "").replace(/^\/+|\/+$/g, "");
    if (!slugRegex.test(slug) || RESERVED_SLUGS.has(slug)) {
      return reply.code(404).send({ error: "Not found" });
    }
    return handleRedirect(slug, store, reply);
  });

  fastify.setNotFoundHandler(async (request, reply) => {
    const pathOnly = (request.raw.url || "").split("?")[0];
    const candidate = pathOnly.replace(/^\/+|\/+$/g, "");
    const isApi = candidate.startsWith("api/");
    const isAsset = candidate.startsWith("assets/");

    if (!candidate || isApi || isAsset || RESERVED_SLUGS.has(candidate)) {
      return reply.code(404).send({ error: "Not found" });
    }

    if (!slugRegex.test(candidate)) {
      return reply.code(404).send({ error: "Not found" });
    }

    return handleRedirect(candidate, store, reply);
  });

  return fastify;
}

async function handleRedirect(slug: string, store: TinyUrlStore, reply: FastifyReply) {
  if (RESERVED_SLUGS.has(slug)) {
    return reply.code(404).send({ error: "Not found" });
  }

  const updated = await store.recordHit(slug, new Date());
  if (updated) {
    return reply.redirect(updated.target, 302);
  }

  // Fallback: redirect even if the hit wasn't recorded (e.g., store bug) as long as the slug exists.
  const existing = await store.get(slug);
  if (existing) {
    return reply.redirect(existing.target, 302);
  }

  return reply.code(404).send({ error: "Not found" });
}

async function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function createStoreWithRetry(
  config: ReturnType<typeof loadConfig>,
  log: Fastify.FastifyLoggerInstance,
  connectFn: (url: string) => Promise<MongoTinyUrlStore> = MongoTinyUrlStore.connect,
): Promise<{ store: TinyUrlStore; isMongo: boolean }> {
  const candidates = expandMongoUrls(config.mongoUrl);

  for (let attempt = 1; attempt <= config.mongoRetries; attempt += 1) {
    const url = candidates[(attempt - 1) % candidates.length];
    try {
      const store = await connectFn(url);
      return { store, isMongo: true };
    } catch (err) {
      log.error(
        { err, attempt, mongoUrl: url, retries: config.mongoRetries },
        "Failed to connect to MongoDB",
      );
      if (attempt === config.mongoRetries) {
        throw err;
      }
      await sleep(config.mongoRetryDelayMs);
    }
  }

  throw new Error("Failed to connect to MongoDB after retries");
}

function expandMongoUrls(url: string): string[] {
  const urls = new Set<string>();
  urls.add(url);

  // Only attempt host fallbacks for single-host URLs of the form mongodb://[auth@]host[:port]/...
  const match = url.match(/^mongodb:\/\/([^@]+@)?([^/:]+)(:[0-9]+)?(\/.*)?$/);
  if (match) {
    const auth = match[1] ?? "";
    const host = match[2];
    const port = match[3] ?? "";
    const rest = match[4] ?? "";
    for (const candidateHost of MONGO_HOST_FALLBACKS) {
      if (candidateHost === host) continue;
      urls.add(`mongodb://${auth}${candidateHost}${port}${rest}`);
    }
  }

  return Array.from(urls);
}

export const _test = { createStoreWithRetry, expandMongoUrls };

export async function start() {
  const config = loadConfig();
  const app = await buildServer();
  try {
    await app.listen({ port: config.port, host: config.host });
    app.log.info({ port: config.port, host: config.host }, "TinyURL service started");
  } catch (err) {
    app.log.error(err, "Failed to start TinyURL service");
    process.exit(1);
  }
}

if (process.env.NODE_ENV !== "test") {
  // eslint-disable-next-line @typescript-eslint/no-floating-promises
  start();
}
