import { type CSSProperties, type ReactNode, FormEvent, useEffect, useRef, useState } from "react";
import {
  BookOpenText,
  CalendarDays,
  Check,
  CheckCircle2,
  Copy,
  Download,
  FileText,
  HelpCircle,
  Eye,
  EyeOff,
  LockKeyhole,
  Mail,
  Mic,
  Menu,
  MessageCircle,
  MessageCirclePlus,
  Moon,
  Plus,
  Send,
  Square,
  Settings,
  ShieldCheck,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  Trash2,
  UploadCloud,
  User,
  ArrowLeft,
  Bell,
  LibraryBig,
  ChevronRight,
  CreditCard,
  Crown,
  Globe,
  Info,
  LogOut,
  Palette,
  Pencil,
  Star,
  Target,
  X,
} from "lucide-react";
import {
  ChatMessage,
  ConversationSummary,
  DocumentInfo,
  ExamPlan,
  OnboardingPayload,
  QuizQuestion,
  SubscriptionPlan,
  SubscriptionStatus,
  UserProfile,
  clearToken,
  confirmPasswordReset,
  completeOnboarding,
  createQuiz,
  createExamPlan,
  createSubscriptionCheckout,
  createRevision,
  deleteDocument,
  exportQuizWord,
  getConversation,
  getSubscription,
  getSubscriptionPlans,
  joinSubscriptionWaitlist,
  login,
  loginWithGoogle,
  markWelcomeSeen,
  listConversations,
  listDocuments,
  me,
  register,
  requestPasswordReset,
  saveToken,
  sendChat,
  uploadDocuments,
  verifyEmailRegistration,
} from "./api";

type View = "chat" | "revision" | "quiz" | "exam" | "support" | "account";
declare global { interface Window { google?: any; } }
const nav = [
  { id: "chat" as View, label: "Chat", icon: MessageCircle },
  { id: "revision" as View, label: "Révision", icon: BookOpenText },
  { id: "quiz" as View, label: "Quiz", icon: HelpCircle },
  { id: "support" as View, label: "Supports", icon: FileText },
];
const navLabels: Record<string, Record<string, string>> = {
  Français: { chat: "Chat", revision: "Révision", quiz: "Quiz", support: "Supports" },
  English: { chat: "Chat", revision: "Review", quiz: "Quiz", support: "Documents" },
  Italiano: { chat: "Chat", revision: "Ripasso", quiz: "Quiz", support: "Documenti" },
  Español: { chat: "Chat", revision: "Repaso", quiz: "Quiz", support: "Documentos" },
};

function App() {
  const [user, setUser] = useState<UserProfile | null>(() => {
    try { const cached = localStorage.getItem("orvix_user"); return localStorage.getItem("orvix_token") && cached ? JSON.parse(cached) as UserProfile : null; } catch { return null; }
  });
  const [authChecked, setAuthChecked] = useState(false);
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [activeDocumentId, setActiveDocumentId] = useState("");
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeConversationId, setActiveConversationId] = useState(() => localStorage.getItem("orvix_active_conversation") || "");
  const [activeMessages, setActiveMessages] = useState<ChatMessage[]>([]);
  const [view, setView] = useState<View>(() => (localStorage.getItem("orvix_view") as View) || "chat");
  const [mobileNav, setMobileNav] = useState(false);
  const [accountPlanName, setAccountPlanName] = useState("Gratuit");
  const [maxDocumentMb, setMaxDocumentMb] = useState(10);
  const [maxDocumentPages, setMaxDocumentPages] = useState(100);
  const [theme, setTheme] = useState<"light" | "dark">(() => localStorage.getItem("orvix_theme") === "dark" ? "dark" : "light");
  const [language, setLanguage] = useState("Français");
  const openedFreshChat = useRef(false);
  // A late conversation fetch must never overwrite a support the user just chose.
  const conversationDocumentHydratedRef = useRef("");

  useEffect(() => {
    const authTimeout = window.setTimeout(() => setAuthChecked(true), 8000);
    me().then((profile) => { localStorage.setItem("orvix_user", JSON.stringify(profile)); setUser(profile); }).catch(() => undefined).finally(() => setAuthChecked(true));
    document.documentElement.dataset.textSize = localStorage.getItem("orvix_text_size") || "normal";
    document.documentElement.dataset.density = localStorage.getItem("orvix_density") || "comfortable";
    document.documentElement.dataset.animations = localStorage.getItem("orvix_animations") === "off" ? "off" : "on";
    return () => window.clearTimeout(authTimeout);
  }, []);

  useEffect(() => {
    const expireSession = () => setUser(null);
    window.addEventListener("orvix-auth-expired", expireSession);
    return () => window.removeEventListener("orvix-auth-expired", expireSession);
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("orvix_theme", theme);
  }, [theme]);
  useEffect(() => {
    const viewport = window.visualViewport;
    const root = document.documentElement;
    const syncMobileViewport = () => {
      if (!window.matchMedia("(max-width: 900px)").matches) {
        root.removeAttribute("data-mobile-keyboard");
        return;
      }
      const top = viewport?.offsetTop || 0;
      const height = viewport?.height || window.innerHeight;
      const keyboardOpen = window.innerHeight - height > 120;
      root.style.setProperty("--orvix-visual-top", `${top}px`);
      root.style.setProperty("--orvix-visual-height", `${height}px`);
      root.style.setProperty("--orvix-welcome-top", `${top + Math.max(118, height * 0.34)}px`);
      root.dataset.mobileKeyboard = keyboardOpen ? "open" : "closed";
    };
    syncMobileViewport();
    viewport?.addEventListener("resize", syncMobileViewport);
    viewport?.addEventListener("scroll", syncMobileViewport);
    window.addEventListener("resize", syncMobileViewport);
    return () => {
      viewport?.removeEventListener("resize", syncMobileViewport);
      viewport?.removeEventListener("scroll", syncMobileViewport);
      window.removeEventListener("resize", syncMobileViewport);
    };
  }, []);
  useEffect(() => {
    localStorage.setItem("orvix_language", language);
    document.documentElement.lang = language === "English" ? "en" : language === "Italiano" ? "it" : language === "Español" ? "es" : "fr";
  }, [language]);

  useEffect(() => {
    localStorage.setItem("orvix_view", view);
    if (activeConversationId) localStorage.setItem("orvix_active_conversation", activeConversationId);
    else localStorage.removeItem("orvix_active_conversation");
    if (user) {
      const accountKey = encodeURIComponent(user.phone || user.name);
      if (activeConversationId) localStorage.setItem(`orvix_active_conversation_${accountKey}`, activeConversationId);
      else localStorage.removeItem(`orvix_active_conversation_${accountKey}`);
    }
    if (activeDocumentId) localStorage.setItem("orvix_active_document", activeDocumentId);
    else localStorage.removeItem("orvix_active_document");
  }, [view, activeConversationId, activeDocumentId, user?.phone]);

  useEffect(() => {
    const savedDocument = localStorage.getItem("orvix_active_document");
    if (savedDocument) setActiveDocumentId(savedDocument);
  }, []);

  useEffect(() => {
    if (!user?.onboarding_completed || !activeConversationId) return;
    const accountKey = encodeURIComponent(user.phone || user.name);
    const messageKey = `orvix_messages_${accountKey}_${activeConversationId}`;
    const cachedMessages = localStorage.getItem(messageKey);
    getConversation(activeConversationId).then((conversation) => {
      setActiveMessages(conversation.messages);
      if (conversationDocumentHydratedRef.current !== conversation.id) {
        setActiveDocumentId(conversation.document_ids.length > 1 ? "__all__" : conversation.document_ids[0] || "");
        conversationDocumentHydratedRef.current = conversation.id;
      }
      localStorage.setItem(messageKey, JSON.stringify(conversation.messages));
    }).catch(() => {
      if (cachedMessages) {
        try { setActiveMessages(JSON.parse(cachedMessages) as ChatMessage[]); return; } catch { localStorage.removeItem(messageKey); }
      }
      setActiveConversationId("");
      setActiveMessages([]);
    });
  }, [user?.onboarding_completed, activeConversationId]);

  useEffect(() => {
    if (!user || !activeConversationId || !activeMessages.length) return;
    const accountKey = encodeURIComponent(user.phone || user.name);
    localStorage.setItem(`orvix_messages_${accountKey}_${activeConversationId}`, JSON.stringify(activeMessages));
  }, [user?.phone, user?.name, activeConversationId, activeMessages]);

  useEffect(() => {
    if (!user?.onboarding_completed) return;
    if (!openedFreshChat.current) {
      openedFreshChat.current = true;
      setView("chat");
    }
    const accountKey = encodeURIComponent(user.phone || user.name);
    const cachedConversations = localStorage.getItem(`orvix_conversations_${accountKey}`);
    const cachedActiveConversation = localStorage.getItem(`orvix_active_conversation_${accountKey}`);
    if (cachedConversations) {
      try { setConversations(JSON.parse(cachedConversations) as ConversationSummary[]); } catch { localStorage.removeItem(`orvix_conversations_${accountKey}`); }
    }
    if (cachedActiveConversation && cachedActiveConversation !== activeConversationId) setActiveConversationId(cachedActiveConversation);
    listDocuments().then((result) => setDocuments(result.documents)).catch(() => undefined);
    listConversations().then((result) => {
      const serverIds = new Set(result.conversations.map((item) => item.id));
      const merged = [...result.conversations, ...((cachedConversations ? JSON.parse(cachedConversations) as ConversationSummary[] : []).filter((item) => !serverIds.has(item.id)))];
      setConversations(merged);
      localStorage.setItem(`orvix_conversations_${accountKey}`, JSON.stringify(merged));
    }).catch(() => undefined);
    getSubscription().then((result) => { setAccountPlanName(result.plan.name); setMaxDocumentMb(result.plan.max_document_mb || 10); setMaxDocumentPages(result.plan.max_document_pages || 100); }).catch(() => undefined);
  }, [user?.onboarding_completed, user?.phone]);

  if (!authChecked) {
    return <div className="auth-loading">ORVIX</div>;
  }

  if (!user) {
    return <AuthView onAuthenticated={setUser} />;
  }

  if (!user.onboarding_completed) {
    if (!user.welcome_seen) {
      return <FirstWelcomeView onContinue={async () => {
        try {
          const profile = await markWelcomeSeen();
          localStorage.setItem("orvix_user", JSON.stringify(profile));
          setUser(profile);
        } catch {
          const profile = { ...user, welcome_seen: true };
          localStorage.setItem("orvix_user", JSON.stringify(profile));
          setUser(profile);
        }
      }} />;
    }
    return <OnboardingView user={user} onCompleted={(profile) => { localStorage.setItem("orvix_user", JSON.stringify(profile)); setUser(profile); }} onLogout={() => { clearToken(); localStorage.removeItem("orvix_user"); setUser(null); }} />;
  }

  const activeDocumentIds = activeDocumentId === "__all__"
    ? documents.map((document) => document.id)
    : activeDocumentId && documents.some((document) => document.id === activeDocumentId) ? [activeDocumentId] : [];

  function newChat() {
    conversationDocumentHydratedRef.current = "";
    setActiveConversationId("");
    setActiveMessages([]);
    setView("chat");
  }

  async function openConversation(conversationId: string) {
    try {
      const conversation = await getConversation(conversationId);
      conversationDocumentHydratedRef.current = conversation.id;
      setActiveConversationId(conversation.id);
      setActiveMessages(conversation.messages);
      setActiveDocumentId(conversation.document_ids.length > 1 ? "__all__" : conversation.document_ids[0] || "");
      setView("chat");
      setMobileNav(false);
    } catch {
      setActiveConversationId("");
      setActiveMessages([]);
    }
  }

  async function refreshConversations() {
    const result = await listConversations();
    setConversations(result.conversations);
    if (user) localStorage.setItem(`orvix_conversations_${encodeURIComponent(user.phone || user.name)}`, JSON.stringify(result.conversations));
  }

  function selectView(nextView: View) {
    setView(nextView);
    setMobileNav(false);
  }

  return (
    <div className={`app-shell theme-${theme}`}>
      <aside className={`sidebar menu-v2 ${mobileNav ? "open" : ""}`}>
        <div className="brand sidebar-brand"><img className="brand-logo" src="/orvix-logo-transparent.png" alt="Logo Orvix" /><span>ORVIX</span><button className="sidebar-menu-button" onClick={() => setMobileNav((open) => !open)} aria-label="Ouvrir le menu"><Menu size={17} /></button></div>
        <button className="close-nav" onClick={() => setMobileNav(false)} aria-label="Fermer le menu"><X /></button>
        <nav>
          {nav.map(({ id, label, icon: Icon }) => (
            <button key={id} className={view === id ? "nav-item active" : "nav-item"} onClick={() => selectView(id)}>
              <Icon size={21} /><span>{navLabels[language]?.[id] || label}</span>
            </button>
          ))}
        </nav>
        <section className="recents">
          <div className="recents-head"><h3>DISCUSSIONS</h3><button onClick={newChat}>+</button></div>
          <div className="recents-list">
            <button className={!activeConversationId ? "conversation-link active" : "conversation-link"} onClick={newChat}>Nouvelle discussion</button>
            {conversations.map((item) => <button key={item.id} className={activeConversationId === item.id ? "conversation-link active" : "conversation-link"} onClick={() => openConversation(item.id)}>{item.title}</button>)}
          </div>
        </section>
        <div className="sidebar-bottom">
          <button className={`profile-card account-button ${view === "account" ? "active" : ""}`} onClick={() => selectView("account")} aria-label="Ouvrir mon compte"><span className="avatar">{user.name.slice(0, 1).toUpperCase()}</span><span><strong>{user.name}</strong><small>Forfait {accountPlanName}</small></span><span className="profile-caret">⌃</span></button>
        </div>
      </aside>

      {mobileNav && <button className="backdrop" onClick={() => setMobileNav(false)} aria-label="Fermer le menu" />}
      <main className={`main-content ${view === "account" ? "account-scroll" : ""} ${view === "chat" ? "chat-main" : ""} ${view === "revision" ? "revision-main" : ""} ${view === "quiz" ? "quiz-main" : ""} ${view === "support" ? "support-main" : ""}`}>
        <div className="page-actions">
          <button className="mobile-menu" onClick={() => setMobileNav(true)} aria-label="Ouvrir le menu"><Menu /></button>
          {view === "chat" && <label className="top-document-selector"><select aria-label="Mode de réponse et support utilisé" value={activeDocumentId} onChange={(event) => setActiveDocumentId(event.target.value)}><option value="">Question libre</option><option value="__all__">Tous les documents</option>{documents.map((doc) => <option key={doc.id} value={doc.id}>Document {doc.number} · {doc.name}</option>)}</select></label>}
          {view === "revision" && <div className="top-view-label" aria-label="Page Révision de cours">Révision de cours</div>}
          {view === "quiz" && <div className="top-view-label" aria-label="Page Quiz de cours">Quiz de cours</div>}
          {view === "support" && <div className="top-view-label" aria-label="Page Supports de cours">Supports de cours</div>}
          <div className="top-actions-right"><button className="top-new-conversation-button" aria-label="Nouvelle discussion" onClick={newChat}><MessageCirclePlus size={22} /></button></div>
        </div>
        {view === "chat" && <ChatView language={language} documents={documents} onDocumentsChange={setDocuments} activeDocumentId={activeDocumentId} onActiveDocumentChange={setActiveDocumentId} documentIds={activeDocumentIds} conversationId={activeConversationId} onConversationChange={setActiveConversationId} messages={activeMessages} onMessagesChange={setActiveMessages} onSaved={refreshConversations} />}
        {view === "revision" && <RevisionView documents={documents} activeDocumentId={activeDocumentId} onActiveDocumentChange={setActiveDocumentId} documentIds={activeDocumentIds} />}
        {view === "quiz" && <QuizView documents={documents} activeDocumentId={activeDocumentId} onActiveDocumentChange={setActiveDocumentId} documentIds={activeDocumentIds} />}
        {view === "support" && <SupportView documents={documents} onDocumentsChange={setDocuments} activeDocumentId={activeDocumentId} onActiveDocumentChange={setActiveDocumentId} maxDocumentMb={maxDocumentMb} maxDocumentPages={maxDocumentPages} />}
        {view === "account" && <AccountView user={user} onSaved={(profile) => { localStorage.setItem("orvix_user", JSON.stringify(profile)); setUser(profile); }} documentCount={documents.length} conversationCount={conversations.length} theme={theme} onThemeChange={() => setTheme((current) => current === "dark" ? "light" : "dark")} language={language} onLanguageChange={setLanguage} onLogout={() => { clearToken(); localStorage.removeItem("orvix_user"); setUser(null); }} />}
      </main>
    </div>
  );
}

