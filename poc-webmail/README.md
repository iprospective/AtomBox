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
| Filtres (non lus / récents / avec PJ / lourds) × tris (date, expéditeur, sujet, taille) | D16 |
| Fil de discussion, tags multi-applications sans écrasement | D55, D17, D20 |
| Gestes : répondre depuis la boîte, transférer par référence, traiter, archiver | Q26, D58, D30 |
| **Pièces jointes** : magasin dédupliqué, MIME déclaré vs détecté, recompression | D11, D24, D32, D69, D70 |
| **Réversibilité** : téléchargement du `.eml` original reconstruit | D25, D26 |
| **Intégration ERP** dans les deux sens : contexte métier + API consommée par l'ERP | D03, D19, D20, D21, D35 |

## Le vrai livrable : le panneau « requêtes »

Chaque geste journalise **la question qu'il pose aux données** et l'index qu'elle suppose.
⚠ en orange = coûteux ou non indexé. C'est cette liste — et non les écrans — qui dictera
les index du schéma.

## Pièces jointes — en conditions réelles

Les fixtures portent de **vraies** pièces jointes : un blob (octets, hash, type **détecté**)
et une liaison (nom de fichier, type **déclaré**, encodage). Quatre blobs **récurrents**
— signature d'entreprise sur 1 284 messages, CGV sur 96, tarifs sur 41 — matérialisent à
eux seuls l'intérêt de la déduplication ; le reste des fichiers est unique, ce qui est
justement le cas le plus fréquent.

Cliquer une pièce jointe journalise trois questions : l'ouvrir, **remonter aux autres
messages qui portent les mêmes octets** (le sens de parcours sans lequel la dédup n'est
qu'un gain de disque), et — sur une photo non optimisée — la recompression, avec son
avertissement : le blob est partagé, le recompresser modifie l'octet de *tous* les porteurs.

Le poids affiché distingue les octets **décodés** de ceux **sur le fil** (+37 % en base64,
D69) : c'est cet écart qui explique l'audit de dimensionnement du chapitre 08.

## Intégration ERP — les deux sens

Un message tagué `client`, `fournisseur`, `sav` ou `partenaire` affiche le **contexte
métier** de l'application connectée : tiers et sa référence externe, encours, échu, pièces
liées (devis, commandes, factures) avec leur statut. **Aucun de ces montants n'est stocké
par AtomBox** — le cadre est rempli par un appel à l'application, ce que la maquette
signale explicitement : c'est le premier endroit où il faudra un cache.

Quatre gestes journalisent l'intégration :

| Geste | Ce qu'il montre |
|---|---|
| **D'où vient ce rattachement ?** | l'adresse pointe une identité, l'identité pointe le tiers de chaque application (D35) |
| **Lier à une pièce** | l'unicité `(axe, application, valeur)` — quatre Dolibarr, quatre jeux de tags, aucun écrasement (D17/D20) |
| **Ce que Dolibarr affiche de son côté** | l'API **consommée par l'ERP** : pagination par curseur (un ERP pagine profond) et portée du token appliquée côté AtomBox (D18/D37) |
| **Notifier l'application** | l'événement sortant en file rejouable : une application injoignable ne bloque jamais la réception |

Les appels d'API sont marqués `API` dans le journal et liserés de bleu, pour les
distinguer des requêtes internes.

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
