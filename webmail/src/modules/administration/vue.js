/* ADMINISTRATION — quatre volets, un onglet.
   Ce qu'un exploitant doit pouvoir régler sans ouvrir psql : les domaines et
   boîtes, les applications connectées et leurs jetons, les axes de tags, et le
   choix des fournisseurs de la suite. */
(function (ABX) {
  "use strict";
  const F = ABX.Fmt, R = ABX.Registry, P = ABX.Providers;
  const Fx = () => ABX.Fixtures;      // POC seulement : les volets historiques s'en servent encore

  const VOLETS = [["boites","Domaines & boîtes"], ["apps","Applications & jetons"],
                  ["axes","Axes & tags"], ["etat","État & journal"], ["regles","Règles"],
                  ["suite","Suite collaborative"], ["canaux","Canaux"]];
  /* Le webmail EST l'interface d'administration (D159) : ces deux volets ne sont pas une
     seconde application, ce sont des pages gardées par un rôle — en V0 il n'y en a pas
     encore, tout compte les voit (D072 viendra en V1). */
  const jalon = v => v && v > 1 ? `<span class="jalon v${v}">V${v}</span>` : "";

  function boites() {
    return `<div class="box"><h4>Domaines</h4>
      <table class="erpl"><tr><th>Domaine</th><th>Rôle</th><th>Boîtes</th><th>Alias</th>
        <th>Ingestion</th></tr>
      ${Fx().DOMAINES.map(d => `<tr><td><b>${F.esc(d.nom)}</b></td>
        <td><span class="st ${d.role === "pilote" ? "ok" : "wait"}">${d.role}</span></td>
        <td class="num">${d.boites}</td><td class="num">${d.alias}</td>
        <td>${F.esc(d.ingestion)}</td></tr>`).join("")}</table>
      <div class="hint">Les alias ne sont pas des redirections : chaque alias est une
        <b>boîte propre</b> (D039), sinon deux destinataires distincts se retrouvent dans le
        même fil et personne ne sait à qui le message était adressé.</div></div>

    <div class="box"><h4>Boîtes</h4>
      <table class="erpl"><tr><th>Adresse</th><th>Type</th><th>Accès</th><th>Messages</th><th></th></tr>
      ${Fx().BOITES.map(b => `<tr><td><b>${F.esc(b.adresse)}</b></td>
        <td>${b.type === "alias" ? `alias → ${F.esc(b.cible)}` : F.esc(b.type)}</td>
        <td class="num">${b.acces != null ? b.acces + " compte(s)" : "—"}</td>
        <td class="num">${b.msg != null ? b.msg.toLocaleString("fr-FR") : "—"}</td>
        <td class="num"><button class="hbtn ic" data-adm="boite:${F.esc(b.adresse)}">⋯</button></td>
        </tr>`).join("")}</table>
      <div class="cbar"><button class="hbtn prim" data-adm="boite:new">+ Créer une boîte</button>
        <button class="hbtn" data-adm="alias:new">+ Créer un alias</button></div>
      <div class="hint">Une boîte <b>commune</b> est un vrai destinataire, pas un partage :
        c'est ce qui permet de répondre depuis elle et de garder le fil entier pour toute
        l'équipe (Q026).</div></div>`;
  }

  function apps() {
    return `<div class="box"><h4>Applications connectées</h4>
      <table class="erpl"><tr><th>Application</th><th>Axes</th><th>Droits</th><th>Portée</th>
        <th>Jeton</th><th>Vue</th><th></th></tr>
      ${Fx().APPLICATIONS.map(a => `<tr>
        <td><b>${F.esc(a.label)}</b><br><span class="hash">${F.esc(a.code)}</span></td>
        <td>${a.axes.map(x => `<span class="tag ax">${F.esc(x)}</span>`).join(" ")}</td>
        <td>${F.esc(a.droits)}</td><td>${F.esc(a.portee)}</td>
        <td><span class="hash">${F.esc(a.jeton)}</span></td>
        <td>${F.esc(a.vu)}</td>
        <td class="num"><button class="hbtn ic dgr" data-adm="tok:${F.esc(a.code)}"
          title="Révoquer et régénérer">⟳</button></td></tr>`).join("")}</table>
      <div class="cbar"><button class="hbtn prim" data-adm="app:new">+ Connecter une application</button></div>
      <div class="hint">Le jeton est <b>opaque</b> et porte sa propre portée (D063/D037) : ce
        n'est pas un compte utilisateur déguisé. Révoquer coupe l'accès sans toucher aux tags
        déjà posés — ils appartiennent à l'application, pas au jeton.</div></div>

    <div class="box"><h4>Ce qu'une application peut faire</h4>
      <div class="hint">Trois droits par <b>axe</b>, pas par message (D018) : lire, écrire,
        administrer. « Retranche, jamais n'élargit » — une application ne voit jamais plus que
        le compte au nom duquel elle appelle, et l'unicité <code>(axe, application, valeur)</code>
        garantit que quatre Dolibarr font quatre jeux de tags sans s'écraser (D020).</div></div>`;
  }

  function axes() {
    return `<div class="box"><h4>Axes de tags</h4>
      <table class="erpl"><tr><th>Axe</th><th>Valeurs</th><th>Posé par</th><th>ACL</th><th></th></tr>
      ${Fx().AXES.map(a => `<tr><td>${a.icon} <b>${F.esc(a.label)}</b>
          <br><span class="hash">${F.esc(a.id)}</span></td>
        <td class="num">${Fx().valeurs[a.id].length}</td>
        <td>${a.id === "notification" || a.id === "social"
              ? `<span class="tag">filtre AtomBox</span>`
              : `<span class="tag">dolibarr-mmi</span>`}</td>
        <td><span class="st ok">lire</span> <span class="st wait">écrire</span></td>
        <td class="num"><button class="hbtn ic" data-adm="axe:${F.esc(a.id)}">⋯</button></td>
        </tr>`).join("")}
      <tr><td>🏷 <b>Libres</b><br><span class="hash">projet, type</span></td>
        <td class="num">—</td><td><span class="tag">utilisateur</span></td>
        <td><span class="st ok">lire</span> <span class="st ok">écrire</span></td><td></td></tr>
      </table>
      <div class="cbar"><button class="hbtn prim" data-adm="axe:new">+ Créer un axe</button></div>
      <div class="hint"><b>Q005 n'est pas tranchée</b> : qui crée un axe, qui le nomme. Le
        mécanisme est là (droit « administrer »), la politique non — et c'est elle qui décide si
        l'interopérabilité tient ou si chaque application invente son vocabulaire.</div></div>`;
  }

  function suite() {
    return `<div class="box"><h4>Fournisseurs de la suite</h4>
      <div class="hint">AtomBox se propose comme une <b>suite collaborative centrée sur la
        messagerie</b> : contacts, tâches, cloud et CRM naissent d'un email. Chaque capacité
        est un <b>contrat</b> — mais les composants <b>internes sont une cible de V3</b>. En
        V1 et V2, AtomBox est une messagerie qui <b>se branche</b> : par connecteur, ou
        absente. Ce que le contrat garantit, c'est que la V3 ne demandera aucune réécriture
        d'interface.</div>
      ${Object.entries(P.CAPACITES).map(([cap, c]) => {
        const a = P.actif(cap);
        return `<div class="capa">
          <div class="capt">${c.ic} <b>${F.esc(c.label)}</b>
            <span class="hash">${c.contrat.join("  ·  ")}</span></div>
          <div class="chips">${Object.entries(c.fournisseurs).map(([id, f]) =>
            `<span class="chip${id === a.id ? " on" : ""}${f.v > 1 ? " futur" : ""}"
              data-cap="${cap}" data-f="${id}"
              >${f.ic} ${F.esc(f.label)} ${jalon(f.v)}</span>`).join("")}</div>
          <div class="hint">${F.esc(a.note)}</div>
        </div>`; }).join("")}
      </div>`;
  }

  /* Les canaux ne sont pas des capacités : c'est de l'ingestion, donc le cœur du
     moteur. Ce volet ne sert qu'à une chose — rappeler ce qu'il ne faut PAS
     s'interdire dès la V1, parce que ces trois précautions sont gratuites
     maintenant et coûteuses plus tard. */
  function canaux() {
    return `<div class="box"><h4>Canaux d'entrée</h4>
      <table class="erpl"><tr><th>Canal</th><th>Jalon</th><th>État</th></tr>
      ${P.CANAUX.map(c => `<tr><td>${c.ic} <b>${F.esc(c.label)}</b></td>
        <td>${jalon(c.v) || `<span class="st ok">V1</span>`}</td>
        <td>${F.esc(c.etat)}</td></tr>`).join("")}</table>
      <div class="hint">La V4 ouvre AtomBox aux canaux non-mail. Ce n'est pas une capacité
        enfichable : un canal ENTRE dans le moteur, il ne se branche pas à côté.</div></div>

    <div class="box"><h4>Ce qu'il ne faut pas s'interdire, dès la V1</h4>
      <div class="hint">Trois précautions gratuites aujourd'hui, très coûteuses en V4 —
        même raisonnement que D062 pour le multi-organisation : on ne construit pas la suite,
        on ne se ferme pas la porte.</div>
      <table class="erpl">
        <tr><th>Précaution</th><th>Sans elle, en V4</th></tr>
        <tr><td><b>L'identifiant d'un correspondant a un TYPE</b><br>
          <span class="hash">correspondant_identifiant (type, valeur)</span> plutôt qu'une
          colonne <code>adresse</code></td>
          <td>un numéro de téléphone ne peut pas rejoindre l'identité qui porte déjà l'email
          — et c'est justement l'intérêt de D035</td></tr>
        <tr><td><b>Le message porte son CANAL</b><br>
          <span class="hash">message.canal = 'email'</span> dès la première ligne</td>
          <td>toutes les vues et tous les index supposent l'email, et il faut réécrire les
          requêtes une par une</td></tr>
        <tr><td><b>Ce qui est PROPRE À L'EMAIL est isolé</b><br>
          <span class="hash">message_email</span> : headers, DKIM/SPF, MIME, uid IMAP</td>
          <td>un SMS se retrouve avec douze colonnes nulles, et <code>message</code> devient
          une table à trous que plus personne n'ose modifier</td></tr>
      </table>
      <div class="hint">La troisième est la seule qui demande un arbitrage : elle coûte une
        jointure sur le chemin le plus chaud du produit. <b>Q038</b>.</div></div>`;
  }

  const RENDU = {
    etat, regles, boites, apps, axes, suite, canaux };

  /* ---- État & journal (F122, D152) — l'état est CHARGÉ, la page se peint deux fois -------- */
  const ko = o => o >= 1048576 ? (o / 1048576).toFixed(1) + " Mio" : Math.round(o / 1024) + " Kio";
  const NIV = { ERROR: "due", WARNING: "pause", INFO: "", DEBUG: "" };

  function etat() {
    const e = ABX.Views.Admin._etat;
    if (!e) return `<div class="box"><div class="empty">Chargement de l'état…</div></div>`;
    const f = e.files, retard = f.retard_secondes;
    const alerte = f.abandonnes || f.en_echec || retard > 300;
    return `<div class="box ${alerte ? "due" : ""}"><h4>${alerte ? "⚠" : "✓"} Files d'événements
        <button class="hbtn" id="etat-recharger" style="margin-left:auto">↻</button></h4>
      <div class="dmeta">Ce qu'AtomBox n'a pas encore fait, et ce qu'il a renoncé à faire. Un
        événement abandonné est une action perdue : c'est la ligne à lire en premier (D152).</div>
      <div class="kpis">
        ${[["en attente", f.en_attente, ""], ["en échec", f.en_echec, f.en_echec ? "due" : ""],
           ["abandonnés", f.abandonnes, f.abandonnes ? "due" : ""], ["traités", f.traites, "ok"],
           ["retard", retard > 60 ? Math.round(retard / 60) + " min" : retard + " s", retard > 300 ? "due" : ""]]
          .map(([l, v, c]) => `<div class="kpi ${c}"><b>${F.esc(String(v))}</b><span>${l}</span></div>`).join("")}
      </div>
      ${(e.en_echec || []).length ? `<table class="erpl" style="margin-top:8px">
        <tr><th>Événement</th><th>Tentatives</th><th>Raison</th><th>Depuis</th></tr>
        ${e.en_echec.map(x => `<tr><td>${F.esc(x.type)}</td><td>${x.tentatives}</td>
          <td class="hint">${F.esc(x.erreur || "")}</td><td class="hash">${F.esc((x.cree_le || "").slice(0, 19).replace("T", " "))}</td></tr>`).join("")}
        </table>` : ""}</div>

    <div class="box"><h4>Ingestion — le retard, dossier par dossier</h4>
      <div class="dmeta">C'est déjà une donnée : l'UID connu du serveur contre celui qu'on a ingéré (D043).
        Un dossier jamais relevé se voit tout de suite.</div>
      <table class="erpl"><tr><th>Boîte</th><th>Dossier</th><th>Messages</th><th>UID suivant</th><th>État</th></tr>
      ${(e.ingestion || []).map(d => `<tr><td class="hint">${F.esc(d.boite)}</td><td>${F.esc(d.dossier)}</td>
        <td>${d.messages}</td><td class="hash">${d.uid_suivant === null ? "—" : d.uid_suivant}</td>
        <td>${d.jamais_releve ? `<span class="st due">jamais relevé</span>` : `<span class="st ok">à jour</span>`}</td></tr>`).join("")}
      </table></div>

    <div class="box"><h4>Magasin et contenu</h4>
      <div class="kpis">
        ${[["messages", e.contenu.messages, ""], ["pièces jointes", e.contenu.pieces_jointes, ""],
           ["blobs", e.magasin.blobs, ""], ["stocké", ko(e.magasin.octets_stockes), ""],
           ["gagné", Math.round(e.magasin.gain * 100) + " %", "ok"],
           ["orphelins", e.magasin.orphelins, e.magasin.orphelins ? "pause" : ""]]
          .map(([l, v, c]) => `<div class="kpi ${c}"><b>${F.esc(String(v))}</b><span>${l}</span></div>`).join("")}
      </div>
      <div class="hint" style="margin-top:6px">Magasin : <code>${F.esc(e.magasin.chemin)}</code> ·
        journaux : <code>${F.esc(e.journaux || "")}</code>${e.magasin.orphelins
        ? ` · <b>${e.magasin.orphelins} blob(s) sans porteur</b> — le ramasse-miettes doit passer (D087)` : ""}</div></div>

    ${(e.regles_muettes || []).length ? `<div class="box pause"><h4>Règles muettes</h4>
      <div class="dmeta">Elles n'ont jamais rien attrapé. C'est ainsi qu'on trouve un « allof »
        saisi à la place d'un « anyof » — celui du chapitre 14 dormait depuis des années (D075 § 1).</div>
      ${e.regles_muettes.map(r => `<div class="kv"><span class="k">${F.esc(r.nom)}</span>
        <span class="v"><span class="st pause">jamais déclenchée</span></span></div>`).join("")}</div>` : ""}

    <div class="box"><h4>Journal</h4>
      <div class="frow">
        <select id="j-domaine">${["atombox", "erreurs", "auth", "api", "imap", "ingestion", "magasin", "filtres", "apps", "schema", "demon", "etat"]
          .map(d => `<option${d === (ABX.Views.Admin._jd || "atombox") ? " selected" : ""}>${d}</option>`).join("")}</select>
        <select id="j-niveau">${["DEBUG", "INFO", "WARNING", "ERROR"]
          .map(n => `<option${n === (ABX.Views.Admin._jn || "INFO") ? " selected" : ""}>${n}</option>`).join("")}</select>
        <input id="j-filtre" placeholder="un mot à retrouver" value="${F.esc(ABX.Views.Admin._jf || "")}">
      </div>
      <div class="journal">${(ABX.Views.Admin._journal || []).length
        ? ABX.Views.Admin._journal.map(l => `<div class="jl"><span class="hash">${F.esc(l.quand)}</span>
            <span class="st ${NIV[l.niveau] || ""}">${F.esc(l.niveau)}</span>
            <span class="jd">${F.esc(l.domaine)}</span> ${F.esc(l.message)}</div>`).join("")
        : `<div class="hint">Rien à ce niveau pour ce domaine.</div>`}</div>
      ${R.contexte("etat.journal", {})}</div>`;
  }

  /* ---- Règles (F016, D074) ---------------------------------------------------------------- */
  function regles() {
    const d = ABX.Views.Admin._filtres;
    if (!d) return `<div class="box"><div class="empty">Chargement des règles…</div></div>`;
    const f = d.filtres || [];
    return `<div class="box"><h4>${f.length} règle${f.length > 1 ? "s" : ""}
        <button class="hbtn on" id="r-nouvelle" style="margin-left:auto">+ Nouvelle règle</button></h4>
      <div class="dmeta">Elles s'évaluent <b>dans l'ordre</b>, à l'arrivée du message. « Arrêter »
        interrompt la chaîne, comme le <code>stop</code> de Sieve. Le compteur dit ce qui sert
        vraiment (D074, D075 § 1).</div>
      ${f.length ? `<table class="erpl"><tr><th>#</th><th>Règle</th><th>Si…</th><th>Alors</th>
          <th>Déclenchée</th><th></th></tr>
        ${f.map(x => `<tr>
          <td>${x.ordre}</td>
          <td><b>${F.esc(x.nom)}</b>${x.actif ? "" : ` <span class="st pause">inactive</span>`}</td>
          <td class="hint">${((x.predicat || {}).criteres || []).map(c =>
            `${F.esc(c.champ)} <i>${F.esc(c.operateur)}</i> ${F.esc(String(c.valeur ?? ""))}`)
            .join(((x.predicat || {}).mode === "ou") ? " <b>ou</b> " : " <b>et</b> ")}</td>
          <td>${F.esc((x.action || {}).type || "")}${(x.action || {}).dossier ? " → " + F.esc(x.action.dossier) : ""}</td>
          <td>${x.nb_declenchements ? `<span class="st ok">${x.nb_declenchements}×</span>`
                                    : `<span class="st pause">jamais</span>`}</td>
          <td><button class="hbtn ic" data-rtoggle="${F.esc(x.id)}" title="${x.actif ? "Désactiver" : "Activer"}">${x.actif ? "⏸" : "▶"}</button>
              <button class="hbtn ic dgr" data-rdel="${F.esc(x.id)}" title="Supprimer">✕</button></td></tr>`).join("")}
        </table>` : `<div class="hint">Aucune règle. En V0 le serveur trie encore à la livraison
          (Sieve) ; les règles existantes seront reprises ici en V1 (D147).</div>`}
      ${R.contexte("regles", {})}</div>
    ${ABX.Views.Admin._nouvelle ? R.render("regle.form", { d, form: ABX.Views.Admin._nouvelle }) : ""}`;
  }

  ABX.Views = ABX.Views || {};
  ABX.Views.Admin = {
    VOLETS,
    render(volet) {
      const v = RENDU[volet] ? volet : "boites";
      return `<div class="backbar"><button data-vue="liste">‹ Retour</button></div>
        <div class="dhead"><div class="dsubj">Administration</div>
          <div class="dmeta">rôles d'administration par utilisateur (D072) — ce POC affiche
            tout, un exploitant réel ne verra que ses volets</div>
          <div class="chips" style="margin-top:9px">${VOLETS.map(([k, l]) =>
            `<span class="chip${k === v ? " on" : ""}" data-vol="${k}">${l}</span>`).join("")}</div>
        </div>
        <div class="admin">${RENDU[v]()}</div>`;
    },
  };
})(window.ABX = window.ABX || {});
