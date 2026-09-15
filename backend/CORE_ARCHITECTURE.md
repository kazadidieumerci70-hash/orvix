# ORVIX Core Engine

Le Core Engine est une couche native, indépendante du frontend et des fournisseurs IA.
Son orchestrateur normalise l’entrée, détermine l’intention, applique les politiques et
retourne une réponse structurée. Les adaptateurs de modèles et les outils seront ajoutés
derrière cette frontière sans rendre un service cloud obligatoire.

Flux : client authentifié → `/core/process` → input/intention → décision → réponse.
L’identité utilisateur est fournie par le token backend et n’est jamais acceptée depuis
le corps de la requête.

La mémoire persistante, les files de tâches et le stockage partagé restent les prochaines
étapes de migration vers PostgreSQL/Redis/object storage pour le scaling horizontal.
