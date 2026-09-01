# POC interface AtomBox (D79/D80)

Maquette **statique**, sur **fixtures** — aucun backend, aucune installation.
Ouvrir `index.html` dans un navigateur : c'est tout.

> Les scripts sont **classiques**, pas des modules ES : `import` est bloqué par CORS
> en `file://`, et ce POC doit rester ouvrable par double-clic. L'ordre de chargement
> déclaré dans `index.html` **est** la déclaration des dépendances.

## Le vrai livrable : la trace des gestes

Ce n'est pas un journal de requêtes SQL : c'est la **cascade complète** d'un geste, dans
l'ordre d'exécution. Ouvrir un message déroule dix-sept étapes — le clic, le cache client,
l'appel HTTP, la route, le contrôleur, la vérification de portée, les quatre requêtes, la
lecture du magasin d'octets, le JSON renvoyé, le rendu, puis l'appel à l'ERP et l'écriture
du « lu ».

Une barre de côté marque les passages de frontière : ce qui est **navigateur**, ce qui
traverse le **réseau**, ce qui tourne sur le **serveur qui reste à écrire**. Chaque étape
porte son type, son détail (code, SQL, JSON, signature de méthode), l'index qu'elle suppose
et un ⚠ quand elle est coûteuse, fragile ou non tranchée.

| Type | Ce qu'il montre |
|---|---|
| `ui` `render` `cache` | ce qui se passe dans le navigateur, y compris ce qu'on **évite** de demander |
| `http` `json` | l'aller-retour — et le **contrat d'API**, en JSON réel construit sur le message affiché |
| `route` `ctrl` `svc` `acl` | ce qu'il faudra écrire : la route, le contrôleur, le service, la vérification de portée |
| `sql` `blob` `event` | les requêtes, la lecture du magasin d'octets, les événements sortants |

**C'est ce fichier qui sert de support de CDC** : `js/services/api-trace.js` décrit la
surface d'API par les gestes qui l'appellent. Écrire le serveur, ce sera écrire ce qui y est
décrit ; tout champ absent du JSON est une colonne dont personne n'a encore eu besoin.

> **Hypothèse de travail, à ne pas confondre avec une décision** : une API REST, une
> ressource par concept du modèle. **Q07 n'est pas tranchée.** Un point d'entrée unique
> (GraphQL, RPC) donnerait une autre cascade — moins d'allers-retours, plus de complexité
> serveur. La trace est faite pour rendre la comparaison possible : **lire une cascade et
> compter ses passages de réseau** est le moyen le plus direct de trancher Q07.

Trois constats sortent déjà de la lecture des cascades :

- **Ouvrir un message tagué coûte deux allers-retours**, dont un vers une application
  qu'AtomBox ne contrôle pas. C'est Q31, et c'est la raison pour laquelle le cadre métier
  doit se remplir *après* le message.
- **Le paramètre `inclure` n'est pas un confort** : sans lui, ouvrir un message demande le
  corps, puis les pièces jointes, puis le fil — trois allers-retours pour un clic.
- **La portée est dans la requête, pas avant elle** : un message hors portée n'existe pas,
  donc 404 et non 403 — il n'y a rien à vérifier puisqu'il n'y a rien à trouver.

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
js/services/   query-log     la trace : un geste = une suite d'étapes typées
               api-trace     LA SURFACE D'API, décrite par les gestes — le support de CDC
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

## Le statut de traitement — un workflow, pas un tag

C'est la décision la plus structurante de ce tour. Un tag « à faire » aurait été un abus :

| | Tag | Statut |
|---|---|---|
| Rôle | **classer** | **piloter** |
| Forme | ouvert, extensible | **fermé**, un petit nombre d'états connus |
| Ordre | aucun | **ordonné** — nouveau → à faire → en cours → en attente → traité |
| Portée | le **message** (D17), interopérable entre applications | le **rattachement** — chacun sa file |
| Écriture | soumise à l'ACL de l'axe (D18) — **une application connectée peut en poser** | l'utilisateur seul |

La dernière ligne suffit à trancher : avec un tag, Dolibarr pourrait vider votre file de
travail. Deux mécaniques, deux tables.

`lu_le` reste à part : c'est un **fait daté** (D41), pas un état. Un message peut être lu
et à faire, non lu et déjà pris en charge par un collègue.

Seul **« traité »** sort de la file — il pose `sorti_le` et déplace donc la partition
(D14/D30). Les autres états sont des positions *dans* la file. Revenir en arrière est
possible, et rouvre Q09 : la trace le signale à chaque fois.

## La suite collaborative — et son calendrier

AtomBox se propose aussi comme une **suite collaborative centrée sur la messagerie** :
contacts, tâches, cloud et CRM naissent d'un email. Là où Nextcloud part du fichier et un
ERP du client, AtomBox part de l'échange.

**Mais pas tout de suite.** Le phasage est explicite :

| Jalon | Ce qui arrive |
|---|---|
| **V1** | le moteur, l'API, le webmail — et les capacités **par connecteur**, ou absentes |
| **V2** | livraison LMTP, module Dovecot, messagerie interne hors SMTP |
| **V3** | les **composants internes** : contacts, tâches, cloud, CRM |
| **V4** | les **canaux non-mail** : SMS, WhatsApp, téléphonie |

Écrire un CRM interne pendant qu'on écrit un moteur de stockage, c'est rater les deux — et
un connecteur Dolibarr rend le service dès la V1. Ce que le contrat garantit, c'est que la
V3 **ne demandera aucune réécriture d'interface**.

### Les capacités sont des contrats

