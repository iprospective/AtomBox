/* VUE DU JOURNAL DES REQUÊTES — le livrable du POC, affiché en continu. */
(function (ABX) {
  "use strict";
  const F = ABX.Fmt, St = ABX.Store;

  /* L'index supposé, ou l'avertissement — même rendu pour une requête et ses filles. */
  const bloc = i => i.index
    ? `<div class="idx${i.warn ? " w" : ""}">${i.warn ? "⚠ " : "↳ "}${F.esc(i.index)}</div>` : "";

  ABX.Views = ABX.Views || {};
  ABX.Views.QueryLog = {
    render(entrees) {
      const nMut = Object.keys(St.ratt).length;
      return `<div class="qh"><b>Requêtes impliquées</b>
          <button class="hbtn" id="qclr">vider</button></div>
        <div class="note">Le livrable du POC, au-delà des écrans (D79) : chaque geste note la
          question qu'il pose aux données. C'est cette liste qui dictera les index.<br>
          <b>État local</b> : ${nMut} rattachement(s) modifié(s), ${St.crees.length} message(s)
          écrit(s), ${St.tailleKo()} ko en localStorage — le corpus, lui, est réengendré à chaque
          chargement : seul le rattachement se stocke.</div>
        ${entrees.map(i => `<div class="qi${i.kind ? " " + i.kind : ""}">
          <div class="lbl">${i.t.toTimeString().slice(0, 8)} — ${F.esc(i.label)}
            ${i.kind === "api" ? `<span class="badge">API</span>` : ""}</div>
          ${i.sql ? `<code>${F.esc(i.sql)}</code>` : ""}
          ${bloc(i)}
          ${i.enfants && i.enfants.length ? `<div class="sub">
            <div class="subt">${i.enfants.length} requête(s) déclenchée(s)
              ${i.kind === "api" ? "côté AtomBox" : ""}</div>
            ${i.enfants.map(e => `<div class="qs">
              ${e.label ? `<div class="lbl">${F.esc(e.label)}</div>` : ""}
              <code>${F.esc(e.sql)}</code>
              ${bloc(e)}</div>`).join("")}</div>` : ""}
        </div>`).join("")}`;
    },
  };
})(window.ABX = window.ABX || {});
