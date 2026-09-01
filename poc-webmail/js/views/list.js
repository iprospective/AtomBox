/* VUE LISTE. Elle ne connaît aucune particularité de dossier : elle demande
   « message.card » avec une variante, et le registre décide (views/partials*.js). */
(function (ABX) {
  "use strict";
  const R = ABX.Registry, F = ABX.Fmt, C = ABX.Corpus;

  const FILTRES = [["file","En file"], ["non_lus","Non lus"], ["recents","30 derniers jours"],
                   ["pj","Avec pièce jointe"], ["lourds","Lourds (> 2 Mo)"], ["sortis","Traités / archivés"]];
  /* Le sens est un axe à part : on le croise avec le filtre, on ne le remplace pas. */
  const SENS = [["tous","Tous"], ["in","↓ Reçus"], ["out","↑ Envoyés"]];
  const SANS_SENS = { sent:1, drafts:1 };   // là, tout est déjà du même sens

  /* La variante d'affichage : le dossier d'abord, sinon l'axe — et seulement si
     une partielle existe pour lui. Ajouter un axe spécialisé = ajouter une
     partielle, sans toucher à ce fichier. */
  function variante(m) {
    /* Ce qui compte est le SENS, pas le dossier : un message sortant rangé dans un
       dossier client doit montrer son destinataire, comme dans « Envoyés ». */
    if ((m.sens || "in") === "out") return "sent";
    const f = m.dossier || m.fid;
    const ax = f.split(":")[0];
    return R.has("message.card.meta", ax) || R.has("message.card.body", ax)
        || R.has("message.card.header", ax) ? ax : null;
  }

  ABX.Views = ABX.Views || {};
  ABX.Views.List = {
    FILTRES, SENS, variante,
    render(ui, messages, selection) {
      const vueSortie = !!C.VUES[ui.folder.id];
      let h = `<div class="backbar"><button data-vue="nav">‹ Dossiers</button>
          <span style="color:var(--muted);font-size:11.5px">${F.esc(ui.folder.label)}</span></div>
        <div class="lbar"><div class="t">${F.esc(ui.folder.label)}
          <small>${messages.length} message${messages.length > 1 ? "s" : ""}</small>
          ${ui.folder.id === "trash" && messages.length
            ? `<button class="hbtn dgr" id="vider" style="margin-left:auto">Vider la corbeille</button>` : ""}</div>
        <div class="chips">${FILTRES
          .filter(([k]) => !(vueSortie && (k === "file" || k === "sortis")))
          .map(([k, l]) => `<span class="chip${ui.filtre === k ? " on" : ""}" data-f="${k}">${l}</span>`).join("")}
          <select class="sortsel" id="tri">
            <option value="date_desc">Date ↓</option><option value="date_asc">Date ↑</option>
            <option value="from">Expéditeur</option><option value="subj">Sujet</option>
            <option value="size">Taille</option></select></div>
        ${SANS_SENS[ui.folder.id] ? "" : `<div class="chips" style="margin-top:6px">
          ${SENS.map(([k, l]) => `<span class="chip${(ui.sens || "tous") === k ? " on" : ""}"
            data-s="${k}">${l}</span>`).join("")}
          ${ui.folder.kind === "axe"
            ? `<span class="chip on" style="margin-left:6px">↳ inclut les sous-dossiers</span>` : ""}</div>`}
        ${SANS_SENS[ui.folder.id] && ui.folder.kind === "axe" ? `<div class="chips" style="margin-top:6px">
          <span class="chip on">↳ inclut les sous-dossiers</span></div>` : ""}</div>`;

      h += messages.length
        ? messages.map(m => R.render("message.card", { m, selection, variant: variante(m) })).join("")
        : `<div class="empty">Aucun message ne correspond à ce filtre.</div>`;
      return h;
    },
  };
})(window.ABX = window.ABX || {});
