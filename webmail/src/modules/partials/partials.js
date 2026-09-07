/* VUES PARTIELLES — le socle.

   Une carte de message est découpée en quatre morceaux (header, body, meta,
   actions) plutôt qu'en un bloc : c'est ce découpage qui rend la surcharge utile.
   Un dossier qui veut afficher « À : » au lieu de l'expéditeur ne réécrit pas la
   carte entière, il remplace l'en-tête. Les surcharges sont dans
   views/partials-overrides.js — ce fichier-ci n'a pas à les connaître. */
(function (ABX) {
  "use strict";
  const R = ABX.Registry, F = ABX.Fmt;

  /* ---- morceaux réutilisables ------------------------------------------- */
  R.define("tag.chip", ({ tag }) => ABX.V0() ? "" :
    `<span class="tag ax">${F.esc(tag.axe)}=${F.esc(tag.val)}</span>`);

  R.define("statut.chip", ({ m }) => ABX.V0() ? "" : m.motif_sortie
    ? `<span class="tag">${m.motif_sortie === "archive" ? "archivé" : "traité"}</span>` : "");

  /* ---- l'expediteur, normalise (D126) ------------------------------------
     Le nom affiche n'est PAS une identite : il est choisi par l'emetteur et rien
     ne l'authentifie. On montre donc le nom du carnet quand l'adresse est connue,
     et L'ADRESSE quand elle ne l'est pas — le nom declare passe en second, en
     gris, entre guillemets. L'usurpation par nom (D128, regle B1) porte en plus
     son propre signal. */
  R.define("expediteur", ({ m, long }) => {
    if (m.sens === "out") return `<span class="from">${F.esc(m.from_nom)}</span>`;
    /* V0 (D140) : pas de carnet, pas d'analyse — mais l'adresse reste visible à côté du
       nom (D126), parce que ça ne coûte rien et que c'est de la sécurité. */
    if (ABX.V0())
      return `<span class="from">${F.esc(m.from_nom)}</span> <span class="adr">&lt;${F.esc(m.from_adresse)}&gt;</span>`;
    if (m.connu)
      return `<span class="from" title="${F.esc(m.from_adresse)}">${F.esc(m.from_nom)}</span>` +
             (long ? ` <span class="adr">&lt;${F.esc(m.from_adresse)}&gt;</span>` : "");
    /* D130 — une machine n'est pas un inconnu suspect. Mettre l'adresse d'une
       newsletter en evidence, comme on le fait d'un inconnu, ferait crier l'ecran
       sur du courrier parfaitement normal : on affiche le service, et sa NATURE. */
    if (m.nature && m.nature !== "humain")
      return `<span class="from srv">${F.esc(m.from_nom)}</span>` +
             R.render("nature.chip", { m }) +
             (long ? ` <span class="adr">&lt;${F.esc(m.from_adresse)}&gt;</span>` : "");
    /* inconnu : l'adresse d'abord, le nom declare relegue */
    return `<span class="from adr-av">${F.esc(m.from_adresse)}</span>` +
           `<span class="decl">« ${F.esc(m.from_nom)} »</span>` +
           (m.usurpation ? `<span class="alerte" title="Le nom correspond a un contact connu,`
                    + ` mais l'adresse n'est pas la sienne (D128, B1)">⚠ nom usurpe</span>` : "");
  });

  /* D137 — l'indicateur de confiance. Il ne s'affiche QUE si le message est
     aligné : une adresse validée en base ne prouve rien sur un message qui ne
     vient peut-être pas d'elle. Marquer fiable un identifiant usurpable, ce
     serait donner à l'attaquant la cible exacte. */
  R.define("fiabilite", ({ m }) => {
    if (ABX.V0() || m.sens === "out" || m.fiabilite === undefined) return "";
    if (m.fiabilite >= 2)
      return `<span class="fiab f2" title="Expéditeur validé par quelqu'un de chez vous,
        et ce message est authentifié (DMARC aligné) — D137">✓</span>`;
    if (m.fiabilite === 1)
      return `<span class="fiab f1" title="Correspondant connu, message authentifié —
        aucune validation humaine (D137)">·</span>`;
    return "";
  });

  /* La nature ne se lit pas comme une alerte : c'est un fait de classement.
     Elle dit ce que le message attend de nous — rien, ou une action (D130). */
  const NATURES = {
    liste:        ["diffusion",    "nat-l", "Diffusion (List-Id) — n'entre pas dans la file des non traités"],
    notification: ["notification", "nat-n", "Notification automatique — entre dans la file : une facture attend un paiement"],
    service:      ["service",      "nat-s", "Message de service (DSN, absence) — se rattache à un envoi"],
  };
  R.define("nature.chip", ({ m }) => {
    if (ABX.V0()) return "";
    const n = NATURES[m.nature];
    return n ? `<span class="nat ${n[1]}" title="${F.esc(n[2])} — D130">${n[0]}</span>` : "";
  });

  /* ---- carte de message (liste) ----------------------------------------- */
  R.define("message.card.header", ({ m }) =>
    `<div class="r1">${R.render("fiabilite", { m })}${R.render("expediteur", { m })}
       <span class="dt">${F.dt(m.date_recue)}</span></div>`);

  R.define("message.card.body", ({ m }) =>
    `<div class="subj">${F.esc(m.sujet)}</div>
     <div class="snip">${F.esc(m.snippet)}</div>`);

  R.define("message.card.meta", ({ m }) =>
    `<div class="meta">${m.nb_pieces_jointes ? `<span class="pj">📎 ${m.nb_pieces_jointes} · ${F.poids(m.pj_ko)}</span>` : ""}
       ${R.render("statut.chip", { m })}
       ${m.tags.map(tag => R.render("tag.chip", { tag })).join("")}</div>`);

  R.define("message.card.actions", ({ m }) => {
    const ou = m.dossier || m.dossier_origine;
    const boutons = ou === "trash"
      ? `<button data-act="restaurer" title="Restaurer">↩</button>`
      : ou === "junk"
        ? `<button data-act="nonJunk" title="Ce n'est pas un indésirable">✓ ham</button>
           <button data-act="corbeille" title="Mettre à la corbeille">🗑</button>`
        : `<button data-act="traiter" title="Marquer traité">✓</button>
           <button data-act="archiver" title="Archiver">🗄</button>
           <button data-act="junk" title="Indésirable">🚫</button>
           <button data-act="corbeille" title="Mettre à la corbeille">🗑</button>`;
    return `<div class="mact">${boutons}</div>`;
  });

  R.define("message.card", ctx => {
    const { m, selection } = ctx;
    return `<div class="msg${m.lu ? "" : " unread"}${selection === m.id ? " sel" : ""}"
        data-id="${F.esc(m.id)}">
        ${R.render("message.card.header", ctx)}
        ${R.render("message.card.body", ctx)}
        ${R.render("message.card.meta", ctx)}
        ${R.render("message.card.actions", ctx)}
      </div>`;
  });

  /* ---- pièces jointes ---------------------------------------------------- */
  R.define("attachment.card", ({ p, i }) => {
    const b = p.b, div = p.declare !== b.mime, At = ABX.Attachments;
    return `<div class="pjc" data-pj="${i}">
      <span class="pic">${b.ic}</span>
      <span class="pn"><b>${F.esc(p.nom)}</b>
        <span class="ps">${F.poids(b.ko)} · <span class="hash">sha256:${b.sha}…</span></span>
        <span class="bd">
          <span class="badge" title="${F.esc(b.mime)}">${F.esc(F.mimeC(b.mime))}</span>
          ${b.refs > 1
            ? `<span class="badge ok">stockée une fois · ${b.refs} liaisons</span>`
            : `<span class="badge">octets uniques</span>`}
          ${div ? `<span class="badge w">déclaré ${F.esc(F.mimeC(p.declare))} — c'est le type
                   DÉTECTÉ qui fait foi</span>` : ""}
          ${b.eml ? `<span class="badge">message/rfc822 — dédupliqué comme un message (D066)</span>` : ""}
          ${At.recompressable(b)
            ? `<span class="badge w">recompression proposée · gain ≈ ${F.poids(At.gain(b))} (D070)</span>` : ""}
        </span></span></div>`;
  });

  R.define("attachment.list", ({ m }) => {
    if (!m.pieces_jointes.length) return "";
    const tot = m.pj_ko;
    return `<div class="box"><h4>Pièces jointes — ${m.pieces_jointes.length} · ${F.poids(tot)} décodés,
        ${F.poids(Math.round(tot * 1.37))} sur le fil (base64, D069)</h4>
      <div class="pjl">${m.pieces_jointes.map((p, i) => R.render("attachment.card", { p, i })).join("")}</div>
      <div class="dmeta" style="margin-top:8px">Le <b>nom</b> et le <b>type déclaré</b> sont portés
        par la liaison, les <b>octets</b> et le <b>type détecté</b> par le blob : c'est ce qui permet
        de dédupliquer sans mentir sur le message d'origine (D024/D025/D032).</div></div>`;
  });

  /* ---- contexte métier --------------------------------------------------- */
  R.define("erp.panel", ({ m }) => {
    if (ABX.V0()) return "";
    const Erp = ABX.Erp, t = Erp.tagDe(m);
    if (!t) return "";
    const f = Erp.fiche(t.axe, t.val), c = f.cfg;
    return `<div class="box erp"><h4>${c.ic} ${F.esc(c.nom)} — contexte métier</h4>
      <div class="kv"><span class="k">${F.esc(c.objet)}</span><span><b>${F.esc(t.val)}</b>
        <span class="tag ax">${F.esc(f.reference)}</span>
        <span class="tag">application ${F.esc(c.app)}</span>
        <span class="tag">client depuis ${f.depuis}</span></span></div>
      <div class="kv"><span class="k">Correspondant</span><span>${F.esc(m.from_adresse)}
        <span class="tag">→ identité résolue par l'annuaire (D035)</span></span></div>
      <div class="kv"><span class="k">Encours</span><span><b>${F.euro(f.encours)}</b>
        ${f.echu ? `<span class="st due">dont ${F.euro(f.echu)} échu</span>`
                 : `<span class="st ok">rien d'échu</span>`}</span></div>
      <table class="erpl">${f.objets.map(o => `<tr>
        <td>${o.type}</td><td><b>${F.esc(o.reference)}</b></td>
        <td class="num">${F.euro(o.montant)}</td>
        <td class="num"><span class="st ${Erp.statutClasse(o)}">${o.statut}</span></td></tr>`).join("")}</table>
      <div class="dacts" style="margin-top:9px">
        <button class="hbtn" data-e="res">↳ D'où vient ce rattachement ?</button>
        <button class="hbtn" data-e="lie">🔗 Lier à une pièce</button>
        <button class="hbtn" data-e="inv">↔ Ce que ${F.esc(c.app)} affiche de son côté</button>
        <button class="hbtn" data-e="push">⇪ Notifier l'application</button>
      </div>
      <div class="dmeta" style="margin-top:8px">AtomBox ne stocke aucun montant : il porte le tag et
        la référence externe (D020). Ce cadre est <b>rempli par un appel à l'application</b> au moment
        de l'affichage — c'est le prix à payer pour ne pas dupliquer l'ERP, et le premier endroit
        où il faudra un cache (Q031).</div></div>`;
  });

  /* ---- tags : la seule partie du message que l'utilisateur écrit ---------- */
  R.define("message.tags", ({ m }) => {
    if (ABX.V0()) return "";
    const AXES = (ABX.Ref.axes || []).map(a => a.id).concat(["projet", "type"]);
    return `<div class="box"><h4>Tags — plusieurs applications, sans écrasement (D017/D020)</h4>
      ${m.tags.length ? m.tags.map((t, i) => `<div class="kv">
          <span class="k">${F.esc(t.axe)}</span>
          <span class="v"><b>${F.esc(t.val)}</b>
            <span class="tag">posé par ${F.esc(t.src)}</span>
            <button class="tagx" data-newv="${i}" title="Créer un dossier virtuel pour ce tag">⊕</button><button class="tagx" data-untag="${i}" title="Retirer ce tag">✕</button></span>
        </div>`).join("") : `<div class="dmeta">aucun tag</div>`}
      <div class="frow" style="margin-top:9px">
        <label>Ajouter</label>
        <select id="t_axe" style="flex:0 0 150px">${AXES.map(a =>
          `<option value="${F.esc(a)}">${F.esc(a)}</option>`).join("")}</select>
        <input id="t_val" list="t_vals" placeholder="valeur">
        <button class="hbtn" id="t_add">+</button>
      </div>
      <datalist id="t_vals"></datalist>
      <div class="hint">Un tag posé à la main appartient à l'utilisateur ; un tag posé par un
        connecteur lui appartient (D019/D021) — le retirer ici ne l'empêche pas d'être reposé.</div>
    </div>`;
  });

  /* Le SUIVI D'UN ENVOI (D099) — sous un message émis : où il en est, destinataire par
     destinataire, et le bouton qui le relance quand il n'est pas parti. Un message « envoyé »
     qui n'est jamais parti est le pire mensonge d'un webmail : cet encart existe pour ça. */
  const ENVOI_ETATS = { remis: ["ok", "✓", "Remis au relais"], livre: ["ok", "✓", "Livré"],
    accepte: ["ok", "✓", "Accepté"], en_attente: ["wait", "⏳", "En attente d'envoi"],
    en_echec: ["due", "⚠", "Envoi en échec"], rejete: ["due", "✗", "Rejeté"],
    abandonne: ["due", "✗", "Envoi abandonné"], differe: ["wait", "⏳", "Différé"] };
  R.define("message.envoi", ({ e }) => {
    if (!e) return "";
    const [cls, ic, titre] = ENVOI_ETATS[e.etat] || ["", "·", e.etat];
    return `<div class="box envoi ${cls}"><h4>${ic} ${F.esc(titre)}
        ${e.relancable ? `<button class="hbtn" id="relancer" title="Remettre cet envoi dans la file">↻ Relancer l'envoi</button>` : ""}</h4>
      <div class="dmeta">${F.esc(e.detail || "")}</div>
      ${(e.destinataires || []).map(d => `<div class="kv"><span class="k">${F.esc(d.adresse)}</span>
        <span class="v"><span class="st ${(ENVOI_ETATS[d.etat] || [""])[0]}">${F.esc((ENVOI_ETATS[d.etat] || [0, 0, d.etat])[2])}</span>
        ${d.code ? `<span class="dmeta">${F.esc(d.code)}</span>` : ""}</span></div>`).join("")}
      ${R.contexte("envoi", { e })}</div>`;
  });

  /* ---- arborescence ------------------------------------------------------ */
  R.define("nav.node", ({ o, cls, sel }) =>
    `<div class="node ${cls || ""}${sel ? " sel" : ""}" data-id="${F.esc(o.id)}"
       data-label="${F.esc(o.label)}" data-kind="${o.kind || ""}" data-axe="${o.axe || ""}">
       <span class="tw">${o.tw || ""}</span><span class="ic">${o.icon || ""}</span>
       <span class="lb">${F.esc(o.label)}</span>
       ${o.axe && o.kind === "axe" ? R.render("nav.axe.outils", { o }) : ""}
       ${ABX.V0() ? "" : R.render("nav.dossier.outils", { o })}
       ${R.render("nav.compteur", { o })}</div>`);

  /* Le compteur d'un dossier : NON LUS / TOTAL. Le non-lu en gras quand il y en
     a, le total toujours en gris — un dossier vide ne montre rien. Deux nombres
     parce qu'ils répondent à deux questions : « ai-je du nouveau ? » et « combien
     y a-t-il là-dedans ? » — et l'ancien affichage cachait la seconde dès que
     la première avait une réponse. */
  R.define("nav.compteur", ({ o }) => {
    const t = o.total || 0, u = o.unread || 0;
    return `<span class="ct" title="${u} non lu${u > 1 ? "s" : ""} sur ${t}">${
      u ? `<b>${u}</b>` : u}<span class="sep">/</span>${t}</span>`;
  });

  /* Les commandes d'ordre n'apparaissent qu'au survol : une arborescence n'est
     pas un tableau de bord, et six boutons par ligne la rendraient illisible. */
  R.define("nav.axe.outils", ({ o }) =>
    `<span class="axops">
       <button class="axop" data-mv="up" data-axe="${F.esc(o.axe)}"
         title="Monter"${o.rang === 0 ? " disabled" : ""}>▲</button>
       <button class="axop" data-mv="down" data-axe="${F.esc(o.axe)}"
         title="Descendre"${o.dernier ? " disabled" : ""}>▼</button>
       <button class="axop${o.triAxe === "alpha" ? " on" : ""}" data-tri="${F.esc(o.axe)}"
         title="${o.triAxe === "alpha" ? "Trié A→Z — repasser au plus récent"
                                       : "Trié par activité — passer en A→Z"}">${
           o.triAxe === "alpha" ? "A↓" : "⏱"}</button>
     </span>`);

  /* Les outils de TOUT dossier, au survol : l'épingle (D144) — allumée quand le
     dossier est en tête — et, pour un dossier virtuel personnel, sa suppression
     (D143 : on jette une définition, jamais un message, donc sans confirmation). */
  R.define("nav.dossier.outils", ({ o }) =>
    `<span class="nops">${o.kind === "perso"
       ? `<button class="axop" data-delv="${F.esc(o.id)}" title="Supprimer ce dossier virtuel — aucun message n'est touché">✕</button>` : ""
     }<button class="axop${o.epingle ? " on" : ""}" data-pin="${F.esc(o.id)}"
       title="${o.epingle ? "Désépingler" : "Épingler en tête de liste"}">📌</button></span>`);

  /* Le formulaire d'un dossier virtuel personnel (D143) : un nom, des critères.
     Chaque critère est un axe et une valeur FACULTATIVE — vide, c'est toute la
     famille. Plusieurs critères se combinent en ET ; pour un OU ou une négation,
     c'est une règle du moteur de filtres (D074), pas ce formulaire. */
  R.define("nav.virtuel.form", ({ form }) => {
    const axes = ABX.Ref.axes;
    return `<div class="vform" id="vform">
      <input id="v_label" placeholder="Nom du dossier (sinon : les critères)" value="${F.esc(form.label || "")}">
      ${form.criteres.map((c, i) => `<div class="vcrit">
        <select class="v_axe" data-i="${i}">${axes.map(a =>
          `<option value="${F.esc(a.id)}"${a.id === c.axe ? " selected" : ""}>${F.esc(a.label)}</option>`).join("")}</select>
        <input class="v_val" data-i="${i}" list="v_vals_${i}" placeholder="toute la famille" value="${F.esc(c.val || "")}">
        <datalist id="v_vals_${i}">${(ABX.Ref.valeurs[c.axe] || []).map(v =>
          `<option value="${F.esc(v.label)}">`).join("")}</datalist></div>`).join("")}
      <div class="frow"><button class="hbtn" id="v_plus" title="Ajouter un critère — les critères se cumulent (ET)">+ critère</button>
        <button class="hbtn on" id="v_ok">Créer</button><button class="hbtn" id="v_non">Annuler</button></div>
      ${R.contexte("nav.virtuel", { form })}</div>`;
  });

  /* Les critères d'un dossier virtuel personnel, rappelés en tête de sa liste :
     un filtre qu'on ne voit pas est un filtre qu'on oublie. */
  R.define("liste.criteres", ({ folder }) => {
    const v = ABX.Api.cache.virtuels().find(x => x.id === folder.id);
    return v ? v.criteres.map(c => `<span class="chip on" style="margin-left:6px" title="critère du dossier virtuel">${
      F.esc(c.val ? c.axe + " = " + c.val : "famille " + c.axe)}</span>`).join("") : "";
  });

  /* ---- fil de discussion ------------------------------------------------- */
  R.define("thread.item", ({ x, courant }) =>
    `<div class="tm${courant ? " cur" : ""}">
       <div class="h"><b>${F.esc(x.from_nom)}</b><span class="dt">${F.dt(x.date_recue)}</span></div>
       <div class="b">${F.esc(x.corps)}</div></div>`);
})(window.ABX = window.ABX || {});
