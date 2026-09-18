const API_ORIGIN = "https://orvix-production.up.railway.app";

export async function onRequest(context) {
  const incoming = new URL(context.request.url);
  const path = Array.isArray(context.params.path) ? context.params.path.join("/") : context.params.path || "";
  const target = new URL(`/api/v1/${path}`, API_ORIGIN);
  target.search = incoming.search;

  const headers = new Headers(context.request.headers);
  headers.delete("host");
  headers.set("Origin", "https://orvix-ai.pages.dev");

  const body = context.request.method === "GET" || context.request.method === "HEAD" ? undefined : context.request.body;
  const upstream = await fetch(new Request(target, {
    method: context.request.method,
    headers,
    body,
    redirect: "follow",
  }));

  const responseHeaders = new Headers(upstream.headers);
  responseHeaders.set("Cache-Control", "no-store");
  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders,
  });
}
