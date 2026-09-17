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
  Menu,
  MessageCircle,
  Moon,
  Plus,
  Send,
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
  completeOnboarding,
  createQuiz,
  createExamPlan,
  createRevision,
  createSubscriptionCheckout,
  deleteDocument,
  exportQuizWord,
  getConversation,
  getSubscription,
  getSubscriptionPlans,
  login,
  loginWithGoogle,
  markWelcomeSeen,
  listConversations,
  listDocuments,
  me,
  register,
  saveToken,
  sendChat,
  uploadDocuments,
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
  const [user, setUser] = useState<UserProfile | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [activeDocumentId, setActiveDocumentId] = useState("");
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeConversationId, setActiveConversationId] = useState("");
  const [activeMessages, setActiveMessages] = useState<ChatMessage[]>([]);
  const [view, setView] = useState<View>("chat");
  const [mobileNav, setMobileNav] = useState(false);
  const [accountPlanName, setAccountPlanName] = useState("Gratuit");
  const [theme, setTheme] = useState<"light" | "dark">(() => localStorage.getItem("orvix_theme") === "dark" ? "dark" : "light");
  const [language, setLanguage] = useState("Français");

  useEffect(() => {
    me().then(setUser).catch(() => clearToken()).finally(() => setAuthChecked(true));
    document.documentElement.dataset.textSize = localStorage.getItem("orvix_text_size") || "normal";
    document.documentElement.dataset.density = localStorage.getItem("orvix_density") || "comfortable";
    document.documentElement.dataset.animations = localStorage.getItem("orvix_animations") === "off" ? "off" : "on";
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("orvix_theme", theme);
  }, [theme]);
  useEffect(() => {
    localStorage.setItem("orvix_language", language);
    document.documentElement.lang = language === "English" ? "en" : language === "Italiano" ? "it" : language === "Español" ? "es" : "fr";
  }, [language]);

  useEffect(() => {
    if (!user?.onboarding_completed) return;
    listDocuments().then((result) => setDocuments(result.documents)).catch(() => undefined);
    listConversations().then((result) => setConversations(result.conversations)).catch(() => undefined);
    getSubscription().then((result) => setAccountPlanName(result.plan.name)).catch(() => undefined);
  }, [user?.onboarding_completed]);

  if (!authChecked) {
    return <div className="auth-loading">ORVIX</div>;
  }

  if (!user) {
    return <AuthView onAuthenticated={setUser} />;
  }

  if (!user.onboarding_completed) {
    if (!user.welcome_seen) {
      return <FirstWelcomeView onContinue={async () => setUser(await markWelcomeSeen())} />;
    }
    return <OnboardingView user={user} onCompleted={setUser} onLogout={() => { clearToken(); setUser(null); }} />;
  }

  const activeDocumentIds = activeDocumentId === "__all__"
    ? documents.map((document) => document.id)
    : activeDocumentId ? [activeDocumentId] : [];

  function newChat() {
    setActiveConversationId("");
    setActiveMessages([]);
    setView("chat");
  }

  async function openConversation(conversationId: string) {
    const conversation = await getConversation(conversationId);
    setActiveConversationId(conversation.id);
    setActiveMessages(conversation.messages);
    setActiveDocumentId(conversation.document_ids.length > 1 ? "__all__" : conversation.document_ids[0] || "");
    setView("chat");
  }

  async function refreshConversations() {
    const result = await listConversations();
    setConversations(result.conversations);
  }

  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobileNav ? "open" : ""}`}>
        <div className="brand sidebar-brand"><img className="brand-logo" src="/orvix-logo-transparent.png" alt="Logo Orvix" /><span>ORVIX</span></div>
        <button className="close-nav" onClick={() => setMobileNav(false)} aria-label="Fermer le menu"><X /></button>
        <nav>
          {nav.map(({ id, label, icon: Icon }) => (
            <button key={id} className={view === id ? "nav-item active" : "nav-item"} onClick={() => { setView(id); setMobileNav(false); }}>
              <Icon size={21} /><span>{navLabels[language]?.[id] || label}</span>
            </button>
          ))}
        </nav>
        <section className="recents">
          <div className="recents-head"><h3>DISCUSSIONS</h3><button onClick={newChat}>+</button></div>
          <button className={!activeConversationId ? "conversation-link active" : "conversation-link"} onClick={newChat}>Nouvelle discussion</button>
          {conversations.map((item) => <button key={item.id} className={activeConversationId === item.id ? "conversation-link active" : "conversation-link"} onClick={() => openConversation(item.id)}>{item.title}</button>)}
        </section>
        <div className="sidebar-bottom">
          <button className={`profile-card account-button ${view === "account" ? "active" : ""}`} onClick={() => { setView("account"); setMobileNav(false); }} aria-label="Ouvrir mon compte"><span className="avatar">{user.name.slice(0, 1).toUpperCase()}</span><span><strong>{user.name}</strong><small>Forfait {accountPlanName}</small></span><span className="profile-caret">⌃</span></button>
        </div>
      </aside>

      {mobileNav && <button className="backdrop" onClick={() => setMobileNav(false)} aria-label="Fermer le menu" />}
      <main className={`main-content ${view === "account" ? "account-scroll" : ""}`}>
        <div className="page-actions">
          <button className="mobile-menu" onClick={() => setMobileNav(true)} aria-label="Ouvrir le menu"><Menu /></button>
          {view === "chat" && <label className="top-document-selector"><FileText size={17} /><select aria-label="Mode de réponse et support utilisé" value={activeDocumentId} onChange={(event) => setActiveDocumentId(event.target.value)}><option value="">Question libre</option><option value="__all__">Tous les documents</option>{documents.map((doc) => <option key={doc.id} value={doc.id}>Document {doc.number} · {doc.name}</option>)}</select></label>}
          <button aria-label="Profil" onClick={() => setView("account")}><User size={22} /></button>
        </div>
        {view === "chat" && <ChatView language={language} documents={documents} onDocumentsChange={setDocuments} activeDocumentId={activeDocumentId} onActiveDocumentChange={setActiveDocumentId} documentIds={activeDocumentIds} conversationId={activeConversationId} onConversationChange={setActiveConversationId} messages={activeMessages} onMessagesChange={setActiveMessages} onSaved={refreshConversations} />}
        {view === "revision" && <RevisionView documents={documents} activeDocumentId={activeDocumentId} onActiveDocumentChange={setActiveDocumentId} documentIds={activeDocumentIds} />}
        {view === "quiz" && <QuizView documents={documents} activeDocumentId={activeDocumentId} onActiveDocumentChange={setActiveDocumentId} documentIds={activeDocumentIds} />}
        {view === "support" && <SupportView documents={documents} onDocumentsChange={setDocuments} activeDocumentId={activeDocumentId} onActiveDocumentChange={setActiveDocumentId} />}
        {view === "account" && <AccountView user={user} onSaved={setUser} documentCount={documents.length} conversationCount={conversations.length} theme={theme} onThemeChange={() => setTheme((current) => current === "dark" ? "light" : "dark")} language={language} onLanguageChange={setLanguage} onLogout={() => { clearToken(); setUser(null); }} />}
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
  const [subscription, setSubscription] = useState<SubscriptionStatus | null>(null);
  const [billingCycle, setBillingCycle] = useState<"monthly" | "annual">("monthly");
  const [paymentLoading, setPaymentLoading] = useState("");
  const [settingsSection, setSettingsSection] = useState<"overview" | "profile" | "subscription" | "appearance" | "security" | "notifications" | "language" | "help" | "about">("overview");
  const [paymentError, setPaymentError] = useState("");
  const [paymentMessage, setPaymentMessage] = useState("");
  const [securityAlerts, setSecurityAlerts] = useState(true);
  const [emailNotifications, setEmailNotifications] = useState(true);

  useEffect(() => {
    getSubscriptionPlans().then((result) => setPlans(result.plans)).catch(() => undefined);
    getSubscription().then(setSubscription).catch(() => undefined);
  }, []);

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
    if (!form.name.trim() || !form.level.trim() || !form.goal.trim()) return;
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

  async function startPayment(planId: "student") {
    setPaymentLoading(planId); setPaymentError(""); setPaymentMessage("");
    try {
      const checkout = await createSubscriptionCheckout(planId, billingCycle);
      if (checkout.simulation) {
        const updated = await getSubscription();
        setSubscription(updated);
        setPaymentMessage(`Simulation réussie : le forfait ${updated.plan.name} est activé pour les tests. Aucun paiement réel n’a été effectué.`);
        setPaymentLoading("");
        return;
      }
      window.location.assign(checkout.payment_url);
    } catch (e) {
      setPaymentError(e instanceof Error ? e.message : "Impossible de démarrer le paiement.");
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
    {settingsSection !== "overview" && <header className="profile-detail-heading"><button type="button" onClick={() => setSettingsSection("overview")}><ArrowLeft /></button><div><span>PROFIL</span><h1>{settingsSection === "profile" ? "Informations personnelles" : settingsSection === "subscription" ? "Abonnement" : settingsSection === "security" ? "Sécurité" : settingsSection === "notifications" ? "Notifications" : settingsSection === "language" ? "Langue" : settingsSection === "help" ? "Aide et support" : settingsSection === "about" ? "À propos d’Orvix" : "Apparence"}</h1></div></header>}
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
    {settingsSection === "help" && <section className="settings-form profile-simple-panel"><section className="setting-group full"><div><h2>Besoin d’aide ?</h2><p>Importe un document, sélectionne-le puis pose ta question à ORVIX. Pour un problème technique, redémarre le site et le backend.</p></div></section></section>}
    {settingsSection === "about" && <section className="settings-form profile-simple-panel"><section className="setting-group full"><div><h2>À propos d’ORVIX</h2><p>ORVIX est une intelligence artificielle créée par DIEU MERCI KAZADI pour aider les étudiants à comprendre leurs documents.</p></div></section></section>}
    {settingsSection === "subscription" && <section className="subscription-panel">
      <div className="subscription-heading"><div><span>ABONNEMENT · MODE TEST</span><h2>Choisis ton forfait ORVIX</h2><p>Simulation uniquement : aucun Mobile Money ni aucune carte bancaire ne sera débité.</p></div><div className="billing-switch"><button className={billingCycle === "monthly" ? "active" : ""} onClick={() => setBillingCycle("monthly")}>Mensuel</button><button className={billingCycle === "annual" ? "active" : ""} onClick={() => setBillingCycle("annual")}>Annuel <small>2 mois offerts</small></button></div></div>
      {subscription && <div className="quota-summary"><span>Forfait actuel : <strong>{subscription.plan.name}</strong></span><span>Requêtes aujourd’hui : <strong>{subscription.requests_used_today}/{subscription.plan.daily_requests}</strong></span><span>Documents autorisés : <strong>{subscription.plan.documents}</strong></span></div>}
      {subscription && <div className="quota-progress"><span style={{ width: `${Math.min(100, (subscription.requests_used_today / subscription.plan.daily_requests) * 100)}%` }} /></div>}
      {paymentError && <p className="subscription-error">{paymentError}</p>}
      {paymentMessage && <p className="settings-success"><CheckCircle2 size={19} />{paymentMessage}</p>}
      <div className="plans-grid">{plans.map((plan) => {
        const active = subscription?.plan.id === plan.id;
        const price = billingCycle === "annual" ? plan.annual_price : plan.monthly_price;
        return <article key={plan.id} className={`plan-card ${active ? "current" : ""} ${plan.id === "student" ? "recommended" : ""}`}>
          {plan.id === "student" && <em>RECOMMANDÉ</em>}<h3>{plan.name}</h3><p className="plan-price"><strong>{price === 0 ? "0 $" : `${price.toFixed(2).replace(".", ",")} $`}</strong><small>{price > 0 ? (billingCycle === "annual" ? "/an" : "/mois") : "pour toujours"}</small></p>
          <ul><li><Check size={17} />{plan.documents} document{plan.documents > 1 ? "s" : ""}</li><li><Check size={17} />{plan.daily_requests} requêtes par jour</li>{plan.features.map((feature) => <li key={feature}><Check size={17} />{feature}</li>)}</ul>
          <button type="button" disabled={active || plan.id === "free" || plan.id === "pro" || Boolean(paymentLoading)} onClick={() => plan.id === "student" && startPayment("student")}>{plan.id === "pro" ? "Bientôt" : active ? "Forfait actuel" : plan.id === "free" ? "Gratuit" : paymentLoading === plan.id ? "Simulation en cours…" : "Tester ce forfait"}</button>
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
const starterPrompts = [
  { title: "Explique-moi", detail: "ce cours simplement", prompt: "Explique-moi ce cours simplement", icon: MessageCircle },
  { title: "Aide-moi à", detail: "comprendre un concept", prompt: "Aide-moi à comprendre un concept", icon: Sparkles },
  { title: "Pose-moi des questions", detail: "pour réviser", prompt: "Pose-moi des questions pour réviser", icon: HelpCircle },
  { title: "Résume le document", detail: "sélectionné", prompt: "Résume le document sélectionné", icon: FileText },
];

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
    if (step < 4) { setStep((value) => value + 1); return; }
    if (!form.name.trim() || !form.level.trim() || !form.goal.trim()) return;
    setLoading(true);
    setError("");
    try {
      onCompleted(await completeOnboarding(form));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Impossible d'enregistrer le profil.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="auth-page onboarding-page">
      <section className="onboarding-panel">
        <div className="brand auth-brand"><img className="brand-logo" src="/orvix-logo-transparent.png" alt="Logo Orvix" /><span>ORVIX</span></div>
        <div className="lia-intro"><span className="lia-avatar">O</span><div><strong>Orvix</strong><small>Ton assistant d’apprentissage</small></div><span className="lia-progress">{step + 1}/5</span></div>
        <div className="page-intro compact"><span>QUELQUES QUESTIONS</span><h1>Faisons connaissance</h1><p>Réponds à chaque question, puis Orvix continuera.</p></div>
        <form className="onboarding-form" onSubmit={submit}>
          <div className="lia-question"><span>Orvix te demande</span><h2>{["Comment tu t’appelles ?", "Tu es en quelle classe ou quel niveau ?", "Quelles matières veux-tu travailler avec moi ?", "Quel est ton objectif ?", "Comment préfères-tu apprendre ?"][step]}</h2></div>
          {step === 0 && <><label htmlFor="student-name">Ton prénom et ton nom</label><input id="student-name" autoFocus value={form.name} onChange={(event) => update("name", event.target.value)} placeholder="Ex. Alex Dupont" /></>}
          {step === 1 && <><label htmlFor="student-level">Ton niveau</label><input id="student-level" autoFocus value={form.level} onChange={(event) => update("level", event.target.value)} placeholder="Ex. Terminale, L1, 4e secondaire" /></>}
          {step === 2 && <><label>Matières principales</label><div className="chip-grid">{subjectOptions.map((subject) => <button type="button" key={subject} className={form.subjects.includes(subject) ? "selected" : ""} onClick={() => toggleSubject(subject)}>{subject}</button>)}</div></>}
          {step === 3 && <><label htmlFor="student-goal">Ton objectif</label><textarea id="student-goal" autoFocus value={form.goal} onChange={(event) => update("goal", event.target.value)} placeholder="Ex. Réussir mes examens, mieux comprendre mes cours..." /></>}
          {step === 4 && <><label>Ta façon d’apprendre</label><div className="chip-grid">{styleOptions.map((style) => <button type="button" key={style} className={form.learning_style === style ? "selected" : ""} onClick={() => update("learning_style", style)}>{style}</button>)}</div></>}

          {error && <p className="error-banner">{error}</p>}
          <div className="onboarding-actions"><button type="button" onClick={() => step > 0 ? setStep((value) => value - 1) : onLogout()}>Retour</button><button disabled={loading}>{loading ? "Enregistrement..." : step === 4 ? "Commencer avec Orvix" : "Suivant"}</button></div>
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
  const googleButtonRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (mode !== "register" || !googleButtonRef.current) return;
    const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID?.trim();
    if (!clientId) { setError("La connexion Google n’est pas configurée."); return; }
    const render = () => {
      if (!window.google?.accounts?.id || !googleButtonRef.current) return;
      window.google.accounts.id.initialize({ client_id: clientId, callback: async (response: { credential: string }) => {
        setLoading(true); setError("");
        try { const result = await loginWithGoogle(response.credential); saveToken(result.token); onAuthenticated(result.user); }
        catch (e) { setError(e instanceof Error ? e.message : "Connexion Google impossible."); }
        finally { setLoading(false); }
      } });
      googleButtonRef.current.innerHTML = "";
      window.google.accounts.id.renderButton(googleButtonRef.current, { type: "standard", theme: "outline", size: "large", text: "continue_with", shape: "rectangular", width: Math.min(520, googleButtonRef.current.clientWidth || 520) });
    };
    if (window.google?.accounts?.id) render();
    else {
      const script = document.createElement("script"); script.src = "https://accounts.google.com/gsi/client"; script.async = true; script.onload = render; script.onerror = () => setError("Google est momentanément indisponible."); document.head.appendChild(script);
    }
  }, [mode, onAuthenticated]);

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
          try { const result = await loginWithGoogle(response.credential); saveToken(result.token); onAuthenticated(result.user); finish(resolve); }
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
      saveToken(result.token);
      onAuthenticated(result.user);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Connexion impossible.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="auth-page">
      <section className={`auth-panel auth-reference ${mode}`}>
        {mode === "register" && <div className="auth-topline"><button type="button" aria-label="Retour à la connexion" onClick={() => { setMode("login"); setRegisterStep("email"); setError(""); }}><ArrowLeft /></button><strong>Créer un compte</strong><span /></div>}
        <div className="auth-logo"><img className="auth-logo-image" src="/orvix-logo-transparent.png" alt="Logo Orvix" /><strong>ORVIX</strong><small>{mode === "login" ? "Votre IA. Vos documents. Nos réponses." : <>Commencez votre expérience avec <b>Orvix.</b></>}</small></div>
        {mode === "login" && <header className="auth-welcome"><h1>Bienvenue !</h1><p>Connectez-vous pour continuer<br />avec <b>Orvix.</b></p></header>}
        {mode === "register" && <>
          <div className="google-account-block">
            <p className="google-account-label">Compte récemment utilisé</p>
            <div ref={googleButtonRef} className="google-primary" aria-label="Continuer avec Google" />
          </div>
          <div className="auth-divider auth-divider-compact"><span />ou avec ton e-mail<span /></div>
        </>}
        <form onSubmit={submit} className="auth-form auth-reference-form">
          <div className="auth-input"><Mail size={20} /><input id="phone" aria-label="Adresse e-mail" type="email" value={phone} onChange={(event) => setPhone(event.target.value)} placeholder="Adresse e-mail" autoComplete="email" /></div>
          {(mode === "login" || registerStep === "password") && <div className="auth-input"><LockKeyhole size={20} /><input id="password" aria-label="Mot de passe" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Mot de passe" type={showPassword ? "text" : "password"} autoComplete={mode === "register" ? "new-password" : "current-password"} /><button type="button" className="password-visibility" onClick={() => setShowPassword((current) => !current)} aria-label={showPassword ? "Masquer le mot de passe" : "Afficher le mot de passe"}>{showPassword ? <EyeOff size={20} /> : <Eye size={20} />}</button></div>}
          {mode === "register" && registerStep === "password" && <div className="auth-input"><LockKeyhole size={20} /><input aria-label="Confirmer le mot de passe" value={passwordConfirmation} onChange={(event) => setPasswordConfirmation(event.target.value)} placeholder="Confirmer le mot de passe" type={showPassword ? "text" : "password"} autoComplete="new-password" /></div>}
          {mode === "login" && <button type="button" className="forgot-password">Mot de passe oublié ?</button>}
          {mode === "register" && registerStep === "password" && <label className="terms-check"><input type="checkbox" checked={acceptedTerms} onChange={(event) => setAcceptedTerms(event.target.checked)} /><span>J’accepte les <b>Conditions d’utilisation</b><br />et la <b>Politique de confidentialité.</b></span></label>}
          {error && <p className="error-banner">{error}</p>}
          <button className="auth-submit" disabled={!phone.trim() || loading || (mode === "login" && password.length < 6) || (mode === "register" && registerStep === "password" && (password.length < 6 || !acceptedTerms || password !== passwordConfirmation))}>{loading ? "Patientez…" : mode === "register" ? registerStep === "email" ? "Suivant" : "Créer le compte" : "Se connecter"}<span>→</span></button>
        </form>
        {mode === "login" && <><div className="auth-divider"><span />ou continuer avec<span /></div><div className="social-auth"><button type="button" className="google-login-button" title="Bientôt disponible"><svg className="google-icon" viewBox="0 0 24 24" aria-hidden="true"><path fill="#4285F4" d="M21.35 12.27c0-.71-.06-1.4-.18-2.05H12v3.88h5.24a4.48 4.48 0 0 1-1.94 2.94v2.45h3.14c1.84-1.7 2.91-4.2 2.91-7.22Z"/><path fill="#34A853" d="M12 21.6c2.63 0 4.84-.87 6.45-2.36l-3.14-2.45c-.87.58-1.98.92-3.31.92-2.54 0-4.7-1.72-5.47-4.03H3.28v2.53A9.74 9.74 0 0 0 12 21.6Z"/><path fill="#FBBC05" d="M6.53 13.68A5.85 5.85 0 0 1 6.22 12c0-.58.1-1.15.31-1.68V7.79H3.28A9.74 9.74 0 0 0 2.25 12c0 1.52.36 2.96 1.03 4.21l3.25-2.53Z"/><path fill="#EA4335" d="M12 6.29c1.43 0 2.71.49 3.72 1.45l2.79-2.79C16.84 3.36 14.63 2.4 12 2.4a9.74 9.74 0 0 0-8.72 5.39l3.25 2.53c.77-2.31 2.93-4.03 5.47-4.03Z"/></svg>Continuer avec Google</button></div></>}
        <p className="auth-switch">{mode === "register" ? "Déjà un compte ?" : "Pas encore de compte ?"}<button type="button" onClick={() => { setMode(mode === "register" ? "login" : "register"); setRegisterStep("email"); setError(""); }}>{mode === "register" ? "Se connecter" : "S’inscrire"}</button></p>
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

function ChatView({
  language,
  documents,
  onDocumentsChange,
  activeDocumentId,
  onActiveDocumentChange,
  documentIds,
  conversationId,
  onConversationChange,
  messages,
  onMessagesChange,
  onSaved,
}: {
  language: string;
  documents: DocumentInfo[];
  onDocumentsChange: (documents: DocumentInfo[]) => void;
  activeDocumentId: string;
  onActiveDocumentChange: (id: string) => void;
  documentIds: string[];
  conversationId: string;
  onConversationChange: (id: string) => void;
  messages: ChatMessage[];
  onMessagesChange: (messages: ChatMessage[]) => void;
  onSaved: () => Promise<void>;
}) {
  const [message, setMessage] = useState("");
  const [composerExpanded, setComposerExpanded] = useState(false);
  const [pendingMessage, setPendingMessage] = useState("");
  const [attachmentMenu, setAttachmentMenu] = useState(false);
  const [loading, setLoading] = useState(false);
  const [mobileComposer, setMobileComposer] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const attachmentInputRef = useRef<HTMLInputElement>(null);
  const composerRef = useRef<HTMLFormElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    const updateMobileComposer = () => setMobileComposer(window.innerWidth <= 900);
    updateMobileComposer();
    window.addEventListener("resize", updateMobileComposer);
    return () => window.removeEventListener("resize", updateMobileComposer);
  }, []);
  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    if (!mobileComposer) {
      textarea.style.removeProperty("height");
      textarea.style.removeProperty("overflow-y");
      return;
    }
    textarea.style.setProperty("height", "auto", "important");
    const styles = window.getComputedStyle(textarea);
    const lineHeight = Number.parseFloat(styles.lineHeight) || 18;
    const paddingTop = Number.parseFloat(styles.paddingTop) || 0;
    const paddingBottom = Number.parseFloat(styles.paddingBottom) || 0;
    const maxHeight = Math.ceil(lineHeight * 4 + paddingTop + paddingBottom);
    const nextHeight = Math.min(Math.max(textarea.scrollHeight, 28), maxHeight);
    textarea.style.setProperty("height", `${nextHeight}px`, "important");
    textarea.style.setProperty("overflow-y", textarea.scrollHeight > maxHeight ? "auto" : "hidden", "important");
  }, [message, mobileComposer]);
  useEffect(() => {
    if (!attachmentMenu) return;
    const closeMenu = (event: MouseEvent) => {
      if (!composerRef.current?.contains(event.target as Node)) setAttachmentMenu(false);
    };
    const closeOnEscape = (event: KeyboardEvent) => { if (event.key === "Escape") setAttachmentMenu(false); };
    document.addEventListener("mousedown", closeMenu);
    document.addEventListener("keydown", closeOnEscape);
    return () => { document.removeEventListener("mousedown", closeMenu); document.removeEventListener("keydown", closeOnEscape); };
  }, [attachmentMenu]);
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function sendValue(value: string) {
    if (!value || loading) return;
    const next = [...messages, { role: "user" as const, content: value }];
    onMessagesChange(next); setPendingMessage(value); setMessage(""); setComposerExpanded(false); setLoading(true);
    try {
      const result = await sendChat(value, messages.slice(-30), documentIds, conversationId);
      onConversationChange(result.conversation_id);
      onMessagesChange([...next, { role: "assistant", content: result.answer }]);
      await onSaved();
    } catch (error) {
      onMessagesChange([...next, { role: "assistant", content: error instanceof Error ? error.message : "Une erreur est survenue." }]);
    } finally { setLoading(false); setPendingMessage(""); }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    await sendValue(message.trim());
  }

  async function addSupports(files: FileList | null) {
    if (!files?.length) return;
    const result = await uploadDocuments(Array.from(files));
    onDocumentsChange(result.documents);
    const uploadedNames = new Set(Array.from(files).map((file) => file.name));
    const uploaded = [...result.documents].reverse().find((document) => uploadedNames.has(document.name));
    if (uploaded) onActiveDocumentChange(uploaded.id);
    setAttachmentMenu(false);
  }

  const activeDocument = documents.find((doc) => doc.id === activeDocumentId);
  const readingDocument = Boolean(documentIds.length) && needsDocumentContext(pendingMessage);
  const chatText = language === "English"
    ? { title: "What do you want to understand today?", hint: "Ask a question or choose a support from the input area.", placeholder: "Write your message…" }
    : language === "Italiano"
      ? { title: "Che cosa vuoi capire oggi?", hint: "Fai una domanda o scegli un documento dall’area di scrittura.", placeholder: "Scrivi il tuo messaggio…" }
      : language === "Español"
        ? { title: "¿Qué quieres comprender hoy?", hint: "Haz una pregunta o elige un documento desde la zona de entrada.", placeholder: "Escribe tu mensaje…" }
        : { title: "Que veux-tu comprendre aujourd’hui ?", hint: "Pose une question, ou choisis un support depuis la zone de saisie.", placeholder: "Écrivez votre message…" };
  const localizedStarters = language === "English"
    ? [{ title: "Explain to me", detail: "this lesson simply" }, { title: "Help me understand", detail: "a concept" }, { title: "Ask me questions", detail: "to revise" }, { title: "Summarize the document", detail: "selected" }]
    : language === "Italiano"
      ? [{ title: "Spiegami", detail: "questa lezione in modo semplice" }, { title: "Aiutami a capire", detail: "un concetto" }, { title: "Fammi delle domande", detail: "per ripassare" }, { title: "Riassumi il documento", detail: "selezionato" }]
      : language === "Español"
        ? [{ title: "Explícame", detail: "esta lección de forma sencilla" }, { title: "Ayúdame a entender", detail: "un concepto" }, { title: "Hazme preguntas", detail: "para repasar" }, { title: "Resume el documento", detail: "seleccionado" }]
        : starterPrompts;

  return <section className="chat-view">
    <div className="messages" aria-live="polite">
      {!messages.length && !loading && (
        <div className="chat-empty">
          <div className="brand chat-empty-brand"><img className="brand-logo" src="/orvix-logo-transparent.png" alt="Logo Orvix" /><span>ORVIX</span></div>
          <div className="orvix-introduction regular-welcome"><h1>{chatText.title}</h1><p>{chatText.hint}</p></div>
          <div className="starter-grid">
            {starterPrompts.map(({ prompt, icon: Icon }, index) => { const item = localizedStarters[index]; return <button key={prompt} onClick={() => setMessage(prompt)}><span><Icon size={30} /></span><strong>{item.title}</strong><small>{item.detail}</small><b>›</b></button>; })}
          </div>
        </div>
      )}
      {messages.map((item, index) => <ChatMessageBubble key={index} item={item} />)}
      {loading && <div className="message-row assistant"><span className="assistant-avatar">O</span><div className="message-stack"><div className="message reading-state"><span>{readingDocument ? (activeDocument ? `Lecture du Document ${activeDocument.number}` : "Recherche dans vos supports") : "Orvix vous répond"}</span>{readingDocument && <small>{activeDocument?.name || "Recherche des passages pertinents"}</small>}<div className="typing"><i /><i /><i /></div></div></div></div>}
      <div ref={bottomRef} />
    </div>
    <form ref={composerRef} className={`composer ${composerExpanded ? "has-message" : ""} ${message ? "is-typing" : ""} ${mobileComposer ? "mobile-flat-input" : ""}`} onSubmit={submit}>
      <div className="composer-tools">
        <button className="composer-support" type="button" onClick={() => setAttachmentMenu((open) => !open)} aria-expanded={attachmentMenu} aria-label="Ajouter une pièce jointe" title="Ajouter une pièce jointe"><Plus size={18} /></button>
        <input ref={attachmentInputRef} className="composer-file-input" type="file" multiple accept=".pdf,.txt,.md" onChange={(event) => addSupports(event.target.files)} />
        {attachmentMenu && <div className="attachment-menu">
          <button type="button" onClick={() => attachmentInputRef.current?.click()}><FileText size={17} /><span><strong>Ajouter un document</strong><small>PDF, TXT ou Markdown</small></span></button>
          <div className="attachment-future"><UploadCloud size={17} /><span><strong>Ajouter une image</strong><small>Analyse visuelle dans une prochaine phase</small></span><b>Bientôt</b></div>
        </div>}
      </div>
      <div className="composer-input-stack">
        <textarea ref={textareaRef} rows={1} value={message} onChange={(event) => { const value = event.target.value; setMessage(value); setComposerExpanded(value.includes("\n") || value.length > 72); }} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); } }} placeholder={chatText.placeholder} aria-label={chatText.placeholder} />
      </div>
      <button disabled={!message.trim() || loading} aria-label="Envoyer"><Send size={21} fill="currentColor" strokeWidth={1.5} /></button>
    </form>
  </section>;
}

function needsDocumentContext(value: string) {
  const normalized = value.toLocaleLowerCase("fr").replace(/[^a-zà-ÿ0-9' ]/g, " ").replace(/\s+/g, " ").trim();
  return !new Set(["bonjour", "bonsoir", "salut", "coucou", "hello", "hey", "merci", "merci beaucoup", "au revoir", "à bientôt", "a bientot", "comment vas tu", "comment allez vous", "ça va", "ca va", "qui es tu", "comment tu t'appelles", "comment tu t appelles"]).has(normalized);
}

function ChatMessageBubble({ item }: { item: ChatMessage }) {
  const time = new Date().toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
  const assistant = item.role === "assistant";
  return <div className={`message-row ${item.role}`}>
    {assistant && <span className="assistant-avatar">O</span>}
    <div className="message-stack">
      <div className="message">
        <FormattedMessage content={item.content} />
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
        const heading = line.match(/^#{1,3}\s+(.+)/);
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

function RevisionView({ documents, activeDocumentId, onActiveDocumentChange, documentIds }: { documents: DocumentInfo[]; activeDocumentId: string; onActiveDocumentChange: (id: string) => void; documentIds: string[] }) {
  const [topic, setTopic] = useState(""); const [content, setContent] = useState(""); const [loading, setLoading] = useState(false); const [error, setError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault(); if (!topic.trim()) return; setLoading(true); setError("");
    try { setContent((await createRevision(topic, documentIds)).content); } catch (e) { setError(e instanceof Error ? e.message : "Impossible de créer la fiche."); } finally { setLoading(false); }
  }
  return <section className="workspace-page">
    <PageIntro eyebrow="DOCUMENTS ET COURS" title="Réviser un support" description="Choisissez un document ou tous vos cours, puis demandez une fiche claire pour réviser." />
    <DocumentPicker documents={documents} activeDocumentId={activeDocumentId} onActiveDocumentChange={onActiveDocumentChange} />
    <form className="action-card" onSubmit={submit}><label htmlFor="revision-topic">Ce que tu veux réviser</label><div className="inline-form"><input id="revision-topic" value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="Ex. Résume le chapitre 2, prépare une fiche sur la photosynthèse..." /><button disabled={loading || !topic.trim()}><Sparkles size={18} />{loading ? "Création…" : "Créer la fiche"}</button></div></form>
    {error && <p className="error-banner">{error}</p>}
    {content ? <article className="result-card prose"><h2>Votre fiche</h2><p>{content}</p></article> : <EmptyState icon={<BookOpenText />} text="Votre prochaine fiche apparaîtra ici." />}
  </section>;
}

function QuizView({ documents, activeDocumentId, onActiveDocumentChange, documentIds }: { documents: DocumentInfo[]; activeDocumentId: string; onActiveDocumentChange: (id: string) => void; documentIds: string[] }) {
  const [topic, setTopic] = useState(""); const [quizType, setQuizType] = useState<"multiple_choice" | "traditional">("multiple_choice"); const [questionCount, setQuestionCount] = useState(3); const [quizTitle, setQuizTitle] = useState("Quiz Orvix"); const [questions, setQuestions] = useState<QuizQuestion[]>([]); const [selectedQuestions, setSelectedQuestions] = useState<Set<number>>(new Set()); const [answers, setAnswers] = useState<Record<number, number>>({}); const [writtenAnswers, setWrittenAnswers] = useState<Record<number, string>>({}); const [reviewed, setReviewed] = useState<Record<number, boolean>>({}); const [selfScores, setSelfScores] = useState<Record<number, boolean>>({}); const [loading, setLoading] = useState(false); const [exporting, setExporting] = useState(false); const [error, setError] = useState("");
  useEffect(() => {
    if (questions.length) window.setTimeout(() => window.scrollTo({ top: document.documentElement.scrollHeight, behavior: "smooth" }), 80);
  }, [questions.length]);
  const answeredCount = quizType === "multiple_choice" ? Object.keys(answers).length : Object.keys(selfScores).length;
  const score = quizType === "multiple_choice" ? questions.reduce((total, item, index) => total + (answers[index] === item.answer_index ? 1 : 0), 0) : Object.values(selfScores).filter(Boolean).length;
  const completed = Boolean(questions.length && answeredCount === questions.length);
  const activeDocument = documents.find((doc) => doc.id === activeDocumentId);
  const missedIndices = questions.map((_, index) => index).filter((index) => quizType === "multiple_choice" ? answers[index] !== questions[index].answer_index : selfScores[index] === false);
  async function submit(event: FormEvent) { event.preventDefault(); if (!topic.trim() && !documentIds.length) return; const quizTopic = topic.trim() || "Le contenu principal du support sélectionné"; setLoading(true); setError(""); setAnswers({}); setWrittenAnswers({}); setReviewed({}); setSelfScores({}); try { const result = await createQuiz(quizTopic, documentIds, questionCount, quizType); setQuestions(result.questions); setSelectedQuestions(new Set(result.questions.map((_, index) => index))); setQuizTitle(result.title); } catch (e) { setError(e instanceof Error ? e.message : "Impossible de créer le quiz."); } finally { setLoading(false); } }
  function toggleQuestion(index: number) { setSelectedQuestions((current) => { const next = new Set(current); if (next.has(index)) next.delete(index); else next.add(index); return next; }); }
  async function downloadWord() { const chosenQuestions = questions.filter((_, index) => selectedQuestions.has(index)); if (!chosenQuestions.length) return; setExporting(true); setError(""); try { const blob = await exportQuizWord(quizTitle, chosenQuestions, quizType); const url = URL.createObjectURL(blob); const link = document.createElement("a"); link.href = url; link.download = `${quizTitle.replace(/[^a-zA-ZÀ-ÿ0-9 -]/g, "").trim().replace(/\s+/g, "-").toLowerCase() || "quiz-orvix"}.docx`; link.click(); URL.revokeObjectURL(url); } catch (e) { setError(e instanceof Error ? e.message : "Téléchargement impossible."); } finally { setExporting(false); } }
  return <section className="workspace-page quiz-page">
    <div className="quiz-hero"><div><PageIntro eyebrow="" title="Quiz de leçon" description="Choisissez un document ou un thème. Orvix corrige vos réponses et vous indique quoi revoir." /></div><div className="quiz-illustration" aria-hidden="true"><div><CheckCircle2 size={26} /><FileText size={72} /><Sparkles size={22} /></div></div></div>
    <DocumentPicker documents={documents} activeDocumentId={activeDocumentId} onActiveDocumentChange={onActiveDocumentChange} />
    <form className="action-card quiz-card" onSubmit={submit}><div className="quiz-settings"><fieldset className="quiz-radio-fieldset"><legend>Type de questions</legend><div className="quiz-radio-group"><label><input type="radio" name="quiz-type" value="multiple_choice" checked={quizType === "multiple_choice"} onChange={() => { setQuizType("multiple_choice"); setQuestions([]); }} /><span>Choix multiple</span></label><label><input type="radio" name="quiz-type" value="traditional" checked={quizType === "traditional"} onChange={() => { setQuizType("traditional"); setQuestions([]); }} /><span>Questions traditionnelles</span></label></div></fieldset><label className="question-count"><span>Nombre de questions</span><select value={questionCount} onChange={(event) => { setQuestionCount(Number(event.target.value)); setQuestions([]); }}><option value={2}>2 questions</option><option value={3}>3 questions</option><option value={5}>5 questions</option><option value={10}>10 questions</option><option value={20}>20 questions</option><option value={50}>50 questions</option><option value={100}>100 questions</option><option value={150}>150 questions</option></select>{questionCount > 20 && <small>Génération par lots — la préparation peut prendre quelques minutes.</small>}</label><button className="quiz-generate-top" disabled={loading || (!topic.trim() && !documentIds.length)}><Plus size={18} />{loading ? `Préparation de ${questionCount} questions…` : "Générer le quiz"}</button></div><label htmlFor="quiz-topic">Leçon ou notion à tester <small>(optionnel)</small></label><div className="inline-form quiz-topic-line"><input id="quiz-topic" value={topic} onChange={(e) => setTopic(e.target.value)} placeholder={activeDocument ? `Facultatif — quiz sur le Document ${activeDocument.number}` : documentIds.length ? "Facultatif — quiz sur les supports sélectionnés" : "Ex. Les fonctions affines"} /></div></form>
    {error && <p className="error-banner">{error}</p>}
    {questions.length ? <div className="quiz-output-grid"><div><div className="quiz-progress"><span>Aperçu du quiz</span><div><strong>{questions.length} Questions</strong><small>{answeredCount}/{questions.length} réponses</small><span className="selection-actions"><button onClick={() => setSelectedQuestions(new Set(questions.map((_, index) => index)))}>Tout sélectionner</button><button onClick={() => setSelectedQuestions(new Set())}>Tout retirer</button></span><button className="word-download" onClick={downloadWord} disabled={exporting || !selectedQuestions.size}><Download size={16} />{exporting ? "Création…" : `Word (${selectedQuestions.size})`}</button></div></div>{questions.length ? <div className="quiz-list">{questions.map((item, index) => <article className={selectedQuestions.has(index) ? "question-card export-selected" : "question-card"} key={index}><button className="question-export-toggle" onClick={() => toggleQuestion(index)} aria-pressed={selectedQuestions.has(index)}>{selectedQuestions.has(index) ? "✓ Incluse" : "+ Word"}</button><span className="question-number">Question {index + 1}</span><h2>{item.question}</h2>{quizType === "multiple_choice" ? <><div className="choices">{item.choices.map((choice, choiceIndex) => { const selected = answers[index] === choiceIndex; const revealedChoice = answers[index] !== undefined; return <button key={choice} className={`${selected ? "selected" : ""} ${revealedChoice && choiceIndex === item.answer_index ? "correct" : ""}`} onClick={() => setAnswers({ ...answers, [index]: choiceIndex })}><span>{String.fromCharCode(65 + choiceIndex)}</span>{choice}</button>; })}</div>{answers[index] !== undefined && <p className={answers[index] === item.answer_index ? "feedback good" : "feedback"}><CheckCircle2 size={17} />{item.explanation}</p>}</> : <div className="traditional-answer"><textarea value={writtenAnswers[index] || ""} onChange={(event) => setWrittenAnswers({ ...writtenAnswers, [index]: event.target.value })} disabled={reviewed[index]} placeholder="Rédigez votre réponse avec vos propres mots…" />{!reviewed[index] ? <button type="button" disabled={!writtenAnswers[index]?.trim()} onClick={() => setReviewed({ ...reviewed, [index]: true })}>Voir la correction</button> : <div className="expected-answer"><strong>Réponse attendue</strong><p>{item.expected_answer}</p><small>{item.explanation}</small><div><button type="button" className={selfScores[index] === true ? "understood active" : "understood"} onClick={() => setSelfScores({ ...selfScores, [index]: true })}>J’avais compris</button><button type="button" className={selfScores[index] === false ? "review active" : "review"} onClick={() => setSelfScores({ ...selfScores, [index]: false })}>À revoir</button></div></div>}</div>}</article>)}</div> : null}</div><aside>{completed ? <QuizSummary score={score} total={questions.length} missedIndices={missedIndices} /> : <article className="quiz-advice-card"><span><BookOpenText size={20} /></span><h2>Conseil de révision</h2><p>Répondez aux questions, puis relisez seulement les notions marquées à revoir.</p></article>}</aside></div> : <EmptyState icon={<HelpCircle />} text="Votre quiz apparaîtra ici." />}
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

function SupportView({ documents, onDocumentsChange, activeDocumentId, onActiveDocumentChange }: { documents: DocumentInfo[]; onDocumentsChange: (documents: DocumentInfo[]) => void; activeDocumentId: string; onActiveDocumentChange: (id: string) => void }) {
  const [loading, setLoading] = useState(false); const [error, setError] = useState("");
  const [deletingId, setDeletingId] = useState("");
  const [search, setSearch] = useState("");
  useEffect(() => { listDocuments().then((r) => onDocumentsChange(r.documents)).catch(() => undefined); }, [onDocumentsChange]);
  async function upload(files: FileList | null) { if (!files?.length) return; setLoading(true); setError(""); try { onDocumentsChange((await uploadDocuments(Array.from(files))).documents); } catch (e) { setError(e instanceof Error ? e.message : "Import impossible."); } finally { setLoading(false); } }
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
  return <section className="workspace-page">
    <PageIntro eyebrow="VOTRE BIBLIOTHÈQUE" title="Supports de cours" description="Ajoutez vos documents pour que les réponses, fiches et quiz utilisent votre contenu." />
    <DocumentPicker documents={documents} activeDocumentId={activeDocumentId} onActiveDocumentChange={onActiveDocumentChange} />
    <input className="document-search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Chercher un document par nom ou numéro..." />
    <label className="upload-zone"><UploadCloud size={34} /><strong>{loading ? "Import en cours…" : "Déposez ou sélectionnez vos fichiers"}</strong><span>PDF, TXT ou Markdown · 10 Mo maximum par fichier</span><input type="file" multiple accept=".pdf,.txt,.md" onChange={(e) => upload(e.target.files)} disabled={loading} /></label>
    {error && <p className="error-banner">{error}</p>}
    <div className="document-grid">{visibleDocuments.map((doc) => <article className={activeDocumentId === doc.id ? "document-card active" : "document-card"} key={doc.id}><button className="document-select" onClick={() => onActiveDocumentChange(activeDocumentId === doc.id ? "" : doc.id)}><span className="document-number">{doc.number}</span><span className="file-icon"><FileText /></span><span className="document-details"><strong>{doc.name}</strong><small>{(doc.size / 1024).toFixed(1)} Ko</small></span></button><button className="document-delete" onClick={() => remove(doc)} disabled={deletingId === doc.id} aria-label={`Supprimer ${doc.name}`} title="Supprimer le document"><Trash2 size={17} /></button></article>)}</div>
    {!documents.length && <EmptyState icon={<FileText />} text="Aucun support importé pour le moment." />}
    {Boolean(documents.length && !visibleDocuments.length) && <EmptyState icon={<FileText />} text="Aucun document ne correspond à cette recherche." />}
  </section>;
}

function EmptyState({ icon, text }: { icon: React.ReactNode; text: string }) { return <div className="empty-state"><span>{icon}</span><p>{text}</p></div>; }
export default App;
