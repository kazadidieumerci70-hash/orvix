export type ChatMessage = { role: "user" | "assistant"; content: string };
export type DocumentInfo = { id: string; number: number; name: string; size: number; created_at: string };
export type ConversationSummary = { id: string; title: string; updated_at: string };
export type ConversationDetail = ConversationSummary & { messages: ChatMessage[]; document_ids: string[] };
export type UserProfile = {
  id: string;
  phone: string;
  name: string;
  onboarding_completed: boolean;
  level: string;
  subjects: string[];
  goal: string;
  learning_style: string;
  difficulties: string;
  welcome_seen: boolean;
};
export type AuthResponse = { token: string; user: UserProfile; existing_account?: boolean };
export type RegistrationResponse = AuthResponse | { verification_required: true; email: string; message: string };
export type OnboardingPayload = {
  name: string;
  level: string;
  subjects: string[];
  goal: string;
  learning_style: string;
  difficulties: string;
};
export type CreditCosts = { chat: number; chat_with_documents: number; revision: number; quiz_short: number; quiz_long: number; exam_plan: number };
export type SubscriptionPlan = { id: string; name: string; tagline: string; monthly_price: number; annual_price: number; documents: number; documents_per_request: number; document_context_chars: number; document_sources: number; max_document_mb: number; max_document_pages: number; daily_credits: number; monthly_credits: number; daily_safety_limit: number; features: string[] };
export type SubscriptionStatus = { subscription: { plan_id: string; status: string; billing_cycle: "monthly" | "annual"; expires_at: string | null }; plan: SubscriptionPlan; credits_used_today: number; credits_used_month: number; credits_remaining: number; credits_limit: number; credit_period: "daily" | "monthly"; bonus_credits: number; daily_credits_remaining: number; credit_costs: CreditCosts };
export type ExamPlan = { title: string; readiness_score: number; summary: string; mastered: string[]; priorities: string[]; plan: { day: number; title: string; tasks: string[]; minutes: number }[]; first_questions: QuizQuestion[] };

const configuredUrl = import.meta.env.VITE_API_URL?.trim();
// In production the Pages Function proxies /api to the FastAPI service. This
// keeps auth and chat same-origin in the browser and avoids cross-origin fetch
// failures in embedded/mobile browsers.
const API_URL = (import.meta.env.DEV
  ? (configuredUrl || `http://${window.location.hostname}:8010`)
  : (configuredUrl || "https://orvix-production.up.railway.app")
).replace(/\/$/, "");
const TOKEN_KEY = "orvix_token";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function saveToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const token = getToken();
  let response: Response | undefined;
  for (let attempt = 0; attempt < 2; attempt += 1) {
    try {
      const headers = new Headers(options?.headers);
      if (token) headers.set("Authorization", `Bearer ${token}`);
      const language = localStorage.getItem("orvix_language");
      if (language) headers.set("X-Orvix-Language", language);
      response = await fetch(`${API_URL}${path}`, { ...options, headers, cache: "no-store" });
      if (![502, 503, 504].includes(response.status) || attempt === 1) break;
    } catch {
      if (attempt === 1) throw new Error("ORVIX est momentanément inaccessible. Vérifiez votre connexion puis réessayez.");
    }
    await new Promise((resolve) => window.setTimeout(resolve, 900));
  }
  if (!response) throw new Error("ORVIX est momentanément inaccessible. Vérifiez votre connexion puis réessayez.");
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    if (response.status === 401 && token) {
      clearToken();
      localStorage.removeItem("orvix_user");
      window.dispatchEvent(new Event("orvix-auth-expired"));
    }
    const detail = typeof payload?.detail === "string"
      ? payload.detail
      : Array.isArray(payload?.detail)
        ? payload.detail.map((item: { msg?: string }) => item?.msg).filter(Boolean).join(" ")
        : "ORVIX est momentanément indisponible. Réessayez dans quelques instants.";
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

export function register(phone: string, password: string) {
  return request<RegistrationResponse>("/api/v1/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ phone, password }),
  });
}

export function login(phone: string, password: string) {
  return request<AuthResponse>("/api/v1/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ phone, password }),
  });
}

export function verifyEmailRegistration(email: string, code: string) {
  return request<AuthResponse>("/api/v1/auth/register/verify", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, code }),
  });
}

export function requestPasswordReset(email: string) {
  return request<{ message: string }>("/api/v1/auth/password-reset/request", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
}

export function confirmPasswordReset(token: string, password: string) {
  return request<{ message: string }>("/api/v1/auth/password-reset/confirm", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token, password }),
  });
}

export function loginWithGoogle(credential: string) {
  return request<AuthResponse>("/api/v1/auth/google", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ credential }) });
}

export function me() {
  return request<UserProfile>("/api/v1/auth/me");
}

