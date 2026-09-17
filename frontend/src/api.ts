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
export type AuthResponse = { token: string; user: UserProfile };
export type OnboardingPayload = {
  name: string;
  level: string;
  subjects: string[];
  goal: string;
  learning_style: string;
  difficulties: string;
};
export type SubscriptionPlan = { id: string; name: string; monthly_price: number; annual_price: number; documents: number; daily_requests: number; features: string[] };
export type SubscriptionStatus = { subscription: { plan_id: string; status: string; billing_cycle: "monthly" | "annual"; expires_at: string | null }; plan: SubscriptionPlan; requests_used_today: number; requests_remaining_today: number };
export type ExamPlan = { title: string; readiness_score: number; summary: string; mastered: string[]; priorities: string[]; plan: { day: number; title: string; tasks: string[]; minutes: number }[]; first_questions: QuizQuestion[] };

const configuredUrl = import.meta.env.VITE_API_URL?.trim();
const API_URL = (configuredUrl || (import.meta.env.DEV ? `http://${window.location.hostname}:8010` : "")).replace(/\/$/, "");
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
  const headers = new Headers(options?.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const language = localStorage.getItem("orvix_language");
  if (language) headers.set("X-Orvix-Language", language);

  const response = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    if (response.status === 401 && token) {
      clearToken();
      localStorage.removeItem("orvix_user");
      window.dispatchEvent(new Event("orvix-auth-expired"));
    }
    throw new Error(payload?.detail || "Le serveur Orvix est momentanément indisponible.");
  }
  return response.json() as Promise<T>;
}

export function register(phone: string, password: string) {
  return request<AuthResponse>("/api/v1/auth/register", {
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
  return request<{ currency: string; annual_discount_percent: number; plans: SubscriptionPlan[] }>("/api/v1/subscription/plans");
}

export function getSubscription() {
  return request<SubscriptionStatus>("/api/v1/subscription");
}

export function createSubscriptionCheckout(planId: "student" | "pro", billingCycle: "monthly" | "annual") {
  return request<{ transaction_id: string; payment_url: string; simulation: boolean }>("/api/v1/subscription/checkout", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ plan_id: planId, billing_cycle: billingCycle }),
  });
}

export function sendChat(message: string, history: ChatMessage[], documentIds: string[], conversationId: string) {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 42_000);
  return request<{ conversation_id: string; answer: string }>("/api/v1/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    signal: controller.signal,
    body: JSON.stringify({ conversation_id: conversationId, message, history, document_ids: documentIds }),
  }).catch((error) => {
    if (controller.signal.aborted) {
      throw new Error("Orvix n’a pas reçu de réponse à temps. Vérifiez la connexion puis réessayez.");
    }
    throw error;
  }).finally(() => window.clearTimeout(timeout));
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

export async function uploadDocuments(files: File[]) {
  const data = new FormData();
  files.forEach((file) => data.append("files", file));
  return request<{ documents: DocumentInfo[] }>("/api/v1/documents", { method: "POST", body: data });
}

export function deleteDocument(documentId: string) {
  return request<{ documents: DocumentInfo[] }>(`/api/v1/documents/${documentId}`, { method: "DELETE" });
}