function FirstWelcomeView({ onContinue }: { onContinue: () => Promise<void> }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  async function continueToProfile() {
    setLoading(true); setError("");
    try { await onContinue(); }
    catch (e) { setError(e instanceof Error ? e.message : "Impossible de continuer."); setLoading(false); }
  }
  return <main className="first-welcome-page"><section className="first-welcome-card">
    <div className="welcome-brand"><img src="/orvix-logo-transparent.png" alt="Logo Orvix" /><span>ORVIX</span></div>
    <h1>Bonjour, je suis ORVIX.</h1>
    <p>Je suis là pour t’aider à comprendre tes cours, tes documents et à avancer plus facilement.</p>
    <p className="welcome-callout"><strong>Pose tes questions, je t’accompagne.</strong></p>
    {error && <p className="error-banner">{error}</p>}
    <button onClick={continueToProfile} disabled={loading}>{loading ? "Préparation…" : "Continuer"}<span>→</span></button>
  </section></main>;
}

function AppSettingsView() {
  const [textSize, setTextSize] = useState(localStorage.getItem("orvix_text_size") || "normal");
  const [density, setDensity] = useState(localStorage.getItem("orvix_density") || "comfortable");
  const [animations, setAnimations] = useState(localStorage.getItem("orvix_animations") !== "off");
  const [saved, setSaved] = useState(false);

  function saveSettings() {
    localStorage.setItem("orvix_text_size", textSize);
    localStorage.setItem("orvix_density", density);
    localStorage.setItem("orvix_animations", animations ? "on" : "off");
    document.documentElement.dataset.textSize = textSize;
    document.documentElement.dataset.density = density;
    document.documentElement.dataset.animations = animations ? "on" : "off";
    setSaved(true);
    window.setTimeout(() => setSaved(false), 2500);
  }

  return <section className="appearance-settings">
    <div className="settings-form general-settings">
      <section className="setting-group full"><div><h2>Taille du texte</h2><p>Modifie la taille générale des textes de l’interface.</p></div><div className="setting-options">{[["small", "Petite"], ["normal", "Normale"], ["large", "Grande"]].map(([value, label]) => <button key={value} className={textSize === value ? "selected" : ""} onClick={() => { setTextSize(value); setSaved(false); }}>{label}</button>)}</div></section>
      <section className="setting-group full"><div><h2>Disposition</h2><p>Choisis l’espacement des menus et des éléments.</p></div><div className="setting-options">{[["compact", "Compacte"], ["comfortable", "Confortable"]].map(([value, label]) => <button key={value} className={density === value ? "selected" : ""} onClick={() => { setDensity(value); setSaved(false); }}>{label}</button>)}</div></section>
      <section className="setting-group full"><div><h2>Animations</h2><p>Active ou réduit les mouvements visuels dans l’application.</p></div><button className={`setting-toggle ${animations ? "on" : ""}`} onClick={() => { setAnimations((current) => !current); setSaved(false); }} aria-pressed={animations}><span />{animations ? "Activées" : "Désactivées"}</button></section>
      {saved && <p className="settings-success full"><CheckCircle2 size={19} />Les paramètres ont été enregistrés.</p>}
      <div className="settings-validation full"><span>Les modifications sont conservées sur cet appareil.</span><button onClick={saveSettings}><Check size={19} />Enregistrer les réglages</button></div>
    </div>
  </section>;
}

