const appUrl = window.ORVIX_CONFIG?.appUrl;
if (appUrl) {
  const target = new URL(appUrl);
  if (target.protocol === 'https:') {
    document.querySelectorAll('[data-app-link]').forEach(link => {
      link.href = target.href;
    });
  }
}

const menuButton = document.querySelector('.menu-toggle');
const nav = document.querySelector('.site-nav');
menuButton?.addEventListener('click', () => {
  const open = menuButton.getAttribute('aria-expanded') === 'true';
  menuButton.setAttribute('aria-expanded', String(!open));
  menuButton.setAttribute('aria-label', open ? 'Ouvrir le menu' : 'Fermer le menu');
  nav?.classList.toggle('open', !open);
});
nav?.querySelectorAll('a').forEach(link => link.addEventListener('click', () => {
  nav.classList.remove('open');
  menuButton?.setAttribute('aria-expanded', 'false');
  menuButton?.setAttribute('aria-label', 'Ouvrir le menu');
}));
document.getElementById('year').textContent = String(new Date().getFullYear());
const billingButtons = document.querySelectorAll('[data-billing]');
let billingCycle = 'monthly';
let livePlans = null;
let currency = 'USD';
const fallbackPlans = {
  free: { monthly_price: 0, annual_price: 0, documents: 1 },
  student: { monthly_price: 4.99, annual_price: 49.9, documents: 10 },
  pro: { monthly_price: 9.99, annual_price: 99.9, documents: 30 },
};
function renderPrices() {
  const formatMoney = amount => new Intl.NumberFormat('fr-FR', { style: 'currency', currency }).format(amount);
  document.querySelectorAll('[data-plan]').forEach(card => {
    const id = card.dataset.plan;
    const plan = livePlans?.find(item => item.id === id) || fallbackPlans[id];
    if (!plan) return;
    const price = card.querySelector('[data-price]');
    const period = card.querySelector('[data-period]');
    const documents = card.querySelector('[data-documents]');
    const comparison = card.querySelector('[data-annual-comparison]');
    const paidLabel = card.querySelector('[data-paid-label]');
    if (id === 'free') { price.textContent = 'Gratuit'; period.textContent = 'offre Free'; }
    else {
      const amount = billingCycle === 'annual' ? plan.annual_price : plan.monthly_price;
      price.textContent = formatMoney(amount);
      period.textContent = billingCycle === 'annual' ? '/ an' : '/ mois';
      if (paidLabel) paidLabel.hidden = billingCycle !== 'annual';
      if (comparison) {
        comparison.hidden = billingCycle !== 'annual';
        const regularTotal = Math.round(Number(plan.monthly_price) * 12 * 100) / 100;
        const savings = Math.round((regularTotal - Number(plan.annual_price)) * 100) / 100;
        comparison.querySelector('[data-original]').textContent = formatMoney(regularTotal);
        comparison.querySelector('[data-savings]').textContent = formatMoney(savings);
      }
    }
    if (documents) documents.textContent = String(plan.documents);
  });
}
billingButtons.forEach(button => button.addEventListener('click', () => {
  billingCycle = button.dataset.billing;
  billingButtons.forEach(item => { const active = item === button; item.classList.toggle('active', active); item.setAttribute('aria-pressed', String(active)); });
  renderPrices();
}));
renderPrices();
fetch('https://orvix-production.up.railway.app/api/v1/subscription/plans')
  .then(response => { if (!response.ok) throw new Error('Tarifs indisponibles'); return response.json(); })
  .then(config => { if (Array.isArray(config.plans)) { livePlans = config.plans; currency = config.currency || 'USD'; renderPrices(); } })
  .catch(() => { /* Les derniers tarifs vérifiés restent affichés si l’API est indisponible. */ });
if ('IntersectionObserver' in window && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
  const observer = new IntersectionObserver(entries => entries.forEach(entry => {
    if (entry.isIntersecting) { entry.target.classList.add('visible'); observer.unobserve(entry.target); }
  }), { threshold: 0.09, rootMargin: '0px 0px -30px 0px' });
  document.querySelectorAll('.reveal').forEach(element => observer.observe(element));
} else document.querySelectorAll('.reveal').forEach(element => element.classList.add('visible'));
