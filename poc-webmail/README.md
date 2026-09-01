# POC interface AtomBox (D79/D80)

Maquette **statique**, sur **fixtures** — aucun backend, aucune installation.
Ouvrir `index.html` dans un navigateur : c'est tout.

> Les scripts sont **classiques**, pas des modules ES : `import` est bloqué par CORS
> en `file://`, et ce POC doit rester ouvrable par double-clic. L'ordre de chargement
> déclaré dans `index.html` **est** la déclaration des dépendances.

## Le vrai livrable : le panneau « requêtes »

Chaque geste journalise **la question qu'il pose aux données** et l'index qu'elle
suppose. ⚠ en orange = coûteux ou non indexé, badge `API` = appel entre AtomBox et une
application connectée. C'est cette liste — et non les écrans — qui dictera les index du
schéma.

## Architecture

Quatre couches, une dépendance à sens unique : `core → services → views → controllers`.

```
index.html              structure + ordre de chargement
css/app.css
js/core/       prng      aléatoire déterministe (le corpus doit être reproductible)
               format    échappement, dates, poids, montants
               dom       accès au DOM, volontairement minimal
               bus       événements : un service n'appelle jamais une vue
               registry  vues partielles surchargeables
               store     état + persistance localStorage
js/services/   query-log     le journal (le livrable)
               attachments   magasin d'octets dédupliqué
               erp           applications connectées
               fixtures      axes, dossiers, identités
               corpus        génération, vues, filtres, compteurs
               messages      les gestes métier (lire, archiver, corbeille…)
               compose       préparer, fabriquer, envoyer
js/views/      partials + partials-overrides, nav, list, message, compose, tabs, query-log
js/controllers/ app, nav, list, tabs, message, compose
js/app.js      amorçage — le seul fichier qui a le droit de tout connaître
test/          fake-dom, run (harnais), smoke (parcours), metrics
```

**Les vues sont des fonctions `(contexte) → HTML`**, sans effet de bord ; les contrôleurs
peignent et câblent ; les services ne connaissent ni le DOM ni les vues — ils émettent sur
le bus, et `js/app.js` décide de la conséquence à l'écran.

### Vues partielles surchargeables

Une carte de message est découpée en `header` / `body` / `meta` / `actions` plutôt qu'en un
bloc : c'est ce découpage qui rend la surcharge utile. Un dossier qui veut afficher « À : »
au lieu de l'expéditeur ne réécrit pas la carte, il remplace l'en-tête.

```js
Registry.define   ("message.card.header", ctx => …)          // socle
Registry.defineFor("message.card.header", "sent", ctx => …)  // spécialisation
Registry.render   ("message.card", { m, variant: "sent" })
```

La variante est calculée par `views/list.js` : le dossier d'abord (`sent`), sinon **l'axe**,
et seulement si une partielle existe pour lui. **Enregistrer une partielle sous le nom d'un
axe suffit donc à changer son affichage**, sans toucher à la liste. Les surcharges livrées
sont dans `views/partials-overrides.js` — supprimer ce fichier ne casse rien, tout retombe
sur le socle :

| Variante | Ce qu'elle change |
|---|---|
| `sent` | l'en-tête montre le **destinataire**, pas l'expéditeur |
| `notification` | pas de snippet, pas de tags — juste la source (elles sont nombreuses et répétitives) |
| `sav` | la référence du ticket et son **statut** passent avant tout le reste |
| `social` | ni pièces jointes ni tags : le réseau d'origine suffit |

## Persistance — et ce qu'elle démontre

Le **corpus** (≈ 4 400 messages, 273 dossiers) est **engendré** à chaque chargement, de
façon déterministe, en une soixantaine de millisecondes. Ce qui est stocké, c'est le
**rattachement** : lu, sorti de la file, déplacé, supprimé — quelques kilo-octets.

C'est exactement le partage du modèle (D36) : le message est un fait, le rattachement est
ce que le compte en a fait. Le bouton `⟲` de l'en-tête oublie l'état local et repart des
fixtures.

Les gestes sont donc **réels** : marquer lu, traiter, archiver, remettre en file, mettre à
la corbeille, restaurer, supprimer définitivement, marquer indésirable, déplacer vers un
dossier utilisateur. Chacun modifie l'état, met à jour les compteurs de l'arborescence —
et journalise sa requête.

Deux d'entre eux méritent le détour :

- **Vider la corbeille** montre que la déduplication impose un **ramasse-miettes** : rien
  ne s'efface en cascade depuis un compte, ni le message (d'autres comptes le portent), ni
  le blob d'une pièce jointe (d'autres liaisons le citent).
- **Remettre dans la file** rouvre Q09 : si `sorti_le` est la clé de partition, un retour
  est un déplacement de partition. Le geste existe, reste à décider s'il est courant.

## Onglets

Deuxième ligne d'en-tête, toujours visible. Un clic ouvre un onglet **provisoire**
(italique), remplacé par le clic suivant ; un **double-clic** l'épingle ; le clic du milieu
ou la croix ferme. Les onglets survivent au rechargement.

Le journal en tire deux enseignements : **changer d'onglet ne coûte aucune requête** (à
condition d'avoir chargé le corps *avec* le message, une requête et non deux), et
**restaurer une session en coûte une seule** (`WHERE message_id = ANY(:ids)`), pas une par
onglet.

## Composition

Trois écrans — nouveau message, répondre / répondre à tous, transférer — ouverts comme des
onglets, donc plusieurs à la fois. Chacun affiche la décision qui le rend particulier
plutôt que de la subir :

