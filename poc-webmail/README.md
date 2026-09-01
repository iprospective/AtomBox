# POC interface AtomBox (D79/D80)

Maquette **statique**, sur **fixtures** — aucun backend. Ouvrir `index.html` dans un
navigateur, rien à installer.

## Ce qu'elle éprouve

| | Décision |
|---|---|
| Arborescence **engendrée** depuis les axes (200 fournisseurs, 52 clients…) | D76, D77 |
| Recherche **dans** l'arborescence + « voir les N autres » | D77 |
| Dossiers **spéciaux** (vues) vs **utilisateur** vs **virtuels** | D51, D75 |
| Recherche **récursive** = le prédicat parent, sans parcours d'arbre | D77 |
| Filtres (non lus / récents / avec PJ) × tris (date, expéditeur, sujet, taille) | D16 |
| Fil de discussion, tags multi-applications sans écrasement | D55, D17, D20 |
| Gestes : répondre depuis la boîte, transférer par référence, traiter, archiver | Q26, D58, D30 |

## Le vrai livrable : le panneau « requêtes »

Chaque geste journalise **la question qu'il pose aux données** et l'index qu'elle suppose.
⚠ en orange = coûteux ou non indexé. C'est cette liste — et non les écrans — qui dictera
les index du schéma.

## Cardinalité (D80)

L'arborescence est à l'échelle réelle : c'est elle qui décide de la conception de l'écran.
Le nombre de messages par dossier reste modeste (~15-40), sans incidence sur ce qu'on
cherche à valider ici.

Le panneau se **masque** par le bouton `⟨/⟩ requêtes` du bandeau (ou `Échap`), et le choix
est mémorisé d'une visite à l'autre.

## Responsive — quatre paliers

| Largeur | Disposition |
|---|---|
| **> 1240 px** | 4 colonnes : arborescence · liste · message · requêtes |
| **980 – 1240** | 3 colonnes ; le panneau **requêtes** passe en tiroir droit |
| **760 – 980** | 2 colonnes (liste · message) ; l'**arborescence** passe en tiroir gauche (☰) |
| **< 760 px** | 1 colonne, navigation par **vues** : dossiers → liste → message, avec barre de retour |

Le point à juger en petite largeur : une arborescence de 200 fournisseurs y est
inutilisable sans le filtre de dossiers et le repli par axe — c'est ce que ce palier rend
évident.

## Ce qu'elle ne prouve PAS

Rien sur la **performance** : tout est instantané sur des fixtures. Une UI validée ici peut
s'effondrer à 5 M messages — cela se vérifiera au POC suivant, sur corpus injecté
(chapitre 08).
