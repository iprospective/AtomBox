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
  R.define("tag.chip", ({ tag }) =>
    `<span class="tag ax">${F.esc(tag.axe)}=${F.esc(tag.val)}</span>`);

  R.define("statut.chip", ({ m }) => m.motif
    ? `<span class="tag">${m.motif === "archive" ? "archivé" : "traité"}</span>` : "");

  /* ---- l'expediteur, normalise (D126) ------------------------------------
     Le nom affiche n'est PAS une identite : il est choisi par l'emetteur et rien
     ne l'authentifie. On montre donc le nom du carnet quand l'adresse est connue,
     et L'ADRESSE quand elle ne l'est pas — le nom declare passe en second, en
     gris, entre guillemets. L'usurpation par nom (D128, regle B1) porte en plus
     son propre signal. */
  R.define("expediteur", ({ m, long }) => {
    if (m.sens === "out") return `<span class="from">${F.esc(m.from)}</span>`;
    if (m.connu)
      return `<span class="from" title="${F.esc(m.mail)}">${F.esc(m.from)}</span>` +
             (long ? ` <span class="adr">&lt;${F.esc(m.mail)}&gt;</span>` : "");
    /* D130 — une machine n'est pas un inconnu suspect. Mettre l'adresse d'une
       newsletter en evidence, comme on le fait d'un inconnu, ferait crier l'ecran
       sur du courrier parfaitement normal : on affiche le service, et sa NATURE. */
    if (m.nature && m.nature !== "humain")
      return `<span class="from srv">${F.esc(m.from)}</span>` +
             R.render("nature.chip", { m }) +
             (long ? ` <span class="adr">&lt;${F.esc(m.mail)}&gt;</span>` : "");
    /* inconnu : l'adresse d'abord, le nom declare relegue */
    return `<span class="from adr-av">${F.esc(m.mail)}</span>` +
           `<span class="decl">« ${F.esc(m.from)} »</span>` +
           (m.spoof ? `<span class="alerte" title="Le nom correspond a un contact connu,`
                    + ` mais l'adresse n'est pas la sienne (D128, B1)">⚠ nom usurpe</span>` : "");
  });

  /* La nature ne se lit pas comme une alerte : c'est un fait de classement.
     Elle dit ce que le message attend de nous — rien, ou une action (D130). */
  const NATURES = {
    liste:        ["diffusion",    "nat-l", "Diffusion (List-Id) — n'entre pas dans la file des non traités"],
    notification: ["notification", "nat-n", "Notification automatique — entre dans la file : une facture attend un paiement"],
    service:      ["service",      "nat-s", "Message de service (DSN, absence) — se rattache à un envoi"],
  };
  R.define("nature.chip", ({ m }) => {
    const n = NATURES[m.nature];
    return n ? `<span class="nat ${n[1]}" title="${F.esc(n[2])} — D130">${n[0]}</span>` : "";
  });

  /* ---- carte de message (liste) ----------------------------------------- */
  R.define("message.card.header", ({ m }) =>
    `<div class="r1">${R.render("expediteur", { m })}
       <span class="dt">${F.dt(m.date)}</span></div>`);

  R.define("message.card.body", ({ m }) =>
    `<div class="subj">${F.esc(m.subject)}</div>
     <div class="snip">${F.esc(m.snippet)}</div>`);

  R.define("message.card.meta", ({ m }) =>
    `<div class="meta">${m.pj ? `<span class="pj">📎 ${m.pj} · ${F.poids(m.pj_ko)}</span>` : ""}
       ${R.render("statut.chip", { m })}
       ${m.tags.map(tag => R.render("tag.chip", { tag })).join("")}</div>`);

  R.define("message.card.actions", ({ m }) => {
    const ou = m.dossier || m.fid;
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
          ${b.eml ? `<span class="badge">message/rfc822 — dédupliqué comme un message (D66)</span>` : ""}
          ${At.recompressable(b)
            ? `<span class="badge w">recompression proposée · gain ≈ ${F.poids(At.gain(b))} (D70)</span>` : ""}
        </span></span></div>`;
  });

  R.define("attachment.list", ({ m }) => {
    if (!m.pjs.length) return "";
    const tot = m.pj_ko;
    return `<div class="box"><h4>Pièces jointes — ${m.pjs.length} · ${F.poids(tot)} décodés,
        ${F.poids(Math.round(tot * 1.37))} sur le fil (base64, D69)</h4>
      <div class="pjl">${m.pjs.map((p, i) => R.render("attachment.card", { p, i })).join("")}</div>
      <div class="dmeta" style="margin-top:8px">Le <b>nom</b> et le <b>type déclaré</b> sont portés
        par la liaison, les <b>octets</b> et le <b>type détecté</b> par le blob : c'est ce qui permet
        de dédupliquer sans mentir sur le message d'origine (D24/D25/D32).</div></div>`;
  });

  /* ---- contexte métier --------------------------------------------------- */
  R.define("erp.panel", ({ m }) => {
    const Erp = ABX.Erp, t = Erp.tagDe(m);
    if (!t) return "";
    const f = Erp.fiche(t.axe, t.val), c = f.cfg;
    return `<div class="box erp"><h4>${c.ic} ${F.esc(c.nom)} — contexte métier</h4>
      <div class="kv"><span class="k">${F.esc(c.objet)}</span><span><b>${F.esc(t.val)}</b>
        <span class="tag ax">${F.esc(f.ref)}</span>
        <span class="tag">application ${F.esc(c.app)}</span>
        <span class="tag">client depuis ${f.depuis}</span></span></div>
      <div class="kv"><span class="k">Correspondant</span><span>${F.esc(m.mail)}
        <span class="tag">→ identité résolue par l'annuaire (D35)</span></span></div>
      <div class="kv"><span class="k">Encours</span><span><b>${F.euro(f.encours)}</b>
        ${f.echu ? `<span class="st due">dont ${F.euro(f.echu)} échu</span>`
                 : `<span class="st ok">rien d'échu</span>`}</span></div>
      <table class="erpl">${f.objets.map(o => `<tr>
        <td>${o.type}</td><td><b>${F.esc(o.ref)}</b></td>
        <td class="num">${F.euro(o.montant)}</td>
        <td class="num"><span class="st ${Erp.statutClasse(o)}">${o.statut}</span></td></tr>`).join("")}</table>
      <div class="dacts" style="margin-top:9px">
        <button class="hbtn" data-e="res">↳ D'où vient ce rattachement ?</button>
        <button class="hbtn" data-e="lie">🔗 Lier à une pièce</button>
        <button class="hbtn" data-e="inv">↔ Ce que ${F.esc(c.app)} affiche de son côté</button>
        <button class="hbtn" data-e="push">⇪ Notifier l'application</button>
      </div>
      <div class="dmeta" style="margin-top:8px">AtomBox ne stocke aucun montant : il porte le tag et
        la référence externe (D20). Ce cadre est <b>rempli par un appel à l'application</b> au moment
        de l'affichage — c'est le prix à payer pour ne pas dupliquer l'ERP, et le premier endroit
        où il faudra un cache (Q31).</div></div>`;
  });

  /* ---- tags : la seule partie du message que l'utilisateur écrit ---------- */
  R.define("message.tags", ({ m }) => {
    const AXES = ABX.Fixtures.AXES.map(a => a.id).concat(["projet", "type"]);
    return `<div class="box"><h4>Tags — plusieurs applications, sans écrasement (D17/D20)</h4>
      ${m.tags.length ? m.tags.map((t, i) => `<div class="kv">
          <span class="k">${F.esc(t.axe)}</span>
          <span class="v"><b>${F.esc(t.val)}</b>
            <span class="tag">posé par ${F.esc(t.src)}</span>
            <button class="tagx" data-untag="${i}" title="Retirer ce tag">✕</button></span>
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
        connecteur lui appartient (D19/D21) — le retirer ici ne l'empêche pas d'être reposé.</div>
    </div>`;
  });

  /* ---- arborescence ------------------------------------------------------ */
  R.define("nav.node", ({ o, cls, sel }) =>
    `<div class="node ${cls || ""}${sel ? " sel" : ""}" data-id="${F.esc(o.id)}"
       data-label="${F.esc(o.label)}" data-kind="${o.kind || ""}" data-axe="${o.axe || ""}">
       <span class="tw">${o.tw || ""}</span><span class="ic">${o.icon || ""}</span>
       <span class="lb">${F.esc(o.label)}</span>
       <span class="ct${o.unread ? " b" : ""}">${o.unread ? o.unread : (o.total || "")}</span></div>`);

  /* ---- fil de discussion ------------------------------------------------- */
  R.define("thread.item", ({ x, courant }) =>
    `<div class="tm${courant ? " cur" : ""}">
       <div class="h"><b>${F.esc(x.from)}</b><span class="dt">${F.dt(x.date)}</span></div>
       <div class="b">${F.esc(x.body)}</div></div>`);
})(window.ABX = window.ABX || {});