- **Répondre** présélectionne l'identité de la **boîte qui a reçu**, pas celle du compte
  (Q26), et le dit — répondre depuis une autre identité ampute le fil pour les collègues
  qui partagent la boîte.
- **Transférer** propose le mode : *par référence* (aucune copie, un lien + une ACL —
  D58/D67, et un lien qui peut mourir, Q30) ou *par valeur* (l'original encapsulé en
  `message/rfc822`, seule forme envoyable à l'extérieur — D66).
- **Envoyer** répartit les destinataires : les **internes** sont livrés en base sans passer
  par le SMTP (D12), les externes partent au relais. Un envoi **mixte** lève un
  avertissement — c'est là que se règle le risque de double livraison, pas dans Postfix.

Les brouillons se rouvrent dans l'état où ils ont été laissés.

## Pièces jointes

Un **blob** (octets, sha256, type *détecté*) et une **liaison** (nom de fichier, type
*déclaré*, encodage) — D32. Quatre blobs récurrents (signature d'entreprise sur 1 284
messages, CGV sur 96, tarifs sur 41) matérialisent l'intérêt de la déduplication ; le reste
est unique, ce qui est le cas le plus fréquent.

Cliquer une pièce jointe journalise trois questions : l'ouvrir, **remonter aux autres
messages qui portent les mêmes octets** (sans ce sens de parcours, la dédup n'est qu'un
gain de disque), et — sur une photo non optimisée — la recompression, avec son
avertissement : le blob est partagé, le recompresser modifie l'octet de *tous* les porteurs.

> **Sur les volumes** : les tailles et fréquences sont **calées** pour que le corpus tombe
> autour de 100 ko par message sur le fil — l'hypothèse du chapitre 08. Un tirage uniforme
> donnerait plus d'un méga, et la maquette raconterait un volume qu'elle n'a pas mesuré.
> `node test/metrics.js` affiche la moyenne obtenue en face de l'hypothèse. La vraie
> distribution ne se saura qu'en ingérant le pilote — c'est l'une des premières choses
> qu'il devra produire.

## Intégration ERP — les deux sens

Un message tagué `client`, `fournisseur`, `sav` ou `partenaire` affiche le contexte métier
de l'application connectée : tiers, référence externe, encours, échu, pièces liées et leur
statut. **Aucun de ces montants n'est stocké** — le cadre est rempli par un appel à
l'application, ce que la maquette signale comme le premier besoin de cache (Q31).

| Geste | Ce qu'il montre |
|---|---|
| **D'où vient ce rattachement ?** | l'adresse pointe une identité, l'identité pointe le tiers de chaque application (D35) |
| **Lier à une pièce** | l'unicité `(axe, application, valeur)` — quatre Dolibarr, quatre jeux de tags, aucun écrasement (D17/D20) |
| **Ce que Dolibarr affiche de son côté** | l'API **consommée par l'ERP** : pagination par curseur, portée du token appliquée côté AtomBox (D18/D37) |
| **Notifier l'application** | l'événement sortant en file rejouable : une application injoignable ne bloque jamais la réception |

## Ce qu'elle éprouve

| | Décision |
|---|---|
| Arborescence **engendrée** depuis les axes (200 fournisseurs, 52 clients…) | D76, D77 |
| Recherche dans l'arborescence (croix / `Échap`) + « voir les N autres » | D77 |
| Dossiers **spéciaux** (vues) vs **utilisateur** vs **virtuels** ; « Traités » et « Archives » sont des vues sur `motif_sortie` | D30, D51, D75 |
| Filtres (en file / non lus / récents / PJ / lourds / sortis) × tris | D16 |
| Fil de discussion, tags multi-applications sans écrasement | D55, D17, D20 |
| Pièces jointes : dédup, MIME déclaré vs détecté, recompression, `.eml` réversible | D11, D24, D25, D26, D32, D69, D70 |
| Composition : identité de boîte, transfert par référence, envoi interne hors SMTP | Q26, D58, D66, D67, D12, D10 |
| État réel : lu, traité, archivé, corbeille, suppression, dossiers | D36, D41, D30, D51 |

## Tests

```
node test/smoke.js     # parcours fonctionnel complet (50 assertions)
node test/metrics.js   # cardinalité et volumes du corpus
```

Le harnais lit les `<script src>` de `index.html` **dans l'ordre déclaré** : une dépendance
mal placée casse le test avant de casser le navigateur. `test/fake-dom.js` est un DOM
minimal — il ne rend rien, il vérifie que le câblage tient.

## Responsive — quatre paliers

| Largeur | Disposition |
|---|---|
| **> 1240 px** | 4 colonnes : arborescence · liste · message · requêtes |
| **980 – 1240** | 3 colonnes ; le panneau **requêtes** passe en tiroir droit |
| **760 – 980** | 2 colonnes ; l'**arborescence** passe en tiroir gauche (☰) |
| **< 760 px** | 1 colonne, navigation par **vues** : dossiers → liste → message |

Le point à juger en petite largeur : une arborescence de 200 fournisseurs y est inutilisable
sans le filtre de dossiers et le repli par axe — c'est ce que ce palier rend évident.

## Ce qu'elle ne prouve PAS

Rien sur la **performance** : tout est instantané sur des fixtures, et les requêtes du
journal ne sont jamais exécutées. Une UI validée ici peut s'effondrer à 5 M messages — cela
se vérifiera au POC suivant, sur corpus injecté (chapitre 08).
