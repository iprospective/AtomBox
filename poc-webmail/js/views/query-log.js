/* VUE DU JOURNAL DES REQUÊTES — le livrable du POC, affiché en continu. */
(function (ABX) {
  "use strict";
  const F = ABX.Fmt, St = ABX.Store;

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
          <code>${F.esc(i.sql)}</code>
          ${i.index ? `<div class="idx${i.warn ? " w" : ""}">${i.warn ? "⚠ " : "↳ "}${F.esc(i.index)}</div>` : ""}
        </div>`).join("")}`;
    },
  };
})(window.ABX = window.ABX || {});