function AccountView({ user, onSaved, documentCount, conversationCount, theme, onThemeChange, language, onLanguageChange, onLogout }: { user: UserProfile; onSaved: (user: UserProfile) => void; documentCount: number; conversationCount: number; theme: "light" | "dark"; onThemeChange: () => void; language: string; onLanguageChange: (language: string) => void; onLogout: () => void }) {
  const [form, setForm] = useState<OnboardingPayload>({
    name: user.name,
    level: user.level,
    subjects: user.subjects,
    goal: user.goal,
    learning_style: user.learning_style || styleOptions[0],
    difficulties: user.difficulties,
  });
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [plans, setPlans] = useState<SubscriptionPlan[]>([]);
  const [plansLoading, setPlansLoading] = useState(true);
  const [plansError, setPlansError] = useState("");
  const [subscriptionError, setSubscriptionError] = useState("");
  const [subscription, setSubscription] = useState<SubscriptionStatus | null>(null);
  const [billingCycle, setBillingCycle] = useState<"monthly" | "annual">("monthly");
  const [settingsSection, setSettingsSection] = useState<"overview" | "profile" | "subscription" | "appearance" | "security" | "notifications" | "language" | "help" | "about">("overview");
  const [securityAlerts, setSecurityAlerts] = useState(true);
  const [emailNotifications, setEmailNotifications] = useState(true);
  const [waitlistedPlans, setWaitlistedPlans] = useState<Set<string>>(new Set());
  const [paymentLoading, setPaymentLoading] = useState("");

  useEffect(() => {
    void loadSubscriptionData();
  }, []);

  async function loadSubscriptionData() {
    setPlansLoading(true);
    setPlansError("");
    setSubscriptionError("");
    await Promise.all([
      getSubscriptionPlans().then((result) => {
        setPlans(result.plans);
        if (!result.plans.length) setPlansError("Aucun forfait n’est disponible pour le moment. Réessaie dans quelques instants.");
      }).catch(() => setPlansError("Impossible de charger les forfaits pour le moment. Réessaie dans quelques instants.")),
      getSubscription().then(setSubscription).catch(() => setSubscriptionError("Impossible de vérifier ton abonnement actuel. Réessaie avant de choisir un forfait.")),
    ]);
    setPlansLoading(false);
  }

  function update<K extends keyof OnboardingPayload>(key: K, value: OnboardingPayload[K]) {
    setForm((current) => ({ ...current, [key]: value }));
    setMessage("");
  }

  function toggleSubject(subject: string) {
    update("subjects", form.subjects.includes(subject)
      ? form.subjects.filter((item) => item !== subject)
      : [...form.subjects, subject]);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (loading) return;
    if (!form.name.trim() || !form.level.trim()) { setError("Indique au moins ton nom et ton niveau pour continuer."); return; }
    setLoading(true);
    setError("");
    setMessage("");
    try {
      const savedUser = await completeOnboarding(form);
      onSaved(savedUser);
      setMessage("Tes préférences ont bien été enregistrées. Orvix adaptera désormais ses réponses à cette sélection.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Impossible d'enregistrer les paramètres.");
    } finally {
      setLoading(false);
    }
  }

  async function joinWaitlist(planId: "student" | "pro") {
    setError("");
    try {
      await joinSubscriptionWaitlist(planId);
      setWaitlistedPlans((current) => new Set(current).add(planId));
      setMessage(`Vous serez prévenu dès que le forfait ${planId === "student" ? "Étudiant" : "Pro"} sera disponible.`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Impossible de rejoindre la liste d’attente.");
    }
  }

  async function startCheckout(planId: "student" | "pro") {
    if (paymentLoading) return;
    if (planId === "student" && subscription?.plan.id === "pro") {
      setError("Ton forfait Pro est encore actif. Le forfait Étudiant sera disponible après son expiration.");
      return;
    }
    const accountEmail = user.phone.includes("@") ? user.phone : "";
    const customerEmail = accountEmail || window.prompt("Quelle adresse e-mail utiliser pour le reçu de paiement ?")?.trim() || "";
    if (!customerEmail && !accountEmail) return;
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(customerEmail)) {
      setError("Indique une adresse e-mail valide pour le paiement.");
      return;
    }
    setPaymentLoading(planId);
    setError("");
    setMessage("");
    try {
      const result = await createSubscriptionCheckout(planId, billingCycle, customerEmail);
      if (result.payment_url) {
        window.location.assign(result.payment_url);
      } else if (result.simulation) {
        const refreshed = await getSubscription();
        setSubscription(refreshed);
        setMessage("Ton abonnement a été activé.");
      } else {
        throw new Error("Le lien de paiement n’a pas été généré.");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Impossible de démarrer le paiement.");
    } finally {
      setPaymentLoading("");
    }
  }

  function confirmLogout() {
    const confirmed = window.confirm(
      "Voulez-vous vraiment vous déconnecter d’ORVIX ?\n\nVos documents et vos conversations resteront enregistrés dans votre compte."
    );
    if (confirmed) onLogout();
  }

  const planName = subscription?.plan.name || "Gratuit";
  const english = language === "English";
  const tx = (fr: string, en: string) => language === "English" ? en : fr;
  return <section className="settings-page profile-page">
    {settingsSection === "overview" && <>
      <header className="profile-heading"><div><h1>{tx("Profil", "Profile")}</h1><p>{tx("Gérez votre compte et vos préférences", "Manage your account and preferences")}</p></div><Settings size={25} /></header>
      <section className="profile-hero-card">
        <div className="profile-hero-main"><div className="profile-avatar-large"><User size={58} /><button type="button" aria-label="Modifier le profil" onClick={() => setSettingsSection("profile")}><Pencil size={17} /></button></div><h2>{user.name}</h2><p>{user.phone}</p><span className="profile-plan"><Crown size={16} />{planName}</span></div>
        <div className="profile-stats"><div><strong>{conversationCount}</strong><span>Conversations</span></div><div><strong>{documentCount}</strong><span>Documents</span></div><div><strong>0</strong><span>Favoris</span></div></div>
      </section>
      <ProfileMenuGroup title={tx("Compte", "Account")}><button onClick={() => setSettingsSection("profile")}><User /><span>{tx("Informations personnelles", "Personal information")}</span><ChevronRight /></button><button onClick={() => setSettingsSection("security")}><ShieldCheck /><span>{tx("Sécurité", "Security")}</span><ChevronRight /></button><button onClick={() => setSettingsSection("subscription")}><CreditCard /><span>{tx("Abonnement", "Subscription")}</span><small>{planName}</small><ChevronRight /></button><button onClick={() => setSettingsSection("notifications")}><Bell /><span>{tx("Notifications", "Notifications")}</span><ChevronRight /></button></ProfileMenuGroup>
      <ProfileMenuGroup title={tx("Préférences", "Preferences")}><button type="button" onClick={onThemeChange}><Moon /><span>{tx("Mode sombre", "Dark mode")}</span><i className={`profile-toggle ${theme === "dark" ? "on" : ""}`}><b /></i></button><button type="button" onClick={() => setSettingsSection("language")}><Globe /><span>{tx("Langue", "Language")}</span><small>{language}</small><ChevronRight /></button><button onClick={() => setSettingsSection("appearance")}><Palette /><span>{tx("Apparence", "Appearance")}</span><ChevronRight /></button></ProfileMenuGroup>
      <ProfileMenuGroup title={tx("Autres", "Other")}><button type="button" onClick={() => setSettingsSection("help")}><HelpCircle /><span>{tx("Aide et support", "Help and support")}</span><ChevronRight /></button><button type="button" onClick={() => setSettingsSection("about")}><Info /><span>{tx("À propos d’Orvix", "About Orvix")}</span><ChevronRight /></button><button type="button" className="profile-logout" onClick={confirmLogout}><LogOut /><span>{tx("Se déconnecter", "Log out")}</span><ChevronRight /></button></ProfileMenuGroup>
    </>}
    {settingsSection !== "overview" && <header className={`profile-detail-heading ${settingsSection === "profile" ? "personal-details-heading" : ""}`}><button type="button" onClick={() => setSettingsSection("overview")}><ArrowLeft /></button><div><span>PROFIL</span><h1>{settingsSection === "profile" ? "Informations personnelles" : settingsSection === "subscription" ? "Abonnement" : settingsSection === "security" ? "Sécurité" : settingsSection === "notifications" ? "Notifications" : settingsSection === "language" ? "Langue" : settingsSection === "help" ? "Aide et support" : settingsSection === "about" ? "À propos d’Orvix" : "Apparence"}</h1></div></header>}
    {settingsSection === "profile" && <form className="settings-form" onSubmit={submit}>
      <div className="settings-field"><label htmlFor="settings-name">Nom</label><input id="settings-name" value={form.name} onChange={(event) => update("name", event.target.value)} /></div>
      <div className="settings-field"><label htmlFor="settings-level">Niveau ou classe</label><input id="settings-level" value={form.level} onChange={(event) => update("level", event.target.value)} /></div>
      <div className="settings-field full"><label>Matières à privilégier</label><div className="chip-grid">{subjectOptions.map((subject) => <button type="button" key={subject} className={form.subjects.includes(subject) ? "selected" : ""} onClick={() => toggleSubject(subject)}><Check size={16} />{subject}</button>)}</div></div>
      <div className="settings-field full"><label>Façon d’apprendre préférée</label><div className="chip-grid">{styleOptions.map((style) => <button type="button" key={style} className={form.learning_style === style ? "selected" : ""} onClick={() => update("learning_style", style)}><CheckCircle2 size={16} />{style}</button>)}</div></div>
      <div className="settings-field full"><label htmlFor="settings-goal">Objectif</label><textarea id="settings-goal" value={form.goal} onChange={(event) => update("goal", event.target.value)} /></div>
      <div className="settings-field full"><label htmlFor="settings-difficulties">Difficultés particulières</label><textarea id="settings-difficulties" value={form.difficulties} onChange={(event) => update("difficulties", event.target.value)} placeholder="Facultatif" /></div>
      {error && <p className="error-banner full">{error}</p>}
      {message && <p className="settings-success full"><CheckCircle2 size={19} />{message}</p>}
      <div className="settings-validation full"><span>Les changements ne seront appliqués qu’après validation.</span><button disabled={loading || !form.name.trim() || !form.level.trim() || !form.goal.trim()}><Check size={19} />{loading ? "Validation…" : "Valider ma sélection"}</button></div>
    </form>}
    {settingsSection === "security" && <section className="settings-form profile-simple-panel"><section className="setting-group full"><div><h2>Protection du compte</h2><p>Gère les alertes importantes liées à la sécurité de ton compte.</p></div><button className={`setting-toggle ${securityAlerts ? "on" : ""}`} onClick={() => setSecurityAlerts((value) => !value)} aria-pressed={securityAlerts}><span />{securityAlerts ? "Activées" : "Désactivées"}</button></section><section className="setting-group full"><div><h2>Mot de passe</h2><p>Pour modifier ton mot de passe, utilise la procédure de récupération depuis l’écran de connexion.</p></div><button type="button" className="setting-action" onClick={() => alert("Un lien de récupération sera bientôt disponible.")}>Gérer</button></section></section>}
    {settingsSection === "notifications" && <section className="settings-form profile-simple-panel"><section className="setting-group full"><div><h2>Notifications par e-mail</h2><p>Reçois les informations importantes concernant ton compte et tes abonnements.</p></div><button className={`setting-toggle ${emailNotifications ? "on" : ""}`} onClick={() => setEmailNotifications((value) => !value)} aria-pressed={emailNotifications}><span />{emailNotifications ? "Activées" : "Désactivées"}</button></section><section className="setting-group full"><div><h2>Réponses et quiz</h2><p>Les notifications liées aux générations terminées seront disponibles prochainement.</p></div><span className="setting-status">Bientôt</span></section></section>}
    {settingsSection === "language" && <section className="settings-form profile-simple-panel"><section className="setting-group full"><div><h2>Langue de l’interface</h2><p>Le français est disponible maintenant. Les autres langues arrivent bientôt.</p></div><div className="setting-options">{["Français", "English", "Italiano", "Español"].map((item) => <button type="button" key={item} className={language === item ? "selected" : ""} disabled={item !== "Français"} onClick={() => item === "Français" && onLanguageChange("Français")}>{item}{item !== "Français" && <small>Bientôt</small>}</button>)}</div></section></section>}
    {settingsSection === "help" && <section className="settings-form profile-simple-panel"><section className="setting-group full"><div><h2>Besoin d’aide ?</h2><p>Importe un document, sélectionne-le puis pose ta question à ORVIX. Si un problème survient, actualise la page puis réessaie.</p></div></section></section>}
    {settingsSection === "about" && <section className="settings-form profile-simple-panel"><section className="setting-group full"><div><h2>À propos d’ORVIX</h2><p>ORVIX est une intelligence artificielle créée par DIEU MERCI KAZADI pour aider les étudiants à comprendre leurs documents.</p></div></section></section>}
    {settingsSection === "subscription" && <section className="subscription-panel">
      <div className="subscription-heading"><div><span>ABONNEMENT · CRÉDITS ORVIX</span><h2>Choisis ton forfait ORVIX</h2><p>Choisis l’offre qui correspond à tes besoins.</p></div><div className="billing-switch"><button className={billingCycle === "monthly" ? "active" : ""} onClick={() => setBillingCycle("monthly")}>Mensuel</button><button className={billingCycle === "annual" ? "active" : ""} onClick={() => setBillingCycle("annual")}>Annuel <small>2 mois offerts</small></button></div></div>
      {subscription && <div className="quota-summary"><span>Forfait actuel : <strong>{subscription.plan.name}</strong></span><span>Crédits disponibles {subscription.credit_period === "daily" ? "aujourd’hui" : "ce mois"} : <strong>{subscription.credits_remaining}/{subscription.credits_limit}</strong></span><span>{subscription.credit_period === "daily" ? "Renouvelés chaque jour" : "Renouvelés chaque mois"}</span><span>Documents autorisés : <strong>{subscription.plan.documents}</strong></span></div>}
      {subscription && <div className="quota-progress"><span style={{ width: `${Math.min(100, ((subscription.credits_limit - subscription.credits_remaining) / Math.max(1, subscription.credits_limit)) * 100)}%` }} /></div>}
      {message && settingsSection === "subscription" && <p className="settings-success"><CheckCircle2 size={19} />{message}</p>}
      {error && settingsSection === "subscription" && <p className="subscription-error">{error}</p>}
      {plansLoading && <p role="status" aria-live="polite">Chargement des forfaits et de ton abonnement…</p>}
      {!plansLoading && (plansError || subscriptionError) && <div className="subscription-load-error" role="alert"><p>{plansError || subscriptionError}</p><button type="button" onClick={() => void loadSubscriptionData()}>Réessayer</button></div>}
      <div className="plans-grid">{plans.map((plan) => {
        const active = subscription?.plan.id === plan.id;
        const downgradeBlocked = subscription?.plan.id === "pro" && plan.id === "student";
        const price = billingCycle === "annual" ? plan.annual_price : plan.monthly_price;
        return <article key={plan.id} className={`plan-card ${active ? "current" : ""} ${plan.id === "student" ? "recommended" : ""}`}>
          {plan.id === "student" && <em>RECOMMANDÉ</em>}<h3>{plan.name}</h3><p className="plan-tagline">{plan.tagline}</p><p className="plan-price"><strong>{price === 0 ? "Gratuit" : `${price.toFixed(2).replace(".", ",")} $`}</strong><small>{price > 0 ? (billingCycle === "annual" ? "/an" : "/mois") : ""}</small></p>{billingCycle === "annual" && price > 0 && <p className="annual-comparison"><s>{(plan.monthly_price * 12).toFixed(2).replace(".", ",")} $</s><span>2 mois offerts</span></p>}
          <ul><li><Check size={17} />{plan.id === "free" ? `Environ ${plan.daily_credits} crédits/jour` : plan.id === "student" ? "Environ 1 500–2 000 crédits/mois" : "Environ 4 000–6 000 crédits/mois"}</li><li><Check size={17} />{plan.documents} document{plan.documents > 1 ? "s" : ""}</li>{plan.features.map((feature) => <li key={feature}><Check size={17} />{feature}</li>)}</ul>
          {downgradeBlocked && <p role="note">Tu conserves tes avantages Pro{subscription?.subscription.expires_at ? ` jusqu’au ${new Date(subscription.subscription.expires_at).toLocaleDateString("fr-FR")}` : ""}. Tu pourras choisir Étudiant après son expiration.</p>}
          <button type="button" disabled={plansLoading || !!subscriptionError || !subscription || active || downgradeBlocked || plan.id === "free" || !!paymentLoading} onClick={() => !active && !downgradeBlocked && plan.id !== "free" && startCheckout(plan.id as "student" | "pro")}>{active ? "Forfait actuel" : downgradeBlocked ? "Disponible après Pro" : plan.id === "free" ? "Gratuit pour toujours" : paymentLoading === plan.id ? "Ouverture du paiement…" : "Payer maintenant"}</button>
        </article>;
      })}</div>
    </section>}
    {settingsSection === "appearance" && <AppSettingsView />}
  </section>;
}

function ProfileMenuGroup({ title, children }: { title: string; children: ReactNode }) {
  return <section className="profile-menu-group"><h2>{title}</h2><div>{children}</div></section>;
}

const subjectOptions = ["Maths", "Physique", "Chimie", "SVT", "Français", "Anglais", "Histoire", "Informatique", "Autres"];
const styleOptions = ["Explications simples", "Exemples concrets", "Questions pas a pas", "Fiches courtes"];
function OnboardingView({ user, onCompleted, onLogout }: { user: UserProfile; onCompleted: (user: UserProfile) => void; onLogout: () => void }) {
  const [form, setForm] = useState<OnboardingPayload>({
    name: user.name === "Etudiant" ? "" : user.name,
    level: "",
    subjects: [],
    goal: "",
    learning_style: styleOptions[0],
    difficulties: "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [step, setStep] = useState(0);
  const [customSubject, setCustomSubject] = useState("");

  function update<K extends keyof OnboardingPayload>(key: K, value: OnboardingPayload[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function toggleSubject(subject: string) {
    const subjects = form.subjects.includes(subject)
      ? form.subjects.filter((item) => item !== subject)
      : [...form.subjects, subject];
    update("subjects", subjects);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (loading) return;
    if (step === 0 && !form.name.trim()) { setError("Écris ton nom pour continuer."); return; }
    if (step === 1 && !form.level.trim()) { setError("Indique ton niveau ou ta classe pour continuer."); return; }
    if (step === 2 && !form.subjects.length) { setError("Choisis au moins une matière pour continuer."); return; }
    if (step === 2 && form.subjects.includes("Autres") && !customSubject.trim()) { setError("Écris la matière que tu veux ajouter."); return; }
    if (step === 3 && !form.goal.trim()) { setError("Indique ton objectif pour continuer."); return; }
    if (step < 5) { setError(""); setStep((value) => value + 1); return; }
    if (!form.name.trim() || !form.level.trim() || !form.goal.trim()) return;
    const subjects = form.subjects.filter((subject) => subject !== "Autres");
    if (customSubject.trim()) subjects.push(customSubject.trim());
    setLoading(true);
    setError("");
    try {
      onCompleted(await completeOnboarding({ ...form, subjects, goal: form.goal.trim() || "À définir" }));
    } catch (e) {
      if (e instanceof Error && e.message.toLowerCase().includes("utilisateur introuvable")) {
        clearToken();
        localStorage.removeItem("orvix_user");
        onLogout();
        return;
      }
      setError(e instanceof Error ? e.message : "Impossible d'enregistrer le profil.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="auth-page onboarding-page">
      <section className="onboarding-panel">
        <div className="brand auth-brand"><img className="brand-logo" src="/orvix-logo-transparent.png" alt="Logo Orvix" /><span>ORVIX</span></div>
        <div className="onboarding-steps" aria-label={`Étape ${Math.min(step + 1, 5)} sur 5`}>{[0, 1, 2, 3, 4].map((item) => <span key={item} className={item <= step ? "active" : ""} />)}</div>
        <form className="onboarding-form" onSubmit={submit}>
          <div className="lia-question"><h2>{step === 5 ? `Oui ${form.name || "à toi"}, voici ton profil.` : ["Comment tu t’appelles ?", "Tu es en quelle classe ou quel niveau ?", "Quelles matières veux-tu travailler avec moi ?", "Quel est ton objectif ?", "Comment préfères-tu apprendre ?"][step]}</h2></div>
          {step === 0 && <input id="student-name" autoFocus value={form.name} onChange={(event) => update("name", event.target.value)} placeholder="Ton prénom et ton nom" aria-label="Ton prénom et ton nom" />}
          {step === 1 && <input id="student-level" autoFocus value={form.level} onChange={(event) => update("level", event.target.value)} placeholder="Ton niveau ou ta classe" aria-label="Ton niveau ou ta classe" />}
          {step === 2 && <><label>Matières principales</label><div className="chip-grid">{subjectOptions.map((subject) => <button type="button" key={subject} className={form.subjects.includes(subject) ? "selected" : ""} onClick={() => toggleSubject(subject)}>{subject}</button>)}</div>{form.subjects.includes("Autres") && <input autoFocus value={customSubject} onChange={(event) => setCustomSubject(event.target.value)} placeholder="Écris ta matière" aria-label="Ta matière personnalisée" />}</>}
          {step === 3 && <textarea id="student-goal" autoFocus value={form.goal} onChange={(event) => update("goal", event.target.value)} placeholder="Ton objectif" aria-label="Ton objectif" />}
          {step === 4 && <><label>Ta façon d’apprendre</label><div className="chip-grid">{styleOptions.map((style) => <button type="button" key={style} className={form.learning_style === style ? "selected" : ""} onClick={() => update("learning_style", style)}>{style}</button>)}</div></>}
          {step === 5 && <div className="onboarding-summary"><p><strong>Nom</strong><span>{form.name || "Non renseigné"}</span></p><p><strong>Niveau</strong><span>{form.level || "Non renseigné"}</span></p><p><strong>Matières</strong><span>{[...form.subjects.filter((subject) => subject !== "Autres"), ...(customSubject.trim() ? [customSubject.trim()] : [])].join(", ") || "Non renseigné"}</span></p><p><strong>Objectif</strong><span>{form.goal || "Non renseigné"}</span></p><p><strong>Préférence</strong><span>{form.learning_style || "Non renseignée"}</span></p><small>Tu peux revenir en arrière pour modifier une réponse avant de valider.</small></div>}

          {error && <p className="error-banner">{error}</p>}
          <div className="onboarding-actions">{step > 0 && <button type="button" onClick={() => setStep((value) => value - 1)}>{step === 5 ? "Modifier" : "Retour"}</button>}<button disabled={loading}>{loading ? "Enregistrement..." : step === 5 ? "Valider mon profil" : "Suivant"}</button></div>
        </form>
      </section>
    </main>
  );
}

function AuthView({ onAuthenticated }: { onAuthenticated: (user: UserProfile) => void }) {
  const [mode, setMode] = useState<"login" | "register">("register");
  const [registerStep, setRegisterStep] = useState<"email" | "password">("email");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirmation, setPasswordConfirmation] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [acceptedTerms, setAcceptedTerms] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [resetToken, setResetToken] = useState(() => new URLSearchParams(window.location.search).get("reset_token") || "");
  const [verificationEmail, setVerificationEmail] = useState("");
  const [verificationCode, setVerificationCode] = useState("");
  const [googleAccountUsed, setGoogleAccountUsed] = useState(() => localStorage.getItem("orvix_google_account_used") === "true");
  function completeAuthentication(profile: UserProfile) {
    localStorage.setItem("orvix_user", JSON.stringify(profile));
    onAuthenticated(profile);
  }
  const googleButtonRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!googleButtonRef.current) return;
    const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID?.trim();
    if (!clientId) { setError("La connexion Google n’est pas configurée."); return; }
    const render = () => {
      if (!window.google?.accounts?.id || !googleButtonRef.current) return;
      window.google.accounts.id.initialize({ client_id: clientId, auto_select: true, use_fedcm_for_prompt: true, callback: async (response: { credential: string }) => {
        setLoading(true); setError("");
        try { const result = await loginWithGoogle(response.credential); localStorage.setItem("orvix_google_account_used", "true"); setGoogleAccountUsed(true); saveToken(result.token); completeAuthentication(result.existing_account ? { ...result.user, onboarding_completed: true } : result.user); }
        catch (e) { setError(e instanceof Error ? e.message : "Connexion Google impossible."); }
        finally { setLoading(false); }
      } });
      googleButtonRef.current.innerHTML = "";
      window.google.accounts.id.renderButton(googleButtonRef.current, { type: "standard", theme: "outline", size: "large", text: "continue_with", shape: "rectangular", width: Math.min(520, googleButtonRef.current.clientWidth || 520) });
      // Après une première connexion réussie, Google peut restaurer la session
      // du même navigateur et déclencher automatiquement le callback.
      if (localStorage.getItem("orvix_google_account_used") === "true") {
        window.google.accounts.id.prompt();
      }
    };
    if (window.google?.accounts?.id) render();
    else {
      const script = document.createElement("script"); script.src = "https://accounts.google.com/gsi/client"; script.async = true; script.onload = render; script.onerror = () => setError("Google est momentanément indisponible."); document.head.appendChild(script);
    }
  }, [mode, onAuthenticated, resetToken]);

  async function continueWithGoogle() {
    const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID?.trim();
    if (!clientId) { setError("La connexion Google n’est pas configurée."); return; }
    setLoading(true); setError("");
    try {
      if (!window.google?.accounts?.id) await new Promise<void>((resolve, reject) => { const script = document.createElement("script"); script.src = "https://accounts.google.com/gsi/client"; script.async = true; script.onload = () => resolve(); script.onerror = () => reject(new Error("Google est momentanément indisponible.")); document.head.appendChild(script); });
      await new Promise<void>((resolve, reject) => {
        let settled = false;
        const finish = (callback: () => void) => { if (settled) return; settled = true; window.clearTimeout(timeoutId); callback(); };
        const timeoutId = window.setTimeout(() => finish(() => reject(new Error("La fenêtre Google n’a pas pu être ouverte. Vérifiez les fenêtres pop-up bloquées puis réessayez."))), 12000);
        window.google.accounts.id.initialize({ client_id: clientId, callback: async (response: { credential: string }) => {
          try { const result = await loginWithGoogle(response.credential); localStorage.setItem("orvix_google_account_used", "true"); setGoogleAccountUsed(true); saveToken(result.token); completeAuthentication(result.existing_account ? { ...result.user, onboarding_completed: true } : result.user); finish(resolve); }
          catch (e) { finish(() => reject(e)); }
        } });
        window.google.accounts.id.prompt((notice: any) => {
          if (notice.isNotDisplayed?.() || notice.isSkippedMoment?.()) finish(() => reject(new Error("Google n’a pas affiché la fenêtre de connexion. Autorisez les fenêtres pop-up et réessayez.")));
        });
      });
    } catch (e) { setError(e instanceof Error ? e.message : "Connexion Google impossible."); } finally { setLoading(false); }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (verificationEmail) {
      if (loading || !/^\d{6}$/.test(verificationCode)) return;
      setLoading(true); setError("");
      try {
        const result = await verifyEmailRegistration(verificationEmail, verificationCode);
        saveToken(result.token); completeAuthentication(result.user);
      } catch (e) { setError(e instanceof Error ? e.message : "Code invalide."); }
      finally { setLoading(false); }
      return;
    }
    if (resetToken) {
      if (loading || password.length < 8 || password !== passwordConfirmation) {
        if (password !== passwordConfirmation) setError("Les mots de passe ne correspondent pas.");
        return;
      }
      setLoading(true); setError(""); setNotice("");
      try {
        const result = await confirmPasswordReset(resetToken, password);
        window.history.replaceState({}, "", window.location.pathname);
        setResetToken(""); setPassword(""); setPasswordConfirmation(""); setMode("login"); setNotice(result.message);
      } catch (e) { setError(e instanceof Error ? e.message : "Réinitialisation impossible."); }
      finally { setLoading(false); }
      return;
    }
    if (!phone.trim() || loading) return;
    if (mode === "register" && registerStep === "email") {
      setRegisterStep("password");
      setError("");
      return;
    }
    if (password.length < 6) return;
    if (mode === "register" && (password !== passwordConfirmation || !acceptedTerms)) {
      setError(password !== passwordConfirmation ? "Les mots de passe ne correspondent pas." : "Vous devez accepter les conditions d’utilisation.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const result = mode === "register" ? await register(phone, password) : await login(phone, password);
      if ("verification_required" in result) {
        setVerificationEmail(result.email); setNotice(result.message); setPassword(""); setPasswordConfirmation("");
        return;
      }
      saveToken(result.token);
      completeAuthentication(result.user);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Connexion impossible.");
    } finally {
      setLoading(false);
    }
  }

  async function forgotPassword() {
    const email = phone.trim().toLowerCase();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setError("Saisis d’abord l’adresse e-mail de ton compte.");
      return;
    }
    setLoading(true); setError(""); setNotice("");
    try {
      const result = await requestPasswordReset(email);
      setNotice(result.message);
    } catch (e) { setError(e instanceof Error ? e.message : "Envoi du lien impossible."); }
    finally { setLoading(false); }
  }

  return (
    <main className="auth-page">
      <section className={`auth-panel auth-reference ${mode}`}>
        {(mode === "register" || resetToken || verificationEmail) && <div className="auth-topline"><button type="button" aria-label="Retour à la connexion" onClick={() => { window.history.replaceState({}, "", window.location.pathname); setResetToken(""); setVerificationEmail(""); setVerificationCode(""); setMode("login"); setRegisterStep("email"); setError(""); }}><ArrowLeft /></button><strong>{verificationEmail ? "Vérifie ton e-mail" : resetToken ? "Nouveau mot de passe" : "Créer un compte"}</strong><span /></div>}
        <div className="auth-logo"><img className="auth-logo-image" src="/orvix-logo-transparent.png" alt="Logo Orvix" /><strong>ORVIX</strong><small>{mode === "login" ? "Votre IA. Vos documents. Nos réponses." : <>Commencez votre expérience avec <b>Orvix.</b></>}</small></div>
        {mode === "login" && !resetToken && <header className="auth-welcome"><h1>Bienvenue !</h1><p>Connectez-vous pour continuer<br />avec <b>Orvix.</b></p></header>}
        {!resetToken && !verificationEmail && <>
          <div className="google-account-block">
            {googleAccountUsed && <p className="google-account-label">Compte récemment utilisé</p>}
            <div ref={googleButtonRef} className="google-primary" aria-label="Continuer avec Google" />
          </div>
          <div className="auth-divider auth-divider-compact"><span />ou avec ton e-mail<span /></div>
        </>}
        <form onSubmit={submit} className="auth-form auth-reference-form">
          {verificationEmail && <><p className="verification-copy">Nous avons envoyé un code à <strong>{verificationEmail}</strong></p><div className="auth-input verification-code"><ShieldCheck size={20} /><input aria-label="Code de vérification" inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={verificationCode} onChange={(event) => setVerificationCode(event.target.value.replace(/\D/g, "").slice(0, 6))} placeholder="000 000" /></div></>}
          {!resetToken && !verificationEmail && <div className="auth-input"><Mail size={20} /><input id="phone" aria-label="Adresse e-mail ou numéro de téléphone" type="text" inputMode="email" value={phone} onChange={(event) => setPhone(event.target.value)} placeholder="Adresse e-mail ou numéro de téléphone" autoComplete="username" /></div>}
          {!verificationEmail && (resetToken || mode === "login" || registerStep === "password") && <div className="auth-input"><LockKeyhole size={20} /><input id="password" aria-label={resetToken ? "Nouveau mot de passe" : "Mot de passe"} value={password} onChange={(event) => setPassword(event.target.value)} placeholder={resetToken ? "Nouveau mot de passe" : "Mot de passe"} type={showPassword ? "text" : "password"} autoComplete={mode === "register" || resetToken ? "new-password" : "current-password"} /><button type="button" className="password-visibility" onClick={() => setShowPassword((current) => !current)} aria-label={showPassword ? "Masquer le mot de passe" : "Afficher le mot de passe"}>{showPassword ? <EyeOff size={20} /> : <Eye size={20} />}</button></div>}
          {!verificationEmail && (resetToken || (mode === "register" && registerStep === "password")) && <div className="auth-input"><LockKeyhole size={20} /><input aria-label="Confirmer le mot de passe" value={passwordConfirmation} onChange={(event) => setPasswordConfirmation(event.target.value)} placeholder="Confirmer le mot de passe" type={showPassword ? "text" : "password"} autoComplete="new-password" /></div>}
          {mode === "login" && !resetToken && <button type="button" className="forgot-password" onClick={forgotPassword}>Mot de passe oublié ?</button>}
          {!verificationEmail && mode === "register" && registerStep === "password" && <label className="terms-check"><input type="checkbox" checked={acceptedTerms} onChange={(event) => setAcceptedTerms(event.target.checked)} /><span>J’accepte les <b>Conditions d’utilisation</b><br />et la <b>Politique de confidentialité.</b></span></label>}
          {error && <p className="error-banner">{error}</p>}
          {notice && <p className="auth-notice">{notice}</p>}
          <button className="auth-submit" disabled={loading || (verificationEmail ? !/^\d{6}$/.test(verificationCode) : resetToken ? password.length < 8 || password !== passwordConfirmation : !phone.trim() || (mode === "login" && password.length < 6) || (mode === "register" && registerStep === "password" && (password.length < 6 || !acceptedTerms || password !== passwordConfirmation)))}>{loading ? "Patientez…" : verificationEmail ? "Vérifier et continuer" : resetToken ? "Modifier le mot de passe" : mode === "register" ? registerStep === "email" ? "Suivant" : "Créer le compte" : "Se connecter"}<span>→</span></button>
        </form>
        {!resetToken && !verificationEmail && <p className="auth-switch">{mode === "register" ? "Déjà un compte ?" : "Pas encore de compte ?"}<button type="button" onClick={() => { setMode(mode === "register" ? "login" : "register"); setRegisterStep("email"); setError(""); setNotice(""); }}>{mode === "register" ? "Se connecter" : "S’inscrire"}</button></p>}
      </section>
    </main>
  );
}

function PageIntro({ eyebrow, title, description }: { eyebrow: string; title: string; description: string }) {
  return <div className="page-intro"><span>{eyebrow}</span><h1>{title}</h1><p>{description}</p></div>;
}

function DocumentPicker({ documents, activeDocumentId, onActiveDocumentChange }: { documents: DocumentInfo[]; activeDocumentId: string; onActiveDocumentChange: (id: string) => void }) {
  return (
    <label className="document-picker">
      <span>Support utilisé</span>
      <select value={activeDocumentId} onChange={(event) => onActiveDocumentChange(event.target.value)}>
        <option value="">Aucun support</option>
        <option value="__all__">Tous les documents</option>
        {documents.map((doc) => <option key={doc.id} value={doc.id}>Document {doc.number} - {doc.name}</option>)}
      </select>
    </label>
  );
}

function ChatView({ language, documents, onDocumentsChange, activeDocumentId, onActiveDocumentChange, documentIds, conversationId, onConversationChange, messages, onMessagesChange, onSaved }: { language: string; documents: DocumentInfo[]; onDocumentsChange: (documents: DocumentInfo[]) => void; activeDocumentId: string; onActiveDocumentChange: (id: string) => void; documentIds: string[]; conversationId: string; onConversationChange: (id: string) => void; messages: ChatMessage[]; onMessagesChange: (messages: ChatMessage[]) => void; onSaved: () => Promise<void> }) {
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [responding, setResponding] = useState(false);
  const [attachmentMenu, setAttachmentMenu] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const attachmentButtonRef = useRef<HTMLButtonElement>(null);
  const attachmentMenuRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const messagesRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const followLatestMessageRef = useRef(true);
  const responseControllerRef = useRef<AbortController | null>(null);
  const responseRunRef = useRef(0);
  useEffect(() => {
    const panel = messagesRef.current;
    if (!panel || !followLatestMessageRef.current) return;
    requestAnimationFrame(() => { panel.scrollTo({ top: panel.scrollHeight, behavior: "auto" }); });
  }, [messages, loading]);
  useEffect(() => {
    if (!attachmentMenu) return;
    const closeOutside = (event: PointerEvent) => {
      const target = event.target as Node;
      if (attachmentButtonRef.current?.contains(target) || attachmentMenuRef.current?.contains(target)) return;
      setAttachmentMenu(false);
    };
    const closeWithEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setAttachmentMenu(false);
    };
    document.addEventListener("pointerdown", closeOutside);
    document.addEventListener("keydown", closeWithEscape);
    return () => {
      document.removeEventListener("pointerdown", closeOutside);
      document.removeEventListener("keydown", closeWithEscape);
    };
  }, [attachmentMenu]);
  useEffect(() => () => responseControllerRef.current?.abort(), []);
  useEffect(() => {
    if (!window.matchMedia("(max-width: 900px)").matches) return;
    const focusComposer = () => textareaRef.current?.focus({ preventScroll: true });
    const frame = requestAnimationFrame(focusComposer);
    const timer = window.setTimeout(focusComposer, 180);
    return () => {
      cancelAnimationFrame(frame);
      window.clearTimeout(timer);
    };
  }, [conversationId]);
  useEffect(() => {
    if (responding || !window.matchMedia("(max-width: 900px)").matches) return;
    const timer = window.setTimeout(() => textareaRef.current?.focus({ preventScroll: true }), 80);
    return () => window.clearTimeout(timer);
  }, [responding]);
  useEffect(() => {
    if (!message && textareaRef.current) {
      textareaRef.current.style.height = "24px";
      textareaRef.current.style.overflowY = "hidden";
    }
  }, [message]);

  function stopResponse() {
    responseRunRef.current += 1;
    responseControllerRef.current?.abort();
    responseControllerRef.current = null;
    setLoading(false);
    setResponding(false);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    const value = message.trim();
    if (!value || responding) return;
    setAttachmentMenu(false);
    const next = [...messages, { role: "user" as const, content: value }];
    const run = responseRunRef.current + 1;
    responseRunRef.current = run;
    const controller = new AbortController();
    responseControllerRef.current = controller;
    followLatestMessageRef.current = true;
    onMessagesChange(next); setMessage(""); setLoading(true); setResponding(true);
    requestAnimationFrame(() => { messagesRef.current?.scrollTo({ top: messagesRef.current.scrollHeight, behavior: "auto" }); });
    try {
      const result = await sendChat(value, messages.slice(-60), documentIds, conversationId, controller.signal);
      if (controller.signal.aborted || responseRunRef.current !== run) return;
      onConversationChange(result.conversation_id);
      const answer = result.answer || "";
      setLoading(false);
      let visible = "";
      for (let i = 0; i < answer.length; i += 6) {
        if (controller.signal.aborted || responseRunRef.current !== run) return;
        visible += answer.slice(i, i + 6);
        onMessagesChange([...next, { role: "assistant", content: visible }]);
        await new Promise((resolve) => window.setTimeout(resolve, 18));
      }
      if (controller.signal.aborted || responseRunRef.current !== run) return;
      await onSaved();
    } catch (error) {
      if (!(error instanceof DOMException && error.name === "AbortError") && !controller.signal.aborted && responseRunRef.current === run) {
        onMessagesChange([...next, { role: "assistant", content: error instanceof Error ? error.message : "Une erreur est survenue." }]);
      }
    } finally {
      if (responseRunRef.current === run) {
        responseControllerRef.current = null;
        setLoading(false);
        setResponding(false);
      }
    }
  }

  async function addSupports(files: FileList | null) {
    if (!files?.length) return;
    const result = await uploadDocuments(Array.from(files));
    onDocumentsChange(result.documents);
    const names = new Set(Array.from(files).map((file) => file.name));
    const uploaded = [...result.documents].reverse().find((doc) => names.has(doc.name));
    if (uploaded) onActiveDocumentChange(uploaded.id);
    setAttachmentMenu(false);
  }
  function resize(event: React.ChangeEvent<HTMLTextAreaElement>) {
    const el = event.currentTarget;
    const maxHeight = 88;
    el.style.height = "24px";
    el.style.overflowY = "hidden";
    const nextHeight = Math.min(Math.max(el.scrollHeight, 24), maxHeight);
    el.style.height = `${nextHeight}px`;
    if (el.scrollHeight > maxHeight) el.style.overflowY = "auto";
  }

  return <section className={`orvix-chat-shell chat-view ${messages.length || loading ? "has-messages" : "empty-chat"}`}>
    <div
      ref={messagesRef}
      className="messages orvix-chat-messages"
      aria-live="polite"
      onScroll={(event) => {
        const panel = event.currentTarget;
        followLatestMessageRef.current = panel.scrollHeight - panel.scrollTop - panel.clientHeight < 72;
      }}
    >
      {!messages.length && (
        <div className="chat-empty orvix-chat-empty">
          <div className="brand chat-empty-brand orvix-chat-empty-brand"><img className="brand-logo chat-empty-logo orvix-chat-logo" src="/orvix-logo-transparent.png" alt="Logo Orvix" /></div>
          <div className="orvix-introduction regular-welcome orvix-chat-welcome"><h1><span>Que veux-tu comprendre</span><br /><em>aujourd'hui ?</em></h1></div>
        </div>
      )}
      {messages.map((item, index) => <ChatMessageBubble key={index} item={item} />)}
      {loading && <div className="message-row assistant orvix-chat-loading"><span className="assistant-avatar"><img src="/orvix-logo-transparent.png" alt="Orvix" /></span><div className="message reading-state">Orvix réfléchit…</div></div>}
      <div ref={bottomRef} />
    </div>
    <form className="orvix-functional-composer" onSubmit={submit}>
      <div className="orvix-functional-writing"><textarea ref={textareaRef} autoFocus inputMode="text" enterKeyHint="send" value={message} onFocus={() => setAttachmentMenu(false)} onChange={(event) => { setMessage(event.target.value); resize(event); }} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); } }} placeholder="Poser une question" aria-label="Poser une question" rows={1} /></div>
      <div className="orvix-functional-actions"><button ref={attachmentButtonRef} type="button" aria-label="Ajouter un support" aria-expanded={attachmentMenu} onClick={() => setAttachmentMenu((value) => !value)}><Plus size={30} /></button><input ref={fileRef} type="file" hidden multiple accept=".pdf,.txt,.md" onChange={(event) => addSupports(event.target.files)} />{attachmentMenu && <div ref={attachmentMenuRef} className="orvix-functional-menu"><button type="button" onClick={() => { setAttachmentMenu(false); fileRef.current?.click(); }}>Ajouter un document</button></div>}<div><button type="button" aria-label="Microphone"><Mic size={28} /></button><button type={responding ? "button" : "submit"} aria-label={responding ? "Arrêter la réponse" : "Envoyer"} onClick={responding ? stopResponse : undefined} disabled={!responding && !message.trim()}>{responding ? <Square size={13} fill="currentColor" /> : <Send size={22} fill="currentColor" />}</button></div></div>
    </form>
  </section>;
}