export function completeOnboarding(payload: OnboardingPayload) {
  return request<UserProfile>("/api/v1/auth/onboarding", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function markWelcomeSeen() {
  return request<UserProfile>("/api/v1/auth/welcome-seen", { method: "POST" });
}

export function getSubscriptionPlans() {
  return request<{ currency: string; annual_discount_percent: number; credit_costs: CreditCosts; plans: SubscriptionPlan[] }>("/api/v1/subscription/plans");
}

export function getSubscription() {
  return request<SubscriptionStatus>("/api/v1/subscription");
}

export function joinSubscriptionWaitlist(planId: "student" | "pro") {
  return request<{ joined: boolean; plan_id: string }>("/api/v1/subscription/waitlist", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ plan_id: planId }),
  });
}

export function createSubscriptionCheckout(planId: "student" | "pro", billingCycle: "monthly" | "annual", customerEmail: string, paymentMethod: "airtel_money" | "orange_money" | "mtn_money" | "card", customerPhone = "", customerCountry: "CD" | "CM" | "CI" = "CD") {
  return request<{ transaction_id: string; payment_url: string; simulation: boolean }>("/api/v1/subscription/checkout", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ plan_id: planId, billing_cycle: billingCycle, customer_email: customerEmail, payment_method: paymentMethod, customer_phone: customerPhone, customer_country: customerCountry }),
  });
}

export function sendChat(message: string, history: ChatMessage[], documentIds: string[], conversationId: string, signal?: AbortSignal) {
  const controller = new AbortController();
  let timedOut = false;
  const abortFromCaller = () => controller.abort();
  signal?.addEventListener("abort", abortFromCaller, { once: true });
  const timeout = window.setTimeout(() => { timedOut = true; controller.abort(); }, 42_000);
  return request<{ conversation_id: string; answer: string }>("/api/v1/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    signal: controller.signal,
    body: JSON.stringify({ conversation_id: conversationId, message, history, document_ids: documentIds }),
  }).catch((error) => {
    if (timedOut) {
      throw new Error("Orvix n’a pas reçu de réponse à temps. Vérifiez la connexion puis réessayez.");
    }
    if (signal?.aborted) throw new DOMException("Réponse arrêtée", "AbortError");
    throw error;
  }).finally(() => {
    window.clearTimeout(timeout);
    signal?.removeEventListener("abort", abortFromCaller);
  });
}

export function listConversations() {
  return request<{ conversations: ConversationSummary[] }>("/api/v1/conversations");
}

export function getConversation(conversationId: string) {
  return request<ConversationDetail>(`/api/v1/conversations/${conversationId}`);
}

export function createRevision(topic: string, documentIds: string[]) {
  return request<{ content: string }>("/api/v1/revision", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ topic, document_ids: documentIds }),
  });
}

export function createQuiz(topic: string, documentIds: string[], count = 5, quizType: "multiple_choice" | "traditional" = "multiple_choice") {
  return request<{ title: string; questions: QuizQuestion[] }>("/api/v1/quiz", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ topic, document_ids: documentIds, count, quiz_type: quizType }),
  });
}

export function createExamPlan(documentIds: string[], examDate: string, minutesPerDay: number, confidence: number, subject: string) {
  return request<ExamPlan>("/api/v1/exam-mode", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ document_ids: documentIds, exam_date: examDate, minutes_per_day: minutesPerDay, confidence, subject }),
  });
}

export async function exportQuizWord(title: string, questions: QuizQuestion[], quizType: "multiple_choice" | "traditional") {
  const headers = new Headers({ "Content-Type": "application/json" });
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${API_URL}/api/v1/quiz/export`, {
    method: "POST",
    headers,
    body: JSON.stringify({ title, questions, quiz_type: quizType }),
  });
  if (!response.ok) throw new Error("Impossible de créer le document Word.");
  return response.blob();
}

export type QuizQuestion = {
  question: string;
  choices: string[];
  answer_index: number;
  expected_answer: string;
  explanation: string;
};

export function listDocuments() {
  return request<{ documents: DocumentInfo[] }>("/api/v1/documents");
}

export function uploadDocuments(files: File[], onProgress?: (percent: number) => void) {
  const data = new FormData();
  files.forEach((file) => data.append("files", file));
  return new Promise<{ documents: DocumentInfo[] }>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_URL}/api/v1/documents`);
    const token = getToken();
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    const language = localStorage.getItem("orvix_language");
    if (language) xhr.setRequestHeader("X-Orvix-Language", language);
    xhr.upload.onprogress = (event) => { if (event.lengthComputable) onProgress?.(Math.max(1, Math.round((event.loaded / event.total) * 100))); };
    xhr.onerror = () => reject(new Error("Import impossible. Vérifiez votre connexion puis réessayez."));
    xhr.onload = () => {
      let result: unknown = null;
      try { result = xhr.responseText ? JSON.parse(xhr.responseText) : null; } catch { /* handled below */ }
      if (xhr.status < 200 || xhr.status >= 300) {
        const detail = typeof (result as { detail?: unknown } | null)?.detail === "string" ? (result as { detail: string }).detail : "Import impossible.";
        reject(new Error(detail)); return;
      }
      resolve(result as { documents: DocumentInfo[] });
    };
    xhr.send(data);
  });
}

export function deleteDocument(documentId: string) {
  return request<{ documents: DocumentInfo[] }>(`/api/v1/documents/${documentId}`, { method: "DELETE" });
}
