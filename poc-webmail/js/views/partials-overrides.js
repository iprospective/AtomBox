/* SURCHARGES DE VUES PARTIELLES.

   Aucun autre fichier n'a besoin de connaître ce qui suit : la vue liste
   demande « message.card » avec une variante, le registre choisit. Supprimer
   ce fichier ne casse rien — tout retombe sur le socle.

   La variante est calculée par views/list.js : le dossier d'abord (sent),
   sinon l'axe (notification, sav, social…). Il suffit donc d'enregistrer une
   partielle sous le nom d'un axe pour que cet axe s'affiche autrement. */
(function (ABX) {
  "use strict";
  const R = ABX.Registry, F = ABX.Fmt;

  /* --- Envoyés et brouillons : ce qui compte est le DESTINATAIRE ---------- */
  R.defineFor("message.card.header", "sent", ({ m }) =>
    `<div class="r1"><span class="from">À : ${F.esc((m.to || []).join(", ") || "—")}</span>
       <span class="dt">${F.dt(m.date)}</span></div>`);

  /* --- Notifications : volumineuses et répétitives, donc compactes -------- */
  R.defineFor("message.card.body", "notification", ({ m }) =>
    `<div class="subj">${F.esc(m.subject)}</div>`);

  R.defineFor("message.card.meta", "notification", ({ m }) =>
    `<div class="meta"><span class="tag">${F.esc(m.mail.split("@")[1] || "système")}</span>
       ${m.pj ? `<span class="pj">📎 ${m.pj}</span>` : ""}</div>`);

  /* --- SAV : le ticket et son état passent AVANT le reste ----------------- */
  R.defineFor("message.card.meta", "sav", ctx => {
    const { m } = ctx, t = ABX.Erp.tagDe(m);
    const f = t ? ABX.Erp.fiche(t.axe, t.val) : null;
    const piece = f && f.objets[0];
    return `<div class="meta">
      ${f ? `<span class="tag ax">${F.esc(f.ref)}</span>` : ""}
      ${piece ? `<span class="st ${ABX.Erp.statutClasse(piece)}">${piece.statut}</span>` : ""}
      ${m.pj ? `<span class="pj">📎 ${m.pj} · ${F.poids(m.pj_ko)}</span>` : ""}
      ${R.render("statut.chip", { m })}</div>`;
  });

  /* --- Réseaux sociaux : ni pièces jointes ni tags, une source ------------ */
  R.defineFor("message.card.meta", "social", ({ m }) =>
    `<div class="meta"><span class="tag">${F.esc((m.tags[0] && m.tags[0].val) || "réseau")}</span>
       ${R.render("statut.chip", { m })}</div>`);
})(window.ABX = window.ABX || {});