function ChatMessageBubble({ item }: { item: ChatMessage }) {
  const time = new Date().toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
  const assistant = item.role === "assistant";
  const { cleanContent, sources } = parseMessageSources(item.content);
  return <div className={`message-row ${item.role} orvix-chat-message-row`}>
    {assistant && <span className="assistant-avatar orvix-chat-avatar"><img src="/orvix-logo-transparent.png" alt="Orvix" /></span>}
    <div className="message-stack">
      <div className="message orvix-chat-message">
        <FormattedMessage content={cleanContent} />
        {assistant && sources.length > 0 && <DocumentSources sources={sources} />}
        <span className="message-time">{time}{!assistant && <Check size={11} />}</span>
      </div>
      {assistant && <div className="message-actions">
        <button type="button" onClick={() => navigator.clipboard?.writeText(item.content)} aria-label="Copier la réponse"><Copy size={14} /></button>
        <button type="button" aria-label="Réponse utile"><ThumbsUp size={14} /></button>
        <button type="button" aria-label="Réponse à améliorer"><ThumbsDown size={14} /></button>
      </div>}
    </div>
  </div>;
}

function FormattedMessage({ content }: { content: string }) {
  const lines = content.split("\n").map((line) => line.trim()).filter(Boolean);
  if (!lines.length) return null;
  return (
    <div className="formatted-message">
      {lines.map((line, index) => {
        if (/^-{3,}$/.test(line)) return <hr key={index} />;
        const heading = line.match(/^#{1,6}\s*(.+)/);
        if (heading) return <h3 key={index}>{renderInline(heading[1])}</h3>;
        if (/^[-*]\s+/.test(line)) return <p className="bullet-line" key={index}>{renderInline(line.replace(/^[-*]\s+/, ""))}</p>;
        if (/^\d+[.)]\s+/.test(line)) return <p className="number-line" key={index}>{renderInline(line)}</p>;
        return <p key={index}>{renderInline(line)}</p>;
      })}
    </div>
  );
}

