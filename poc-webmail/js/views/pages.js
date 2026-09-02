/* LES PAGES D'ACCOMPAGNEMENT — ce qu'un collaborateur doit lire avant de cliquer.
   Aide, fonctionnalités, CDC, feuille de route. La page CDC lit `ABX.CDC`, qui est
   GÉNÉRÉ depuis le registre réel (outils/gen-cdc-index.py) : elle ne peut donc pas
   raconter autre chose que ce que dit le CDC. */
(function (ABX) {
  "use strict";
  const F = ABX.Fmt, P = ABX.Providers;

  const PAGES = [["aide","Aide"], ["features","Fonctionnalités"],
                 ["cdc","CDC"], ["roadmap","Feuille de route"]];

  /* ---- aide ------------------------------------------------------------ */
  function aide() {
    return `<div class="box"><h4>Ce que cette maquette est</h4>
      <p>Une <b>maquette d'interface</b> sur données inventées. Aucun serveur, aucune base,
        aucun message réel : tout est engendré dans le navigateur au chargement. Rien de ce
        que vous ferez ici n'a d'effet ailleurs, et le bouton <b>⟲</b> remet tout à zéro.</p>
      <p>Elle sert à décider du <b>schéma de base de données</b> et de la <b>surface d'API</b>
        d'AtomBox : les écrans sont un moyen, pas le but.</p></div>

    <div class="box"><h4>Le panneau de droite est le livrable</h4>
      <p>Chaque clic y déroule la <b>cascade complète</b> de ce qui se passerait : l'appel
        d'API, la route, le contrôleur, les requêtes SQL, la lecture du stockage, le JSON
        renvoyé, le rendu. Une barre marque le passage du réseau — à gauche le navigateur,
        à droite le serveur <b>qui reste à écrire</b>.</p>
      <p>Le ⚠ orange signale ce qui coûte cher, ce qui n'est pas indexé, ou ce qui n'est pas
        tranché. <b>C'est là qu'il faut regarder</b> : si une requête manque, ou si l'une
        d'elles vous paraît inacceptable, c'est exactement ce que ce POC doit produire.</p>
      <p>Le bouton <code>⟨/⟩ requêtes</code> le masque, <kbd>Échap</kbd> aussi.</p></div>

    <div class="box"><h4>Se déplacer</h4>
      <table class="erpl">
        <tr><th>Geste</th><th>Effet</th></tr>
        <tr><td><b>Clic</b> sur un message</td><td>l'ouvre dans un onglet <i>provisoire</i>
          (en italique), remplacé au clic suivant</td></tr>
        <tr><td><b>Double-clic</b></td><td>épingle l'onglet — il reste ouvert</td></tr>
        <tr><td>Clic du <b>milieu</b>, ou la croix</td><td>ferme l'onglet</td></tr>
        <tr><td>Champ <b>Filtrer les dossiers</b></td><td>cherche dans les 370 dossiers ;
          la croix ou <kbd>Échap</kbd> l'efface</td></tr>
        <tr><td>Survol d'un message</td><td>fait apparaître ses actions rapides</td></tr>
      </table></div>

    <div class="box"><h4>Ce qui vaut le détour</h4>
      <ul>
        <li><b>L'arborescence</b> : 200 fournisseurs, 52 clients — la taille est réaliste,
          car c'est elle qui décide de la conception de l'écran.</li>
        <li><b>Une pièce jointe</b> : cliquez-la dans un message. La trace montre qui d'autre
          porte les mêmes octets, et ce que la déduplication économise vraiment.</li>
        <li><b>Le cadre métier</b> d'un message client : il n'est pas stocké, il est demandé
          à l'application connectée — et cela coûte un second aller-retour.</li>
        <li><b>⚙ Administration → Suite collaborative</b> : changez de fournisseur et refaites
          le même geste. L'écran ne bouge pas, la cascade change entièrement.</li>
        <li><b>📎 Pièces jointes</b> : renommez-en une. Le fichier n'est pas touché — seul son
          nom dans <i>ce</i> message change.</li>
      </ul></div>

    <div class="box"><h4>Les expéditeurs, et le nom qu'ils déclarent</h4>
      <p>Un correspondant <b>enregistré</b> s'affiche par le nom de votre carnet. Un
        <b>inconnu</b> s'affiche par son <b>adresse</b>, mise en avant, son nom déclaré
        relégué entre guillemets : le nom d'un email est choisi par l'émetteur, et rien
        ne l'authentifie (D126).</p>
      <p>Quelques messages portent une <b>usurpation par nom</b> — celui d'un contact que
        vous connaissez, posé sur une adresse qui n'est pas la sienne. Ils sont signalés
        dans la liste, et le message ouvert nomme la règle déclenchée (D128, B1). Cette
        fréquence est <b>volontairement gonflée</b> pour qu'on en croise sans chercher :
        dans la réalité c'est rare, et c'est justement ce qui rend l'alerte crédible.</p></div>

    <div class="box"><h4>Les machines, et ce qu'elles attendent de vous</h4>
      <p>Une PME reçoit plus de messages de machines que de personnes. Chaque message porte
        donc une <b>nature</b> (D130) : <i>diffusion</i> pour une newsletter,
        <i>notification</i> pour une facture ou une alerte, <i>service</i> pour un avis de
        non-remise. La ligne de partage n'est pas humain/machine — c'est
        « <b>quelqu'un attend-il quelque chose de moi ?</b> ». Une diffusion ne remplit pas
        la file des non traités ; une notification y entre, parce qu'une facture est une
        machine qui attend un paiement.</p>
      <p>Les diffusions se rangent d'elles-mêmes sous <b>Abonnements</b> : un dossier par
        liste, <b>déduit du corpus</b> et non saisi (D133). Le message n'a pas bougé pour
        autant — il est toujours chez son correspondant, et il apparaît ici <i>en plus</i>.
        C'est l'arborescence engendrée de D77 prise au mot : ouvrez « Fournisseurs › une
        société » puis « Abonnements › la même société », vous verrez les mêmes messages
        d'un côté parmi les factures, de l'autre seuls.</p>
      <p>À l'ouverture d'un tel message, le bouton <b>Répondre</b> cesse d'être l'action
        principale, et une ligne dit pourquoi. Sur quelques messages, il est carrément
        <b>refusé</b> — et là, l'écran ne devine pas : il vous montre le rejet
        <code>550</code> reçu la dernière fois qu'on a écrit à cette adresse (D131). C'est
        ce que le cycle de vie de l'émission permet, et qu'un filtre sur le mot
        « noreply » ne saura jamais faire.</p></div>

    <div class="box"><h4>Ce que la maquette ne prouve pas</h4>
      <p>Rien sur la <b>performance</b> : tout est instantané sur des données inventées, et
        les requêtes affichées ne sont jamais exécutées. Une interface validée ici peut
        s'effondrer à cinq millions de messages — cela se vérifiera au POC suivant, sur
        corpus réel.</p></div>`;
  }

  /* ---- fonctionnalités -------------------------------------------------- */
  const FEATURES = [
    ["Réception et stockage", [
      ["Ingestion IMAP des boîtes administrées", 1, "maquetté", "D46, D49"],
      ["Stockage compressé zstd, hors base", 1, "décidé", "D05, D07"],
      ["Déduplication des messages identiques", 1, "décidé", "D10, D64"],
      ["Détachement et déduplication des pièces jointes", 1, "maquetté", "D11, D24"],
      ["Verdicts DKIM / SPF figés à l'ingestion", 1, "décidé", "D26, D27"],
      ["Quarantaine et apprentissage anti-spam", 1, "maquetté", "D71, D91"],
      ["Livraison LMTP (sans Dovecot)", 2, "décidé", "D42, D45"],
      ["Module de stockage Dovecot", 2, "à trancher", "Q24"],
      ["Import d'historique (IMAP, mbox, PST)", 1, "décidé", "D107"],
    ]],
    ["Classement et recherche", [
      ["Tags par axes, paramétrables, avec ACL", 1, "maquetté", "D02, D16, D18"],
      ["Dossiers virtuels = filtres enregistrés", 1, "maquetté", "D75, D77"],
      ["Dossiers utilisateur classiques", 1, "maquetté", "D51"],
      ["Recherche plein texte sur la zone active", 1, "décidé", "D34"],
      ["Recherche dans les pièces jointes (nom)", 1, "maquetté", "D96"],
      ["Moteur de filtres (remplace Sieve)", 1, "décidé", "D74"],
      ["Nature du message : diffusion, notification, service", 1, "maquetté", "D130"],
      ["Newsletters hors de la file, factures dedans", 1, "maquetté", "D130, D13"],
      ["Un dossier par liste, déduit du corpus", 1, "maquetté", "D133, D77"],
      ["Archivage par sortie de file", 1, "maquetté", "D14, D30"],
    ]],
    ["Travail au quotidien", [
      ["Statut de traitement (workflow)", 1, "maquetté", "D93"],
      ["Onglets multiples, restaurés", 1, "maquetté", "—"],
      ["Composition : nouveau, réponse, transfert", 1, "maquetté", "Q26, D58"],
      ["Transfert par référence, sans copie", 1, "maquetté", "D58, D67"],
      ["Envoi interne hors SMTP", 2, "décidé", "D12"],
      ["Groupes de discussion par service", 2, "décidé", "D122, Q46"],
      ["Messages de groupe stockés en base, pas en fichiers", 2, "décidé", "D123"],
      ["Position de lecture par membre", 2, "décidé", "D124"],
      ["Temps réel (arrivée, prise en charge)", 2, "décidé", "D125"],
      ["File de travail partagée sur boîte commune", 1, "à trancher", "Q35"],
      ["Note interne d'équipe, jamais transmise", 1, "décidé", "D101"],
      ["Identités d'expédition et signatures", 1, "décidé", "D102"],
      ["Boîte partagée : « au nom de » optionnel", 1, "décidé", "D116"],
      ["Réponses types partagées", 1, "décidé", "D102"],
      ["Réveil et échéance sur un message", 1, "décidé", "D103"],
      ["Complétion des destinataires", 1, "décidé", "D109"],
      ["Impression et export PDF", 1, "décidé", "D110"],
    ]],
    ["Collaboration et accès", [
      ["Boîtes communes, alias = vraies boîtes", 1, "maquetté", "D38, D39"],
      ["ACL par email, partage révocable", 1, "décidé", "D57, D60"],
      ["Journal d'activité (qui a lu, traité)", 1, "décidé", "D54, D56"],
      ["Rôles d'administration", 1, "maquetté", "D72"],
      ["Authentification par jeton, SSO possible", 1, "décidé", "D63"],
      ["Paramétrage en cascade, verrouillable", 1, "décidé", "D106"],
      ["Interface responsive (mobile)", 1, "décidé", "D112"],
      ["Accès IMAP en repli assumé", 2, "à trancher", "Q24, D112"],
    ]],
    ["Intégration", [
      ["API REST — hypothèse de travail", 1, "à trancher", "Q07, Q08"],
      ["Contexte métier affiché sans être stocké", 1, "maquetté", "D19, D21"],
      ["Applications connectées, jetons, portée", 1, "maquetté", "D20, D37"],
      ["Événements sortants (webhooks) rejouables", 1, "maquetté", "D86"],
      ["Mise en cache du contexte métier", 1, "à trancher", "Q31"],
      ["SDK par langage (PHP, puis JS)", 1, "décidé", "D108"],
      ["Composants d'interface embarquables", 1, "décidé", "D108"],
    ]],
    ["Émission et délivrabilité", [
      ["Cycle de vie de l'envoi, par destinataire", 1, "décidé", "D99"],
      ["Envoi programmé, annulable avant l'heure", 1, "décidé", "D99"],
      ["Retours de non-remise corrélés (DSN)", 1, "décidé", "D99, D66"],
      ["Rapports DMARC agrégés, délivrabilité", 1, "décidé", "D100"],
      ["Absence et réponse auto, renvoi sur collègue", 1, "décidé", "D113, D74"],
      ["Pièce jointe par lien de téléchargement", 1, "décidé", "D111"],
      ["Émission via le relais du client", 1, "décidé", "D114"],
      ["Retour d'enveloppe unique (VERP)", 1, "décidé", "D119"],
      ["Réécriture d'enveloppe (SRS) sur les renvois", 1, "décidé", "D120"],
      ["Journal du MTA : sort connu en secondes", 1, "décidé", "D119"],
      ["Boîte de collecte DMARC + dépouillement", 1, "décidé", "D115"],
      ["Adresse non répondable apprise d'un DSN 5xx", 2, "maquetté", "D131, D119"],
      ["Désabonnement en un clic (List-Unsubscribe)", 2, "décidé", "D132, Q51"],
    ]],
    ["Sécurité et conformité", [
      ["HTML assaini à l'affichage, pas à l'ingestion", 1, "décidé", "D105, D25"],
      ["Images externes bloquées, proxy serveur", 1, "décidé", "D105"],
      ["Bannière « expéditeur externe »", 1, "décidé", "D105"],
      ["Avertir avant de répondre à un « noreply@ »", 1, "maquetté", "D131"],
      ["Réorienter vers un contact connu du domaine", 1, "décidé", "D131"],
      ["Aucun accusé de lecture émis ni demandé", 1, "décidé", "D105"],
      ["Rétention par type de contenu et par boîte", 1, "décidé", "D104"],
      ["Gel sur litige — prime sur toute purge", 1, "décidé", "D104"],
      ["Suppression = détachement, déchetterie", 1, "décidé", "D118"],
      ["Déchetterie : métadonnées, restauration à l'origine", 1, "décidé", "D121"],
      ["Verrouillage : jamais le poste de travail", 1, "décidé", "D117"],
      ["Expéditeur normalisé sur le carnet", 1, "maquetté", "D126"],
      ["Signal d'usurpation par nom (règle B1)", 1, "maquetté", "D128"],
      ["Catalogue de règles anti-usurpation", 1, "décidé", "D127, D128"],
      ["Cohérence IBAN / tiers de l'ERP", 1, "décidé", "D129"],
      ["Alerter, mettre en quarantaine, ou refuser ?", 1, "à trancher", "Q49"],
      ["Analyse des traceurs d'images (option)", 5, "à venir", "D105"],
    ]],
    ["Suite collaborative", [
      ["Contacts — lecture du correspondant", 1, "maquetté", "D35, D95b"],
      ["Tâches, contacts, cloud, CRM par connecteur", 1, "maquetté", "D94"],
      ["Contacts — carnet d'adresses", 3, "à venir", "D95b"],
      ["Tâches internes", 3, "à venir", "D95b"],
      ["Cloud interne", 3, "à venir", "D95b"],
      ["CRM interne", 3, "à venir", "D95b, Q39"],
    ]],
    ["Canaux", [
      ["E-mail", 1, "maquetté", "—"],
      ["Messagerie interne", 2, "décidé", "D12"],
      ["SMS", 4, "à venir", "D97"],
      ["WhatsApp", 4, "à venir", "D97"],
      ["Téléphonie", 4, "à venir", "D97"],
    ]],
  ];

  const ETATS = { "maquetté":"ok", "décidé":"wait", "à trancher":"due", "à venir":"" };

  function features() {
    const n = FEATURES.reduce((s, [, l]) => s + l.length, 0);
    return `<div class="box"><h4>${n} fonctionnalités, par domaine</h4>
      <div class="hint"><span class="st ok">maquetté</span> visible dans ce POC ·
        <span class="st wait">décidé</span> tranché au CDC, pas encore maquetté ·
        <span class="st due">à trancher</span> question ouverte ·
        <span class="st">à venir</span> jalon ultérieur</div></div>
    ${FEATURES.map(([dom, liste]) => `<div class="box"><h4>${F.esc(dom)}</h4>
      <table class="erpl"><tr><th>Fonctionnalité</th><th>Jalon</th><th>État</th><th>Réf.</th></tr>
      ${liste.map(([lib, v, etat, ref]) => `<tr>
        <td>${F.esc(lib)}</td>
        <td><span class="jalon${v > 1 ? " v" + v : ""}">V${v}</span></td>
        <td><span class="st ${ETATS[etat]}">${etat}</span></td>
        <td><span class="hash">${F.esc(ref)}</span></td></tr>`).join("")}
      </table></div>`).join("")}`;
  }

  /* ---- CDC (index généré) ----------------------------------------------- */
  function cdc() {
    const C = ABX.CDC;
    if (!C) return `<div class="empty">Index du CDC absent — lancer
      <code>python3 outils/gen-cdc-index.py</code>.</div>`;
    const parEtat = e => C.decisions.filter(d => d.etat === e);
    const parUrg  = u => C.questions.filter(q => q.urgence === u);
    const LIB = { valide:["validée","ok"], propose:["proposée","wait"], amendee:["amendée","due"],
                  autre:["—",""] };
    return `<div class="box"><h4>Cahier des charges — ${C.ticket}</h4>
      <div class="hint">Index <b>généré</b> depuis le registre réel le ${F.esc(C.genere)} :
        cette page ne peut pas dire autre chose que ce que dit le CDC. Le document complet
        est dans <code>${F.esc(C.depot)}</code>, dossier <code>docs/</code>.</div>
      <div class="chips" style="margin-top:8px">
        <span class="chip on">${C.decisions.length} décisions</span>
        <span class="chip on">${C.questions.length} questions</span>
        <span class="chip on">${C.chapitres.length} chapitres</span>
        <span class="chip">${parEtat("propose").length} en attente d'arbitrage</span>
        <span class="chip">${parUrg("haute").length} questions urgentes</span>
      </div></div>

    <div class="box"><h4>Chapitres</h4>
      <table class="erpl">${C.chapitres.map(c => `<tr><td class="num">${F.esc(c.n)}</td>
        <td><b>${F.esc(c.titre)}</b></td>
        <td><span class="hash">${F.esc(c.fichier)}</span></td></tr>`).join("")}</table></div>

    <div class="box"><h4>Questions ouvertes — ce qui reste à trancher</h4>
      <table class="erpl"><tr><th>#</th><th>Question</th><th>Bloque</th><th>Urgence</th></tr>
      ${["haute","moyenne","basse"].map(u => parUrg(u).map(q => `<tr>
        <td><b>${F.esc(q.id)}</b></td><td>${F.esc(q.objet)}</td>
        <td><span class="hash">${F.esc(q.bloque)}</span></td>
        <td><span class="st ${u === "haute" ? "due" : u === "moyenne" ? "wait" : ""}">${u}</span></td>
        </tr>`).join("")).join("")}</table>
      <div class="hint">${parUrg("tranchee").length} autres questions ont été tranchées et
        ont migré vers le registre des décisions.</div></div>

    <div class="box"><h4>Registre des décisions</h4>
      <table class="erpl"><tr><th>#</th><th>Objet</th><th>État</th></tr>
      ${C.decisions.map(d => `<tr><td><b>${F.esc(d.id)}</b></td><td>${F.esc(d.objet)}</td>
        <td><span class="st ${LIB[d.etat][1]}">${LIB[d.etat][0]}</span></td></tr>`).join("")}
      </table></div>`;
  }

  /* ---- feuille de route -------------------------------------------------- */
  const ROADMAP = [
    { v:1, titre:"Le moteur, l'API, le webmail", etat:"en conception",
      contenu:["Ingestion IMAP en lecture seule sur le domaine pilote",
        "Stockage zstd hors base, index PostgreSQL",
        "Déduplication des messages et des pièces jointes",
        "Tags par axes, dossiers virtuels, archivage",
        "Webmail : lecture, composition, statut de traitement",
        "API et applications connectées (Dolibarr, Redmine, Nextcloud)",
        "Suite collaborative : par connecteur, ou absente",
        "Émission suivie : état par destinataire, envoi programmé, DSN corrélés",
        "Délivrabilité : rapports DMARC agrégés",
        "Affichage sûr, rétention et gel, paramétrage en cascade",
        "Import d'historique, SDK et composants embarquables"],
      note:"Le produit est utilisable seul : une messagerie qui classe et qui se branche." },
    { v:2, titre:"La livraison", etat:"cadré",
      contenu:["Livraison LMTP sans passer par Dovecot",
        "Messagerie interne hors SMTP",
        "Module de stockage Dovecot (à trancher — Q24)"],
      note:"AtomBox cesse de lire les boîtes des autres pour recevoir directement." },
    { v:3, titre:"Les composants internes", etat:"cible",
      contenu:["Carnet de contacts", "Tâches", "Cloud (fichiers)", "CRM"],
      note:"AtomBox devient la suite collaborative. Le CRM est le morceau le plus ambitieux : " +
           "à chiffrer comme un produit à part entière." },
    { v:4, titre:"Les canaux", etat:"horizon",
      contenu:["SMS", "WhatsApp Business", "Téléphonie (CTI, journal d'appels)"],
      note:"AtomBox cesse d'être une messagerie pour devenir un hub de communication. " +
           "Le pivot reste le correspondant — c'est lui qui unifie un mail, un SMS et un appel." },
    { v:5, titre:"L'horizon — et il n'est pas un plan", etat:"réserve",
      contenu:["Analyse des images externes : distinguer le contenu du pixel espion (option)"],
      note:"Une seule entrée, et c'est volontaire : ce jalon existe pour empêcher de faire " +
           "l'analyse de traceurs en V1 « puisqu'on y est ». Un jalon qui ne contient qu'une " +
           "ligne est un jalon honnête ; le remplir d'idées serait l'erreur que le phasage " +
           "sert justement à éviter." },
  ];

  function roadmap() {
    return `<div class="box"><h4>Feuille de route</h4>
      <div class="hint">Les jalons ne sont pas des dates : ce sont des <b>ordres de
        priorité</b>. Ce qui compte ici est ce qu'on s'interdit de faire trop tôt — écrire un
        CRM interne pendant qu'on écrit un moteur de stockage, c'est rater les deux.</div></div>
    ${ROADMAP.map(r => `<div class="box"><h4>
      <span class="jalon${r.v > 1 ? " v" + r.v : ""}">V${r.v}</span>
      ${F.esc(r.titre)} — <span class="st ${r.v === 1 ? "wait" : ""}">${r.etat}</span></h4>
      <ul>${r.contenu.map(c => `<li>${F.esc(c)}</li>`).join("")}</ul>
      <div class="hint">${F.esc(r.note)}</div></div>`).join("")}

    <div class="box"><h4>Ce qui prépare la suite dès maintenant</h4>
      <div class="hint">Trois précautions gratuites aujourd'hui, très coûteuses plus tard —
        elles sont dans le CDC (D98) et visibles dans <b>⚙ Administration → Canaux</b>.</div>
      <ul>
        <li>L'identifiant d'un correspondant porte un <b>type</b> — sinon un numéro de
          téléphone ne pourra jamais rejoindre l'identité qui porte déjà l'email.</li>
        <li>Le message porte son <b>canal</b>, valant « email » dès la première ligne.</li>
        <li>Ce qui est propre à l'email est <b>isolé</b> — sinon un SMS arrivera avec douze
          colonnes vides.</li>
      </ul></div>`;
  }

  const RENDU = { aide, features, cdc, roadmap };

  ABX.Views = ABX.Views || {};
  ABX.Views.Pages = {
    PAGES, FEATURES, ROADMAP,
    titre: p => (PAGES.find(x => x[0] === p) || ["", "Page"])[1],
    render(page) {
      const p = RENDU[page] ? page : "aide";
      return `<div class="backbar"><button data-vue="liste">‹ Retour</button></div>
        <div class="dhead"><div class="dsubj">${F.esc(ABX.Views.Pages.titre(p))}</div>
          <div class="chips" style="margin-top:9px">${PAGES.map(([k, l]) =>
            `<span class="chip${k === p ? " on" : ""}" data-page="${k}">${l}</span>`).join("")}</div>
        </div>
        <div class="admin doc">${RENDU[p]()}</div>`;
    },
  };
})(window.ABX = window.ABX || {});
