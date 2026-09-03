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
        <tr><td>Champ <b>Filtrer les dossiers</b></td><td>cherche dans les 399 dossiers ;
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
      <p><b>Un mot sur l'indicateur de confiance</b> (✓ vert) : il n'apparaît que si le
        message est <b>authentifié par son domaine</b>. Ouvrez un message d'un correspondant
        que vous connaissez mais dont le domaine n'aligne pas : il n'y a <i>aucun</i>
        indicateur, et le bouton de validation est désactivé. C'est délibéré — marquer
        « fiable » un identifiant qu'on peut usurper reviendrait à désigner à l'attaquant la
        cible exacte (D137).</p>
      <p>À l'ouverture d'un tel message, le bouton <b>Répondre</b> cesse d'être l'action
        principale, et une ligne dit pourquoi. Sur quelques messages, il est carrément
        <b>refusé</b> — et là, l'écran ne devine pas : il vous montre le rejet
        <code>550</code> reçu la dernière fois qu'on a écrit à cette adresse (D131). C'est
        ce que le cycle de vie de l'émission permet, et qu'un filtre sur le mot
        « noreply » ne saura jamais faire.</p></div>

    <div class="box"><h4>L'ordre des dossiers vous appartient</h4>
      <p>Survolez le nom d'un axe dans l'arborescence : des commandes apparaissent pour le
        <b>monter</b>, le <b>descendre</b>, ou trier ses dossiers par <b>activité récente</b> ou
        <b>A→Z</b>. L'ordre est le vôtre, il est retenu d'une session à l'autre (D135). Il n'y a
        pas d'ordre manuel sur les dossiers d'un axe : ranger deux cents fournisseurs à la main
        serait une corvée, et l'ordre serait périmé au premier tiers créé dans l'ERP.</p>
      <p>Le nœud d'un axe porte simplement son nom — plus de « Tous — Fournisseurs » au-dessus
        d'un titre « Fournisseurs ».</p></div>

    <div class="box"><h4>Ce que la page CDC montre de plus</h4>
      <p>Le <b>dictionnaire des données</b> (chapitre 16) y est lu depuis la même source que
        ce POC : entités, champs, relations, énumérations, workflows, actions, templates,
        composants, protocoles, normes, routes. Les pages <b>Fonctionnalités</b> et
        <b>Roadmap</b> ne sont plus saisies ici, elles lisent ce dictionnaire — et le harnais de
        tests vérifie que chaque décision qu'il cite existe au registre.</p></div>

    <div class="box"><h4>Ce que la maquette ne prouve pas</h4>
      <p>Rien sur la <b>performance</b> : tout est instantané sur des données inventées, et
        les requêtes affichées ne sont jamais exécutées. Une interface validée ici peut
        s'effondrer à cinq millions de messages — cela se vérifiera au POC suivant, sur
        corpus réel.</p></div>`;
  }

  /* ---- fonctionnalités -------------------------------------------------- */
  /* FONCTIONNALITÉS — LUES dans l'index du CDC (docs/dict/fonctionnalites.yml).
     La forme [[domaine, [[libellé, jalon, état, réf.]]]] est celle qu'attend le
     rendu ; le regroupement par domaine suit l'ordre d'apparition dans la source. */
  const FEATURES = (() => {
    const doms = [], par = {};
    (ABX.CDC.dict.fonctionnalites || []).forEach(f => {
      if (!par[f.domaine]) { par[f.domaine] = []; doms.push(f.domaine); }
      par[f.domaine].push([f.libelle, f.jalon, f.etat,
        (f.decisions || []).concat(f.questions || []).join(", ") || "—"]);
    });
    return doms.map(d => [d, par[d]]);
  })();

  const ETATS = { "maquetté":"ok", "décidé":"wait", "à trancher":"due", "à venir":"",
                  "en pause":"pause" };

  function features() {
    const n = FEATURES.reduce((s, [, l]) => s + l.length, 0);
    return `<div class="box"><h4>${n} fonctionnalités, par domaine</h4>
      <div class="hint"><span class="st ok">maquetté</span> visible dans ce POC ·
        <span class="st wait">décidé</span> tranché au CDC, pas encore maquetté ·
        <span class="st due">à trancher</span> question ouverte ·
        <span class="st">à venir</span> jalon ultérieur ·
        <span class="st pause">en pause</span> écarté volontairement, à reprendre sur un chiffre</div></div>
    ${FEATURES.map(([dom, liste]) => `<div class="box"><h4>${F.esc(dom)}</h4>
      <table class="erpl"><tr><th>Fonctionnalité</th><th>Jalon</th><th>État</th><th>Réf.</th></tr>
      ${liste.map(([lib, v, etat, ref]) => `<tr>
        <td>${F.esc(lib)}</td>
        <td>${v ? `<span class="jalon${v > 1 ? " v" + v : ""}">V${v}</span>`
               : `<span class="jalon aucun" title="Aucun jalon : écarté volontairement">—</span>`}</td>
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

    <div class="box"><h4>Dictionnaire des données — chapitre 16, lu depuis la même source</h4>
      <div class="hint">${(() => { const D = C.dict; return [
        ["entités", D.entites.length], ["champs", Object.values(D.champs).reduce((n, l) => n + l.length, 0)],
        ["relations", D.relations.length], ["énumérations", Object.keys(D.enumerations).length],
        ["workflows", D.workflows.length], ["actions", D.actions.length], ["templates", D.templates.length],
        ["composants", Object.values(D.composants).reduce((n, l) => n + l.length, 0)],
        ["protocoles", D.protocoles.length], ["normes", D.normes.length], ["routes", D.routes.length]]
        .map(([k, n]) => `<b>${n}</b> ${k}`).join(" · "); })()}
        — types logiques, jamais SQL : le SGBD n'est pas définitivement statué.</div>
      <table class="erpl"><tr><th>Entité</th><th>Domaine</th><th>Rôle</th><th>État</th></tr>
      ${C.dict.entites.map(e => `<tr><td><b>${F.esc(e.nom)}</b></td><td>${F.esc(e.domaine)}</td>
        <td>${F.esc((e.role || "").trim())}</td><td>${e.etat || ""}</td></tr>`).join("")}</table>
      <div class="hint" style="margin-top:8px"><b>Workflows</b> : ${C.dict.workflows.map(w =>
        F.esc(w.nom)).join(" · ")}. <b>Actions</b> tracées au journal : ${
        C.dict.actions.filter(a => a.trace === true || a.trace === "oui").length} sur ${C.dict.actions.length}.</div></div>

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
  /* ROADMAP — LUE dans l'index du CDC (docs/dict/jalons.yml), plus jamais
     saisie ici : le POC et le chapitre 16 disent la même chose parce qu'ils
     lisent le même fichier. */
  const ROADMAP = (ABX.CDC.dict.jalons || []).map(j => ({
    v: parseInt(j.id.replace(/\D/g, ""), 10), titre: j.titre, etat: j.etat,
    note: j.note || "", contenu: j.contenu || [] }));

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