function renderInline(text: string) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g).filter(Boolean);
  return parts.map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={index}>{part.slice(2, -2).trim()}</strong>;
    }
    return <span key={index}>{part.replace(/\*/g, "")}</span>;
  });
}

function revisionPresentation(content: string, fallbackTitle: string) {
  const lines = content.split("\n");
  let title = fallbackTitle;
  let titleIndex = -1;
  for (let index = 0; index < lines.length; index += 1) {
    const clean = lines[index].trim().replace(/^#{1,6}\s*/, "").replace(/\*\*/g, "");
    const namedTitle = clean.match(/^(?:fiche de révision|révision guidée|révision express)\s*:\s*(.+)$/i);
    if (namedTitle?.[1]) { title = namedTitle[1].trim(); titleIndex = index; break; }
  }
  if (titleIndex < 0) {
    const headingIndex = lines.findIndex((line) => /^#{1,6}\s*\S/.test(line.trim()));
    if (headingIndex >= 0) {
      title = lines[headingIndex].trim().replace(/^#{1,6}\s*/, "").replace(/\*\*/g, "");
      titleIndex = headingIndex;
    }
  }
  return { title, body: lines.filter((_, index) => index !== titleIndex).join("\n") };
}

type MessageSource = { id: string; document_name: string; document_number: number; page: number | null; location: string; excerpt: string };

function parseMessageSources(content: string): { cleanContent: string; sources: MessageSource[] } {
  const sources: MessageSource[] = [];
  const cleanContent = content.replace(/\[\[ORVIX_SOURCE\]\]([\s\S]*?)\[\[\/ORVIX_SOURCE\]\]/g, (_match, raw: string) => {
    try { sources.push(JSON.parse(raw) as MessageSource); } catch { /* ignore malformed source metadata */ }
    return "";
  }).trim();
  return { cleanContent, sources };
}

function DocumentSources({ sources }: { sources: MessageSource[] }) {
  const [openId, setOpenId] = useState("");
  return <section className="message-sources" aria-label="Sources dans vos documents">
    <strong><BookOpenText size={16} />Source dans vos documents</strong>
    {sources.map((source) => <article key={source.id}>
      <div><span>{source.document_name}</span><small>{source.page ? `Page ${source.page}` : source.location}</small></div>
      <button type="button" onClick={() => setOpenId((current) => current === source.id ? "" : source.id)}>{openId === source.id ? "Masquer le passage" : "Voir le passage"}</button>
      {openId === source.id && <blockquote>{source.excerpt}</blockquote>}
    </article>)}
  </section>;
}

function RevisionView({ documents, activeDocumentId, onActiveDocumentChange, documentIds }: { documents: DocumentInfo[]; activeDocumentId: string; onActiveDocumentChange: (id: string) => void; documentIds: string[] }) {
  const modes = [
    { id: "sheet", label: "Fiche essentielle", description: "Les notions, définitions et exemples à retenir.", placeholder: "Ex. Le chapitre 2 sur la photosynthèse…", action: "Créer la fiche", instruction: "Crée une fiche de révision courte et structurée avec les notions essentielles, les définitions, des exemples et les points à retenir." },
    { id: "guided", label: "Révision guidée", description: "Une explication progressive suivie de questions.", placeholder: "Ex. Aide-moi à comprendre la photosynthèse…", action: "Commencer", instruction: "Prépare une révision guidée : explique progressivement le sujet, puis propose des questions de compréhension avec leurs corrections expliquées." },
    { id: "quick", label: "Révision express", description: "L’essentiel du cours en quelques minutes.", placeholder: "Ex. Les points clés à connaître avant mon contrôle…", action: "Réviser vite", instruction: "Prépare une révision express très concise : résumé, cinq points clés et trois questions flash avec réponses." },
  ] as const;
  const objectives = ["Comprendre", "Mémoriser", "Résumer", "Préparer un examen"] as const;
  const [mode, setMode] = useState<(typeof modes)[number]["id"]>("guided");
  const [objective, setObjective] = useState<(typeof objectives)[number]>("Comprendre");
  const [topic, setTopic] = useState(""); const [content, setContent] = useState(""); const [loading, setLoading] = useState(false); const [error, setError] = useState("");
  const [guidedQuestions, setGuidedQuestions] = useState<QuizQuestion[]>([]);
  const [guidedIndex, setGuidedIndex] = useState(0);
  const [guidedAnswer, setGuidedAnswer] = useState<number | null>(null);
  const [reviewPoints, setReviewPoints] = useState<string[]>([]);
  const selectedMode = modes.find((item) => item.id === mode) || modes[0];
  const revisionDocument = revisionPresentation(content, selectedMode.label);
  function resetGuidedSession() {
    setGuidedQuestions([]); setGuidedIndex(0); setGuidedAnswer(null); setReviewPoints([]);
  }
  async function submit(event: FormEvent) {
    event.preventDefault(); if (!topic.trim()) return; setLoading(true); setError(""); setContent(""); resetGuidedSession();
    const request = `${selectedMode.instruction}\nObjectif de l'étudiant : ${objective}.\n\nSujet demandé : ${topic.trim()}`;
    try {
      if (mode === "guided") {
        const [revision, quiz] = await Promise.all([
          createRevision(request, documentIds),
          createQuiz(`${topic.trim()}. Objectif : ${objective}. Vérifie les notions essentielles avec des questions progressives.`, documentIds, 5, "multiple_choice"),
        ]);
        setContent(revision.content);
        setGuidedQuestions(quiz.questions);
      } else {
        setContent((await createRevision(request, documentIds)).content);
      }
    } catch (e) { setError(e instanceof Error ? e.message : "Impossible de préparer la révision."); } finally { setLoading(false); }
  }
  function answerGuidedQuestion(answerIndex: number) {
    if (guidedAnswer !== null || guidedIndex >= guidedQuestions.length) return;
    setGuidedAnswer(answerIndex);
    const question = guidedQuestions[guidedIndex];
    if (answerIndex !== question.answer_index) {
      const point = `${question.question} — ${question.explanation}`;
      setReviewPoints((current) => current.includes(point) ? current : [...current, point]);
    }
  }
  function nextGuidedQuestion() {
    setGuidedIndex((current) => Math.min(current + 1, guidedQuestions.length));
    setGuidedAnswer(null);
  }
  return <section className="workspace-page revision-page">
    <p className="revision-lead">Choisis une méthode, sélectionne ton cours et indique ce que tu veux maîtriser.</p>
    <div className="revision-modes" role="group" aria-label="Méthode de révision">
      {modes.map((item) => <button key={item.id} type="button" className={mode === item.id ? "active" : ""} onClick={() => { setMode(item.id); setContent(""); resetGuidedSession(); }}><strong>{item.label}</strong><span>{item.description}</span></button>)}
    </div>
    <div className="revision-objectives" role="group" aria-label="Objectif de révision"><span>Mon objectif</span><div>{objectives.map((item) => <button key={item} type="button" className={objective === item ? "active" : ""} onClick={() => { setObjective(item); setContent(""); resetGuidedSession(); }}>{item}</button>)}</div></div>
    <DocumentPicker documents={documents} activeDocumentId={activeDocumentId} onActiveDocumentChange={onActiveDocumentChange} />
    <form className="revision-request" onSubmit={submit}><label htmlFor="revision-topic">Ce que tu veux réviser</label><div className="inline-form"><input id="revision-topic" value={topic} onChange={(e) => setTopic(e.target.value)} placeholder={selectedMode.placeholder} /><button disabled={loading || !topic.trim()}><Sparkles size={17} />{loading ? "Préparation…" : selectedMode.action}</button></div></form>
    {error && <p className="error-banner">{error}</p>}
    {content ? <article className="result-card prose revision-result"><h2>{revisionDocument.title}</h2><FormattedMessage content={revisionDocument.body} /></article> : <EmptyState icon={<BookOpenText />} text="Ta séance de révision apparaîtra ici." />}
    {mode === "guided" && guidedQuestions.length > 0 && guidedIndex < guidedQuestions.length && <section className="guided-session" aria-live="polite">
      <div className="guided-progress"><span>Question {guidedIndex + 1} sur {guidedQuestions.length}</span><div><i style={{ width: `${((guidedIndex + 1) / guidedQuestions.length) * 100}%` }} /></div></div>
      <h3>{guidedQuestions[guidedIndex].question}</h3>
      <div className="guided-choices">{guidedQuestions[guidedIndex].choices.map((choice, index) => {
        const answered = guidedAnswer !== null;
        const correct = index === guidedQuestions[guidedIndex].answer_index;
        const selected = index === guidedAnswer;
        return <button key={choice} type="button" disabled={answered} className={answered ? correct ? "correct" : selected ? "incorrect" : "" : ""} onClick={() => answerGuidedQuestion(index)}><span>{String.fromCharCode(65 + index)}</span>{choice}{answered && correct && <Check size={16} />}{answered && selected && !correct && <X size={16} />}</button>;
      })}</div>
      {guidedAnswer !== null && <div className={guidedAnswer === guidedQuestions[guidedIndex].answer_index ? "guided-feedback correct" : "guided-feedback incorrect"}><strong>{guidedAnswer === guidedQuestions[guidedIndex].answer_index ? "Bonne réponse" : "À revoir"}</strong><p>{guidedQuestions[guidedIndex].explanation}</p><button type="button" onClick={nextGuidedQuestion}>{guidedIndex + 1 === guidedQuestions.length ? "Voir mon bilan" : "Question suivante"}<ChevronRight size={16} /></button></div>}
    </section>}
    {mode === "guided" && guidedQuestions.length > 0 && guidedIndex >= guidedQuestions.length && <section className="guided-summary"><CheckCircle2 size={24} /><div><h3>Séance terminée</h3><p>{reviewPoints.length ? `${reviewPoints.length} point${reviewPoints.length > 1 ? "s" : ""} à revoir.` : "Tout est maîtrisé sur cette série."}</p></div></section>}
    {mode === "guided" && reviewPoints.length > 0 && <aside className="review-points"><h3>Points à revoir</h3>{reviewPoints.map((point) => <p key={point}>{point}</p>)}</aside>}
  </section>;
}

function QuizView({ documents, activeDocumentId, onActiveDocumentChange, documentIds }: { documents: DocumentInfo[]; activeDocumentId: string; onActiveDocumentChange: (id: string) => void; documentIds: string[] }) {
  const [topic, setTopic] = useState(""); const [quizType, setQuizType] = useState<"multiple_choice" | "traditional">("multiple_choice"); const [questionCount, setQuestionCount] = useState(3); const [quizTitle, setQuizTitle] = useState("Quiz Orvix"); const [questions, setQuestions] = useState<QuizQuestion[]>([]); const [selectedQuestions, setSelectedQuestions] = useState<Set<number>>(new Set()); const [answers, setAnswers] = useState<Record<number, number>>({}); const [writtenAnswers, setWrittenAnswers] = useState<Record<number, string>>({}); const [reviewed, setReviewed] = useState<Record<number, boolean>>({}); const [selfScores, setSelfScores] = useState<Record<number, boolean>>({}); const [loading, setLoading] = useState(false); const [exporting, setExporting] = useState(false); const [error, setError] = useState("");
  const [activeQuizIndex, setActiveQuizIndex] = useState(0);
  useEffect(() => {
    if (questions.length) window.setTimeout(() => window.scrollTo({ top: document.documentElement.scrollHeight, behavior: "smooth" }), 80);
  }, [questions.length]);
  const answeredCount = quizType === "multiple_choice" ? Object.keys(answers).length : Object.keys(selfScores).length;
  const score = quizType === "multiple_choice" ? questions.reduce((total, item, index) => total + (answers[index] === item.answer_index ? 1 : 0), 0) : Object.values(selfScores).filter(Boolean).length;
  const completed = Boolean(questions.length && answeredCount === questions.length);
  const activeDocument = documents.find((doc) => doc.id === activeDocumentId);
  const missedIndices = questions.map((_, index) => index).filter((index) => quizType === "multiple_choice" ? answers[index] !== questions[index].answer_index : selfScores[index] === false);
  async function submit(event: FormEvent) { event.preventDefault(); if (!topic.trim() && !documentIds.length) return; const quizTopic = topic.trim() || "Le contenu principal du support sélectionné"; setLoading(true); setError(""); setAnswers({}); setWrittenAnswers({}); setReviewed({}); setSelfScores({}); setActiveQuizIndex(0); try { const result = await createQuiz(quizTopic, documentIds, questionCount, quizType); setQuestions(result.questions); setSelectedQuestions(new Set(result.questions.map((_, index) => index))); setQuizTitle(result.title); } catch (e) { setError(e instanceof Error ? e.message : "Impossible de créer le quiz."); } finally { setLoading(false); } }
  function toggleQuestion(index: number) { setSelectedQuestions((current) => { const next = new Set(current); if (next.has(index)) next.delete(index); else next.add(index); return next; }); }
  async function downloadWord() { const chosenQuestions = questions.filter((_, index) => selectedQuestions.has(index)); if (!chosenQuestions.length) return; setExporting(true); setError(""); try { const blob = await exportQuizWord(quizTitle, chosenQuestions, quizType); const url = URL.createObjectURL(blob); const link = document.createElement("a"); link.href = url; link.download = `${quizTitle.replace(/[^a-zA-ZÀ-ÿ0-9 -]/g, "").trim().replace(/\s+/g, "-").toLowerCase() || "quiz-orvix"}.docx`; link.click(); URL.revokeObjectURL(url); } catch (e) { setError(e instanceof Error ? e.message : "Téléchargement impossible."); } finally { setExporting(false); } }
  return <section className="workspace-page quiz-page">
    <p className="quiz-lead">Choisis ton cours, règle la difficulté de la séance et réponds aux questions une par une.</p>
    <DocumentPicker documents={documents} activeDocumentId={activeDocumentId} onActiveDocumentChange={onActiveDocumentChange} />
    {!questions.length && <form className="quiz-setup" onSubmit={submit}><div className="quiz-options"><div><span>Format</span><div className="quiz-segments"><button type="button" className={quizType === "multiple_choice" ? "active" : ""} onClick={() => setQuizType("multiple_choice")}>Choix multiple</button><button type="button" className={quizType === "traditional" ? "active" : ""} onClick={() => setQuizType("traditional")}>Réponse rédigée</button></div></div><label><span>Questions</span><select value={questionCount} onChange={(event) => setQuestionCount(Number(event.target.value))}><option value={3}>3</option><option value={5}>5</option><option value={10}>10</option><option value={20}>20</option></select></label></div><label htmlFor="quiz-topic">Notion à tester <small>(optionnel avec un support)</small></label><div className="quiz-start-line"><input id="quiz-topic" value={topic} onChange={(e) => setTopic(e.target.value)} placeholder={activeDocument ? `Quiz sur le Document ${activeDocument.number}` : documentIds.length ? "Quiz sur les supports sélectionnés" : "Ex. Les fonctions affines"} /><button disabled={loading || (!topic.trim() && !documentIds.length)}><Sparkles size={17} />{loading ? "Préparation…" : "Commencer"}</button></div></form>}
    {error && <p className="error-banner">{error}</p>}
    {questions.length > 0 && <div className="quiz-focus">
      <header><div><small>{quizTitle}</small><strong>{activeQuizIndex >= questions.length ? "Bilan" : `Question ${activeQuizIndex + 1} sur ${questions.length}`}</strong></div><div><button type="button" className="word-download" onClick={downloadWord} disabled={exporting}><Download size={15} />{exporting ? "Création…" : "Word"}</button><button type="button" onClick={() => { setQuestions([]); setAnswers({}); setWrittenAnswers({}); setReviewed({}); setSelfScores({}); setActiveQuizIndex(0); }}>Nouveau quiz</button></div><span><i style={{ width: `${Math.min(100, (activeQuizIndex / questions.length) * 100)}%` }} /></span></header>
      {activeQuizIndex < questions.length ? <article className="quiz-focus-card"><h2>{questions[activeQuizIndex].question}</h2>{quizType === "multiple_choice" ? <><div className="quiz-focus-choices">{questions[activeQuizIndex].choices.map((choice, choiceIndex) => { const answered = answers[activeQuizIndex] !== undefined; const selected = answers[activeQuizIndex] === choiceIndex; const correct = choiceIndex === questions[activeQuizIndex].answer_index; return <button type="button" key={choice} disabled={answered} className={answered ? correct ? "correct" : selected ? "incorrect" : "" : ""} onClick={() => setAnswers({ ...answers, [activeQuizIndex]: choiceIndex })}><span>{String.fromCharCode(65 + choiceIndex)}</span>{choice}{answered && correct && <Check size={16} />}{answered && selected && !correct && <X size={16} />}</button>; })}</div>{answers[activeQuizIndex] !== undefined && <div className={answers[activeQuizIndex] === questions[activeQuizIndex].answer_index ? "quiz-focus-feedback correct" : "quiz-focus-feedback incorrect"}><strong>{answers[activeQuizIndex] === questions[activeQuizIndex].answer_index ? "Bonne réponse" : "Réponse à revoir"}</strong><p>{questions[activeQuizIndex].explanation}</p><button type="button" onClick={() => setActiveQuizIndex((index) => index + 1)}>{activeQuizIndex + 1 === questions.length ? "Voir le bilan" : "Question suivante"}<ChevronRight size={16} /></button></div>}</> : <div className="quiz-written"><textarea value={writtenAnswers[activeQuizIndex] || ""} onChange={(event) => setWrittenAnswers({ ...writtenAnswers, [activeQuizIndex]: event.target.value })} disabled={reviewed[activeQuizIndex]} placeholder="Écris ta réponse avec tes propres mots…" />{!reviewed[activeQuizIndex] ? <button type="button" disabled={!writtenAnswers[activeQuizIndex]?.trim()} onClick={() => setReviewed({ ...reviewed, [activeQuizIndex]: true })}>Comparer ma réponse</button> : <div className="quiz-expected"><strong>Réponse attendue</strong><p>{questions[activeQuizIndex].expected_answer}</p><small>{questions[activeQuizIndex].explanation}</small><div><button type="button" className={selfScores[activeQuizIndex] === true ? "active" : ""} onClick={() => setSelfScores({ ...selfScores, [activeQuizIndex]: true })}>J’avais compris</button><button type="button" className={selfScores[activeQuizIndex] === false ? "active review" : "review"} onClick={() => setSelfScores({ ...selfScores, [activeQuizIndex]: false })}>À revoir</button></div>{selfScores[activeQuizIndex] !== undefined && <button type="button" className="quiz-next" onClick={() => setActiveQuizIndex((index) => index + 1)}>{activeQuizIndex + 1 === questions.length ? "Voir le bilan" : "Question suivante"}<ChevronRight size={16} /></button>}</div>}</div>}</article> : <div className="quiz-complete"><QuizSummary score={score} total={questions.length} missedIndices={missedIndices} /><section className="quiz-review"><h3>Correction complète</h3><p>Ouvre une question pour revoir la réponse et son explication.</p>{questions.map((question, index) => { const correct = quizType === "multiple_choice" ? answers[index] === question.answer_index : selfScores[index] === true; return <details key={question.question} className={correct ? "correct" : "incorrect"}><summary><span>{correct ? <Check size={14} /> : <X size={14} />}</span><strong>Question {index + 1}</strong><small>{question.question}</small><ChevronRight size={15} /></summary><div>{quizType === "multiple_choice" && <p><b>Ta réponse :</b> {question.choices[answers[index]] || "Aucune réponse"}</p>}<p><b>Réponse attendue :</b> {quizType === "multiple_choice" ? question.choices[question.answer_index] : question.expected_answer}</p><p>{question.explanation}</p></div></details>; })}</section></div>}
    </div>}
    {!questions.length && !loading && <EmptyState icon={<HelpCircle />} text="Ton quiz apparaîtra ici." />}
  </section>;
}

function QuizSummary({ score, total, missedIndices }: { score: number; total: number; missedIndices: number[] }) {
  const percent = Math.round((score / total) * 100);
  const advice = percent >= 80
    ? "Très bon résultat. Relisez seulement les explications des questions hésitantes, puis refaites un quiz plus difficile."
    : percent >= 50
      ? "Vous avez les bases. Revoyez les questions ratées, puis reformulez chaque notion avec vos propres mots."
      : "Reprenez la leçon calmement. Commencez par les définitions, puis demandez à Orvix une explication plus simple avant de refaire le quiz.";
  return (
    <section className="quiz-summary">
      <div><span>Score</span><strong>{score}/{total}</strong><small>{percent}%</small></div>
      <article>
        <h2>Conseil de révision</h2>
        <p>{advice}</p>
        {missedIndices.length ? <p>À revoir en priorité : {missedIndices.map((questionIndex, index) => `question ${questionIndex + 1}${index < missedIndices.length - 1 ? ", " : ""}`)}</p> : <p>Aucune erreur. Vous pouvez passer à une leçon plus avancée.</p>}
      </article>
    </section>
  );
}

function ExamModeView({ documents, activeDocumentId, onActiveDocumentChange, documentIds }: { documents: DocumentInfo[]; activeDocumentId: string; onActiveDocumentChange: (id: string) => void; documentIds: string[] }) {
  const tomorrow = new Date(Date.now() + 86400000).toISOString().slice(0, 10);
  const [examDate, setExamDate] = useState(tomorrow);
  const [minutes, setMinutes] = useState(45);
  const [confidence, setConfidence] = useState(3);
  const [subject, setSubject] = useState("");
  const [result, setResult] = useState<ExamPlan | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!documentIds.length || loading) return;
    setLoading(true); setError(""); setResult(null);
    try { setResult(await createExamPlan(documentIds, examDate, minutes, confidence, subject.trim())); }
    catch (e) { setError(e instanceof Error ? e.message : "Impossible de préparer le programme."); }
    finally { setLoading(false); }
  }

  return <section className="workspace-page exam-page">
    <div className="page-intro"><span>MODE EXAMEN</span><h1>Prépare-moi à mon examen</h1><p>ORVIX analyse tes supports et construit un programme personnel jusqu’au jour de l’examen.</p></div>
    <DocumentPicker documents={documents} activeDocumentId={activeDocumentId} onActiveDocumentChange={onActiveDocumentChange} />
    <form className="exam-setup" onSubmit={submit}>
      <label><span>Matière ou objectif</span><input value={subject} onChange={(event) => setSubject(event.target.value)} placeholder="Ex. Anatomie, chapitre 3…" /></label>
      <label><span>Date de l’examen</span><input type="date" min={tomorrow} value={examDate} onChange={(event) => setExamDate(event.target.value)} /></label>
      <label><span>Temps par jour</span><select value={minutes} onChange={(event) => setMinutes(Number(event.target.value))}><option value={20}>20 minutes</option><option value={30}>30 minutes</option><option value={45}>45 minutes</option><option value={60}>1 heure</option><option value={90}>1 h 30</option><option value={120}>2 heures</option></select></label>
      <label><span>Confiance actuelle : {confidence}/5</span><input type="range" min={1} max={5} value={confidence} onChange={(event) => setConfidence(Number(event.target.value))} /></label>
      <button disabled={!documentIds.length || loading}><Target size={19} />{loading ? "Analyse de tes supports…" : "Créer mon programme"}</button>
    </form>
    {!documentIds.length && <p className="exam-hint"><FileText size={18} />Sélectionne au moins un support pour commencer.</p>}
    {error && <p className="error-banner">{error}</p>}
    {result && <div className="exam-results">
      <section className="readiness-card"><div className="readiness-ring" style={{ "--score": `${result.readiness_score * 3.6}deg` } as CSSProperties}><span>{result.readiness_score}%</span></div><div><small>PRÉPARATION INITIALE</small><h2>{result.title}</h2><p>{result.summary}</p></div></section>
      <div className="exam-columns"><section><h3><CheckCircle2 />Points de départ</h3>{result.mastered.map((item) => <p key={item}>✓ {item}</p>)}</section><section className="priority-card"><h3><Target />À renforcer</h3>{result.priorities.map((item) => <p key={item}>→ {item}</p>)}</section></div>
      <section className="exam-plan"><h2><CalendarDays />Ton programme</h2><div>{result.plan.map((day) => <article key={day.day}><span>Jour {day.day}</span><h3>{day.title}</h3><ul>{day.tasks.map((task) => <li key={task}>{task}</li>)}</ul><small>{day.minutes} minutes</small></article>)}</div></section>
      <section className="exam-questions"><h2>Premier test — 5 questions</h2>{result.first_questions.map((question, index) => <details key={question.question}><summary>{index + 1}. {question.question}</summary><ol>{question.choices.map((choice) => <li key={choice}>{choice}</li>)}</ol><p><strong>Réponse :</strong> {question.choices[question.answer_index]}</p><p>{question.explanation}</p></details>)}</section>
    </div>}
  </section>;
}

function SupportView({ documents, onDocumentsChange, activeDocumentId, onActiveDocumentChange, maxDocumentMb, maxDocumentPages }: { documents: DocumentInfo[]; onDocumentsChange: (documents: DocumentInfo[]) => void; activeDocumentId: string; onActiveDocumentChange: (id: string) => void; maxDocumentMb: number; maxDocumentPages: number }) {
  const [loading, setLoading] = useState(false); const [error, setError] = useState("");
  const [uploadProgress, setUploadProgress] = useState(0);
  const [deletingId, setDeletingId] = useState("");
  const [search, setSearch] = useState("");
  const [dragging, setDragging] = useState(false);
  useEffect(() => { listDocuments().then((r) => onDocumentsChange(r.documents)).catch(() => undefined); }, [onDocumentsChange]);
  async function upload(files: FileList | null) { if (!files?.length) return; setLoading(true); setUploadProgress(1); setError(""); try { onDocumentsChange((await uploadDocuments(Array.from(files), setUploadProgress)).documents); } catch (e) { setError(e instanceof Error ? e.message : "Import impossible."); } finally { setLoading(false); setUploadProgress(0); } }
  async function remove(doc: DocumentInfo) {
    if (!window.confirm(`Supprimer définitivement « ${doc.name} » ?`)) return;
    setDeletingId(doc.id); setError("");
    try {
      const result = await deleteDocument(doc.id);
      onDocumentsChange(result.documents);
      if (activeDocumentId === doc.id || activeDocumentId === "__all__") onActiveDocumentChange("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Suppression impossible.");
    } finally { setDeletingId(""); }
  }
  const visibleDocuments = documents.filter((doc) => `${doc.number} ${doc.name}`.toLowerCase().includes(search.trim().toLowerCase()));
  return <section className="workspace-page support-page">
    <p className="support-lead">Ajoute tes cours une fois, puis utilise-les dans Chat, Révision et Quiz.</p>
    <label className={dragging ? "upload-zone support-upload dragging" : "upload-zone support-upload"} onDragEnter={(event) => { event.preventDefault(); setDragging(true); }} onDragOver={(event) => event.preventDefault()} onDragLeave={(event) => { if (!event.currentTarget.contains(event.relatedTarget as Node)) setDragging(false); }} onDrop={(event) => { event.preventDefault(); setDragging(false); upload(event.dataTransfer.files); }}><UploadCloud size={27} /><span><strong>{loading ? (uploadProgress >= 100 ? "Préparation du support…" : `Import en cours · ${uploadProgress}%`) : "Dépose tes fichiers ici"}</strong><small>ou clique pour les sélectionner · PDF, TXT, Markdown · {maxDocumentMb} Mo · {maxDocumentPages} pages max.</small>{loading && <i className="support-upload-progress" aria-label={`Progression de l’import : ${uploadProgress}%`}><i style={{ width: `${uploadProgress}%` }} /></i>}</span><b>{loading ? `${uploadProgress}%` : "Ajouter"}</b><input type="file" multiple accept=".pdf,.txt,.md" onChange={(e) => upload(e.target.files)} disabled={loading} /></label>
    {error && <p className="error-banner">{error}</p>}
    <div className="support-library-head"><div><strong>Mes documents</strong><span>{documents.length} support{documents.length > 1 ? "s" : ""}</span></div><input className="document-search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Rechercher…" /></div>
    <div className="document-grid support-grid">{visibleDocuments.map((doc) => <article className={activeDocumentId === doc.id ? "document-card active" : "document-card"} key={doc.id}><button className="document-select" onClick={() => onActiveDocumentChange(activeDocumentId === doc.id ? "" : doc.id)}><span className="file-icon"><FileText /></span><span className="document-details"><strong>{doc.name}</strong><small>Document {doc.number} · {(doc.size / 1024).toFixed(1)} Ko</small></span>{activeDocumentId === doc.id && <span className="support-active">Utilisé</span>}</button><button className="document-delete" onClick={() => remove(doc)} disabled={deletingId === doc.id} aria-label={`Supprimer ${doc.name}`} title="Supprimer le document"><Trash2 size={16} /></button></article>)}</div>
    {!documents.length && <EmptyState icon={<FileText />} text="Aucun support importé pour le moment." />}
    {Boolean(documents.length && !visibleDocuments.length) && <EmptyState icon={<FileText />} text="Aucun document ne correspond à cette recherche." />}
  </section>;
}

function EmptyState({ icon, text }: { icon: React.ReactNode; text: string }) { return <div className="empty-state"><span>{icon}</span><p>{text}</p></div>; }
export default App;
