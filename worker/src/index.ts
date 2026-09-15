import { Client } from "pg";

export interface Env {
  BOOKS_BUCKET: R2Bucket;
  ASSETS: Fetcher;
  FRONTEND_ORIGIN: string;
  DATABASE_URL?: string;
  HYPERDRIVE?: { connectionString: string };
  ORVIX_AUTH_SECRET?: string;
}

const profile = (u: any) => ({ id: u.id, phone: u.phone, name: u.name || "Etudiant", onboarding_completed: Boolean(u.onboarding_completed), level: u.level || "", subjects: u.subjects || [], goal: u.goal || "", learning_style: u.learning_style || "", difficulties: u.difficulties || "", welcome_seen: Boolean(u.welcome_seen) });
const normalizePhone = (p: string) => p.trim().replace(/[^\d+]/g, "").replace(/^00/, "+");
async function passwordHash(password: string, salt = crypto.randomUUID()) {
  const key = await crypto.subtle.importKey("raw", new TextEncoder().encode(password), "PBKDF2", false, ["deriveBits"]);
  const bits = await crypto.subtle.deriveBits({ name: "PBKDF2", salt: new TextEncoder().encode(salt), iterations: 120000, hash: "SHA-256" }, key, 256);
  return `${salt}:${btoa(String.fromCharCode(...new Uint8Array(bits)))}`;
}
async function authToken(id: string, secret: string) {
  const key = await crypto.subtle.importKey("raw", new TextEncoder().encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const sig = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(id));
  return `${id}.${btoa(String.fromCharCode(...new Uint8Array(sig)))}`;
}

const json = (body: unknown, status = 200, origin = "*") =>
  new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Access-Control-Allow-Origin": origin,
      "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Orvix-Language, X-Request-ID",
      "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
      "X-Content-Type-Options": "nosniff",
    },
  });

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const origin = env.FRONTEND_ORIGIN || "*";
    if (request.method === "OPTIONS") return json({}, 204, origin);

    const url = new URL(request.url);
    if (url.pathname === "/health") {
      return json({ status: "ok", service: "orvix-api", database: Boolean(env.DATABASE_URL) }, 200, origin);
    }

    if ((url.pathname === "/api/v1/auth/register" || url.pathname === "/api/v1/auth/login") && request.method === "POST") {
      try {
      if (!env.DATABASE_URL || !env.ORVIX_AUTH_SECRET) return json({ detail: "La base de données n'est pas configurée." }, 503, origin);
      const body = await request.json() as { phone?: string; password?: string };
      const phone = normalizePhone(body.phone || "");
      const password = body.password || "";
      if (phone.length < 6 || password.length < 6) return json({ detail: "Numéro ou mot de passe invalide." }, 422, origin);
      const client = new Client({ connectionString: env.HYPERDRIVE?.connectionString || env.DATABASE_URL });
      await client.connect();
      await client.query("CREATE TABLE IF NOT EXISTS orvix_users (id text primary key, phone text unique not null, password_hash text not null, name text default 'Etudiant', onboarding_completed boolean default false, level text default '', subjects jsonb default '[]', goal text default '', learning_style text default '', difficulties text default '', welcome_seen boolean default false, created_at timestamptz default now())");
      const found = (await client.query("SELECT * FROM orvix_users WHERE phone=$1 LIMIT 1", [phone])).rows;
      if (url.pathname.endsWith("register")) {
        if (found.length) return json({ detail: "Ce numero a deja un compte." }, 409, origin);
        const id = crypto.randomUUID(); const hash = await passwordHash(password);
        const rows = (await client.query("INSERT INTO orvix_users (id, phone, password_hash) VALUES ($1,$2,$3) RETURNING *", [id, phone, hash])).rows;
        await client.end();
        return json({ token: await authToken(id, env.ORVIX_AUTH_SECRET), user: profile(rows[0]) }, 201, origin);
      }
      if (!found.length) return json({ detail: "Numero ou mot de passe incorrect." }, 401, origin);
      const [salt, encoded] = found[0].password_hash.split(":"); const check = await passwordHash(password, salt);
      if (check !== `${salt}:${encoded}`) return json({ detail: "Numero ou mot de passe incorrect." }, 401, origin);
      await client.end();
      return json({ token: await authToken(found[0].id, env.ORVIX_AUTH_SECRET), user: profile(found[0]) }, 200, origin);
      } catch (error) {
        console.error("auth_failed", error);
        return json({ detail: "La connexion à Neon a échoué." }, 503, origin);
      }
    }

    if (url.pathname === "/api/v1/books" && request.method === "POST") {
      const form = await request.formData();
      const file = form.get("file");
      if (!(file instanceof File)) return json({ detail: "Le fichier du livre est requis." }, 400, origin);
      const id = crypto.randomUUID();
      await env.BOOKS_BUCKET.put(`books/${id}/${file.name}`, file.stream(), {
        httpMetadata: { contentType: file.type || "application/octet-stream" },
        customMetadata: { originalName: file.name },
      });
      return json({ id, name: file.name, size: file.size, status: "stored" }, 201, origin);
    }

    if (request.method === "GET" && !url.pathname.startsWith("/api/") && url.pathname !== "/health") {
      const asset = await env.ASSETS.fetch(request);
      if (asset.status !== 404) return asset;
      return env.ASSETS.fetch(new Request(new URL("/index.html", request.url), request));
    }

    return json({ detail: "Route Worker non implémentée." }, 404, origin);
  },
};
