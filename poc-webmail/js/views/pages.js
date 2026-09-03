/* LES PAGES D'ACCOMPAGNEMENT — ce qu'un collaborateur doit lire avant de cliquer.
   Aide, fonctionnalités, CDC, feuille de route. La page CDC lit `ABX.CDC`, qui est
   GÉNÉRÉ depuis le registre réel (outils/gen-cdc-index.py) : elle ne peut donc pas
   raconter autre chose que ce que dit le CDC. */
(function (ABX) {
  "use strict";
  const F = ABX.Fmt, P = ABX.Providers;

  const PAGES = [["aide","Aide"], ["features","Fonctionnalités"],
                 ["cdc","CDC"], ["dict","Dictionnaire"], ["roadmap","Feuille de route"]];

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

    <div class="box"><h4>Tout le CDC est dans la maquette</h4>
      <p>La page <b>CDC</b> contient le texte intégral : chaque chapitre, chaque décision,
        chaque question, chaque conseil. Cliquez un chapitre ou un identifiant (D138, Q54,
        C09) où qu'il apparaisse — y compris dans une autre page — et sa section s'ouvre.</p>
      <p>La page <b>Dictionnaire</b> montre les treize tables du chapitre 16 en entier :
        entités avec leurs champs, relations, énumérations, workflows, actions, templates,
        composants, protocoles, normes, routes, fonctionnalités, jalons. C'est la même source
        que le CDC et que ce POC — les pages <b>Fonctionnalités</b> et <b>Roadmap</b> la lisent
        au lieu d'être saisies — et le harnais de tests vérifie que chaque décision citée
        existe au registre.</p></div>

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
  /* ---- CDC : tout le texte, pas seulement les tableaux ------------------
     Les chapitres, chaque décision, chaque question et chaque conseil sont
     dans l'index (ABX.CDC.textes / sections), rendus en markdown minimal.
     Ce que l'on lit ici EST le CDC — la maquette n'en résume plus rien. */
  function cdc() {
    const C = ABX.CDC, M = ABX.Markdown, ui = ABX.Store.ui.cdc || {};
    const lien = id => `<a href="#" class="cdc-lien" data-sec="${F.esc(id)}"><b>${F.esc(id)}</b></a>`;
    const parUrg = u => C.questions.filter(q => q.urgence === u);
    let lecture = "";
    if (ui.sec && C.sections[ui.sec])
      lecture = `<div class="box lecture"><div class="hint"><a href="#" class="cdc-lien" data-sec="">‹ fermer</a>
        · section <b>${F.esc(ui.sec)}</b> du registre</div>${M.rendre(C.sections[ui.sec])}</div>`;
    else if (ui.chap && C.textes[ui.chap])
      lecture = `<div class="box lecture"><div class="hint"><a href="#" class="cdc-lien" data-chap="">‹ fermer</a>
        · chapitre <b>${F.esc(ui.chap)}</b></div>${M.rendre(C.textes[ui.chap])}</div>`;
    return `
    <div class="box"><h4>Le cahier des charges — ${C.chapitres.length} chapitres, ${C.decisions.length} décisions,
        ${C.questions.length} questions, ${(C.conseils || []).length} conseils</h4>
      <div class="hint">Généré le ${F.esc(C.genere)} depuis <span class="hash">${F.esc(C.depot)}</span> — ticket
        ${F.esc(C.ticket)}. Tout le texte est ici : cliquez un chapitre, une décision, une question.</div>
      <div class="chips" style="margin-top:8px">${C.chapitres.map(c =>
        `<span class="chip cdc-lien${ui.chap === c.n && !ui.sec ? " on" : ""}" data-chap="${F.esc(c.n)}">${F.esc(c.n)} · ${F.esc(c.titre)}</span>`).join("")}</div></div>
    ${lecture}
    <div class="box"><h4>Questions ouvertes — ce qui reste à trancher</h4>
      <table class="erpl"><tr><th>#</th><th>Question</th><th>Bloque</th><th>Urgence</th></tr>
      ${["haute","moyenne","basse"].map(u => parUrg(u).map(q => `<tr>
        <td>${lien(q.id)}</td><td>${F.esc(q.objet)}</td>
        <td><span class="hash">${F.esc(q.bloque)}</span></td>
        <td><span class="st ${u === "haute" ? "due" : u === "moyenne" ? "wait" : ""}">${u}</span></td>
        </tr>`).join("")).join("")}</table>
      <div class="hint">${parUrg("tranchee").length} autres questions ont été tranchées — elles restent lisibles
        depuis le registre, et depuis leur identifiant partout où il apparaît.</div></div>
    <div class="box"><h4>Registre des décisions</h4>
      <table class="erpl"><tr><th>#</th><th>Objet</th><th>État</th></tr>
      ${C.decisions.map(d => `<tr><td>${lien(d.id)}</td><td>${F.esc(d.objet)}</td>
        <td><span class="st ${d.etat === "valide" ? "ok" : d.etat === "propose" ? "wait" : d.etat === "amendee" ? "due" : ""}">${
          { valide:"✅ validé", propose:"🟡 proposé", amendee:"❌ amendée" }[d.etat] || d.etat}</span></td></tr>`).join("")}</table></div>
    <div class="box"><h4>Conseils rendus</h4>
      <table class="erpl"><tr><th>#</th><th>Conseil</th><th>État</th></tr>
      ${(C.conseils || []).map(c => `<tr><td>${lien(c.id)}</td><td>${F.esc(c.objet)}</td><td>${F.esc(c.etat)}</td></tr>`).join("")}</table></div>`;
  }

  /* ---- DICTIONNAIRE DES DONNÉES : les treize tables, en entier ----------
     Rendu GÉNÉRIQUE : les colonnes sont déduites des clés présentes, les
     listes jointes, les identifiants D/Q/C cliquables. Ajouter une table au
     dictionnaire n'oblige à rien ici. */
  const DICT_TABLES = [["entites","Entités"], ["champs","Champs"], ["relations","Relations"],
    ["enumerations","Énumérations"], ["workflows","Workflows"], ["actions","Actions"],
    ["templates","Templates"], ["composants","Composants"], ["protocoles","Protocoles"],
    ["normes","Normes"], ["routes","Routes"], ["fonctionnalites","Fonctionnalités"], ["jalons","Jalons"]];
  const CACHE_COLS = { role:1, effet:1, engage:1, note:1, notes:1, contenu:1 };
  function val(v) {
    if (v === null || v === undefined || v === "") return "—";
    if (v === true) return "oui"; if (v === false) return "non";
    if (Array.isArray(v)) return v.map(x => typeof x === "object" ? val(x) : ABX.Markdown.inline(String(x))).join(", ");
    if (typeof v === "object") return Object.entries(v).map(([k, x]) => `<b>${F.esc(k)}</b> ${val(x)}`).join(" · ");
    return ABX.Markdown.inline(String(v));
  }
  function tableau(objs, ordre) {
    if (!objs || !objs.length) return "<div class='hint'>—</div>";
    const cols = ordre || Object.keys(objs.reduce((a, o) => { Object.keys(o).forEach(k => a[k] = 1); return a; }, {}));
    return `<div class="tw"><table class="erpl"><tr>${cols.map(c => "<th>" + F.esc(c) + "</th>").join("")}</tr>${
      objs.map(o => "<tr>" + cols.map(c => `<td${CACHE_COLS[c] ? ' class="long"' : ""}>${val(o[c])}</td>`).join("") + "</tr>").join("")}</table></div>`;
  }
  function dict() {
    const D = ABX.CDC.dict, t = ABX.Store.ui.dictTable || "entites";
    let corps = "";
    if (t === "entites")
      corps = D.entites.map(e => `<div class="box"><h4><code>${F.esc(e.nom)}</code> ${e.etat || ""} <span class="hint">· ${F.esc(e.domaine)}${e.jalon ? " · V" + e.jalon : ""}</span></h4>
        <p>${val((e.role || "").trim())}</p>${e.partition ? `<div class="hint">Partition : ${val(e.partition)}</div>` : ""}
        ${e.notes ? `<div class="hint"><i>${val(e.notes)}</i></div>` : ""}
        <div class="hint">Décisions : ${val(e.decisions)}${e.conseils ? " · conseils : " + val(e.conseils) : ""}</div>
        ${D.champs[e.id] ? tableau(D.champs[e.id], ["nom","type","obligatoire","nature","enum","role"]) : "<div class='hint'>champs : à détailler</div>"}</div>`).join("");
    else if (t === "champs")
      corps = Object.entries(D.champs).map(([e, l]) => `<div class="box"><h4><code>${F.esc(e)}</code> — ${l.length} champs</h4>${tableau(l, ["nom","type","obligatoire","nature","enum","role"])}</div>`).join("");
    else if (t === "enumerations")
      corps = Object.entries(D.enumerations).map(([n, e]) => `<div class="box"><h4><code>${F.esc(n)}</code></h4><p>${val(e.role)}</p>${tableau(e.valeurs)}${e.questions ? `<div class="hint">Questions : ${val(e.questions)}</div>` : ""}</div>`).join("");
    else if (t === "workflows")
      corps = D.workflows.map(w => `<div class="box"><h4>${F.esc(w.nom)} <span class="hint">· ${F.esc(w.entite)}${w.champ ? "." + F.esc(w.champ) : ""}</span></h4>
        ${w.etats ? `<p>États : ${w.etats.map(s => "<code>" + F.esc(s) + "</code>").join(" → ")}</p>` : ""}
        ${w.regles ? "<ul>" + w.regles.map(r => "<li>" + val(r) + "</li>").join("") + "</ul>" : ""}
        ${w.transitions ? tableau(w.transitions, ["de","vers","geste","qui","effet"]) : ""}
        ${w.garde_fous ? "<div class='hint'><b>Garde-fous</b></div><ul>" + w.garde_fous.map(r => "<li>" + val(r) + "</li>").join("") + "</ul>" : ""}
        <div class="hint">Décisions : ${val(w.decisions)}${w.questions ? " · questions : " + val(w.questions) : ""}</div></div>`).join("");
    else if (t === "composants")
      corps = Object.entries(D.composants).map(([fam, l]) => `<div class="box"><h4>${F.esc(fam)}</h4>${tableau(l)}</div>`).join("");
    else if (t === "jalons")
      corps = D.jalons.map(j => `<div class="box"><h4>${F.esc(j.id)} — ${F.esc(j.titre)} <span class="st wait">${F.esc(j.etat)}</span></h4>
        ${j.note ? `<blockquote>${val(j.note)}</blockquote>` : ""}<ul>${(j.contenu || []).map(c => "<li>" + val(c) + "</li>").join("")}</ul></div>`).join("");
    else corps = `<div class="box">${tableau(D[t])}</div>`;
    const n = Array.isArray(D[t]) ? D[t].length : Object.keys(D[t]).length;
    return `<div class="box"><h4>Dictionnaire des données — la source du chapitre 16 et de ce POC</h4>
      <div class="hint">Types logiques, jamais SQL : le SGBD n'est pas définitivement statué. Chaque identifiant
        D/Q/C est cliquable et ouvre sa section dans la page CDC.</div>
      <div class="chips" style="margin-top:8px">${DICT_TABLES.map(([k, l]) =>
        `<span class="chip${k === t ? " on" : ""}" data-dict="${k}">${l}</span>`).join("")}</div>
      <div class="hint" style="margin-top:6px"><b>${n}</b> ${t === "champs" ? "entités détaillées" : "entrées"}</div></div>${corps}`;
  }

  /* ROADMAP — LUE dans l'index du CDC (docs/dict/jalons.yml), plus jamais
     saisie ici : le POC et le chapitre 16 lisent le même fichier. */
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

  const RENDU = { aide, features, cdc, dict, roadmap };

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
