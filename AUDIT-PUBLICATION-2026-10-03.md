# Comparaison avant publication — 3 octobre 2026

Périmètre : parcours visibles du compte connecté sur app.orvix.work, code de production 2852060, comparaison avec les modifications locales et tests backend. Ce contrôle ne constitue pas un audit exhaustif de sécurité, de paiement réel ou de qualité des réponses du modèle.

| Fonction | État constaté | Décision |
|---|---|---|
| Chat, historique, choix des supports, sources consultables | Présents en ligne | Conservés |
| Révisions essentielles, guidées et express | Présentes en ligne | Conservées ; mémoire existante ajoutée au contexte de génération |
| Quiz QCM/rédigés et choix du nombre de questions | Présents en ligne | Conservés ; adaptation aux difficultés pertinentes |
| Profil, abonnement, langue, apparence, aide et à propos | Entrées présentes | Aucun second écran ajouté |
| Aide | Court panneau de démarrage observé | Le centre d'aide enrichi local n'est pas actuellement publié |
| Stockage durable des documents | uploaded_documents et index document_memory présents dans le code récent | Conservation intégrale ; exclusion du stockage concurrent user_documents |
| Mémoire d'apprentissage | Moteur structuré et routes de consultation/suppression existants | Réutilisation ; exclusion de l'ancienne mémoire locale concurrente |
| Intention, pédagogie, vérification | learning_engines déjà intégré | Extension du moteur existant, aucun moteur parallèle |
| Règles adaptatives détaillées | Absentes de cette version de production | Politique commune pour chat, générations structurées et Core |
| Relances documentaires | Recherche limitée au message actuel | Reprise du dernier sujet utilisateur, sans reprendre un sujet remplacé |
| Messages multiligne | Ancienne extraction du dernier paragraphe | Séparation des consignes et du message complet |
| Conversations longues | Limite d'entrée également appliquée aux réponses stockées | Modèle distinct pour messages enregistrés, historique serveur prioritaire |
| Progression réellement évaluée | Mémoire avec scores heuristiques, pas preuve de maîtrise | Ne pas présenter les déclarations comme une maîtrise validée |
| Flashcards et révision espacée | Pas de parcours dédié confirmé dans les écrans inspectés | Non ajoutés implicitement à cette publication |

## Limites et points restant à traiter

- La bibliothèque du compte inspecté affichait zéro support ; cela ne prouve pas que tous les fichiers des autres comptes ont disparu ou ont été récupérés.
- D'anciens messages contiennent « ORVIX est momentanément inaccessible ». Leur présence dans l'historique ne prouve pas une panne actuelle.
- Le profil affichait Gratuit tandis que le menu indiquait Étudiant : incohérence d'affichage à vérifier avec le statut serveur.
- Les versions locales enrichies d'Aide, À propos et Apparence ne correspondent pas au frontend publié. Leur réintégration demande une comparaison dédiée ; le frontend actuel est conservé pour cette publication backend.
- Le contrôle déterministe des réponses garantit certaines règles de format/source, pas la vérité de chaque affirmation. La qualité pédagogique exige encore des essais avec le modèle réel.
- Le stockage et les schémas de mémoire existants ne sont pas remplacés. Aucune clé SSH ni nouvelle autorisation d'accès n'est créée.

## Validation

41 tests automatisés passent, plus 6 sous-tests : règles partagées, stratégie, relances, conservation des messages multiligne, mémoire des quiz, historique long, isolation documentaire, authentification et quotas couverts par les tests existants. Génération IA simulée dans les tests ; pas de paiement réel ni d'import des fichiers privés pour le contrôle.

Coordination : la tâche « Lancer le site » a confirmé suspendre ses modifications/publications concurrentes. Base de publication : 28520605d57088d28dae2c49fb08e3683d16f4e2. Publication par commit ciblé et push non forcé vers main.