| Capacité | Fournisseurs |
|---|---|
| **Tâches** | aucun · Dolibarr · Redmine · Nextcloud Deck · *AtomBox (V3)* |
| **Contacts** | aucun · AtomBox (lecture V1, carnet V3) · CardDAV · Dolibarr · LDAP |
| **Cloud** | aucun · Nextcloud WebDAV · *AtomBox (V3)* |
| **Calendrier** | aucun · CalDAV · *AtomBox (V3)* |
| **CRM** | aucun · Dolibarr · *AtomBox (V3)* |

**« Aucun » est un état normal, pas une panne** : l'entrée de menu disparaît, et c'est tout.
Mieux vaut pas de gestionnaire de tâches qu'un gestionnaire de tâches à moitié fait. Les
contacts font exception — leur lecture est **gratuite** dès la V1, puisque la table
`correspondant` existe déjà pour le rattachement (D35).

**L'écran ne sait pas lequel est branché** — seule la cascade change, et le POC affiche les
deux (basculer sur un fournisseur V3 donne un **aperçu**, précisément pour permettre la
comparaison) :

- **tâche Dolibarr** : un `POST`, une référence externe, un lien qui **peut mourir**, et une
  file de travail qui demande un appel de plus à chaque affichage ;
- **tâche native** : un `INSERT`, une clé étrangère vers le message, et « mes emails à
  traiter » + « mes tâches » se lisent dans **une seule requête** ;
- **cloud Nextcloud** : l'octet existe **deux fois**, la déduplication ne protège plus le
  second exemplaire ;
- **cloud natif** : « enregistrer » ne copie **rien** — l'octet est déjà stocké et
  dédupliqué (D24).

C'est ce contraste qui doit décider du jalon V3, pas une préférence de principe.

### Les canaux — ce qu'il ne faut pas s'interdire

La V4 ouvre AtomBox au non-mail. Ce n'est **pas** une capacité enfichable : un canal *entre*
dans le moteur. Trois précautions gratuites aujourd'hui, très coûteuses ensuite — même
raisonnement que D62 pour le multi-organisation :

| Précaution | Sans elle, en V4 |
|---|---|
| L'identifiant d'un correspondant a un **type** | un numéro de téléphone ne peut pas rejoindre l'identité qui porte déjà l'email — l'intérêt même de D35 |
| Le message porte son **canal** | toutes les vues supposent l'email, et il faut réécrire les requêtes une par une |
| Ce qui est **propre à l'email** est isolé | un SMS se retrouve avec douze colonnes nulles, et `message` devient une table à trous |

La troisième est la seule qui demande un arbitrage : elle coûte une jointure sur le chemin
le plus chaud du produit.

## Administration

Un onglet, quatre volets : **domaines et boîtes** (les alias sont de vraies boîtes, D39),
**applications et jetons** (empreinte stockée, jamais le secret ; révoquer ne réécrit pas
les tags déjà posés), **axes et tags** (le mécanisme d'ACL existe, la politique de Q05 non),
**suite collaborative** (le choix des fournisseurs, quatre lignes de configuration).

## Pièces jointes — chercher, renommer, taguer, enregistrer

Un écran à part, qui rend visible ce que rien d'autre ne montre : **le nom appartient à la
liaison, les octets au blob**. Renommer une pièce jointe renomme *sa liaison* — les autres
messages qui portent le même octet gardent leur nom, et le message d'origine reste
reconstructible à l'identique (D25/D32).

C'est aussi le seul écran qui cherche du **texte hors du corps**, et il le paie : un
`ILIKE '%…%'` sur `nom_fichier` ne s'indexe pas sans trigramme. À quatre millions de
liaisons, ce n'est plus un détail.

L'en-tête affiche le total « nommé » face au total « réellement stocké » : c'est la mesure
directe du gain de déduplication, sur le corpus affiché.

## Sens, tags, quarantaine

**Reçus / envoyés** est un axe de filtre **à part**, croisé avec le reste : on veut « non
lus ET reçus », pas l'un ou l'autre. Un dossier virtuel porte toute la correspondance d'un
tiers, entrante et sortante — sans les envois, un dossier client raconte la moitié de
l'histoire et le fil est amputé. L'affichage suit : un message **sortant** montre son
destinataire, quel que soit son dossier, en réutilisant la variante `sent` du registre.

Le journal en tire une contrainte : **le sens doit être une colonne du rattachement**, posée
à l'ingestion et à l'émission. Le déduire de `from_adresse IN (mes adresses)` est faux — une
boîte commune reçoit ses propres envois — et ne s'indexe pas.

**Les tags** s'ajoutent et se retirent réellement, avec le nom des valeurs existantes de
l'axe proposé en autocomplétion : sans cela, chacun écrit « Belair SAS », « belair » et
« Belair sas », et l'axe ne regroupe plus rien — c'est Q05 vue depuis l'écran. Retirer un
tag posé par un **connecteur** lève un avertissement : il sera reposé au passage suivant, un
retrait durable suppose autre chose (D19/D21).

**La quarantaine** a son geste symétrique. « Ce n'est pas un indésirable » remet le message
à sa place *et* fait désapprendre le filtre : un filtre qui n'apprend que dans un sens
dérive, et c'est la seule trace qui permettra de mesurer son taux de faux positifs.

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
| Filtres (en file / non lus / récents / PJ / lourds / sortis) **×** sens (reçus / envoyés) **×** tris | D16 |
| Tags posés et retirés à la main, à côté de ceux des connecteurs | D17, D18, D20, Q05 |
| Quarantaine symétrique : marquer indésirable **et** désapprendre | D71 |
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
