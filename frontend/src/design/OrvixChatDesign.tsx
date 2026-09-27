import "./orvix-design.css";

const conversations = [
  "Comprendre les fractions",
  "Réviser la photosynthèse",
  "Préparer mon quiz",
];

export default function OrvixChatDesign() {
  return (
    <div className="orvix-design-lab">
      <aside className="orvix-lab-sidebar">
        <div className="orvix-lab-brand"><img src="/orvix-logo-transparent.png" alt="Orvix" /><strong>ORVIX</strong><span>☰</span></div>
        <nav className="orvix-lab-nav">
          <button className="is-active">◯ <span>Chat</span></button>
          <button>▣ <span>Révision</span></button>
          <button>ⓘ <span>Quiz</span></button>
          <button>▤ <span>Supports</span></button>
        </nav>
        <div className="orvix-lab-discussions"><div><small>DISCUSSIONS</small><button>+</button></div><button className="new-discussion">◯ <span>Nouvelle discussion</span></button>{conversations.map((conversation) => <button key={conversation}>◌ <span>{conversation}</span></button>)}</div>
        <div className="orvix-lab-profile"><b>O</b><span><strong>Olivia Martin</strong><small>Forfait Gratuit</small></span><em>⌄</em></div>
      </aside>
      <main className="orvix-lab-main">
        <header className="orvix-lab-header"><button className="question-select">Question libre <span>⌄</span></button><div><button>▧</button><button>♧</button></div></header>
        <section className="orvix-lab-stage">
          <div className="orvix-lab-ambient" aria-hidden="true"><i /><i /><i /></div>
          <div className="orvix-lab-empty"><img src="/orvix-logo-transparent.png" alt="" /><h1>Que veux-tu comprendre<br /><em>aujourd’hui ?</em></h1><p>Une question, une idée ou une notion à explorer.</p></div>
          <form className="orvix-lab-composer" onSubmit={(event) => event.preventDefault()}><button type="button">+</button><input placeholder="Écrivez votre message..." aria-label="Écrivez votre message..." /><button type="submit" aria-label="Envoyer">➤</button></form>
        </section>
      </main>
    </div>
  );
}
