/* VUE ONGLETS — deuxième ligne d'en-tête, toujours visible.
   Un onglet « provisoire » (italique) est remplacé par le clic suivant ; un
   double-clic l'épingle. C'est la convention des éditeurs, et elle évite
   d'accumuler vingt onglets en parcourant une liste. */
(function (ABX) {
  "use strict";
  const F = ABX.Fmt, C = ABX.Corpus;

  ABX.Views = ABX.Views || {};
  ABX.Views.Tabs = {
    ICONES: { compo:"✎", msg:"✉", admin:"⚙", pj:"📎", page:"📖" },
    titre(t) {
      if (t.type === "compo") return t.data.sujet || "(sans sujet)";
      if (t.type === "admin") return "Administration";
      if (t.type === "pj")    return "Pièces jointes";
      if (t.type === "page")  return ABX.Views.Pages.titre(t.page);
      const m = C.par(t.id);
      return m ? m.subject : "(message effacé)";
    },
    render(ui) {
      return ui.tabs.map(t => {
        const titre = ABX.Views.Tabs.titre(t);
        return `<div class="tab${t.key === ui.tab ? " on" : ""}${t.prov ? " prov" : ""}"
          data-k="${F.esc(t.key)}" title="${F.esc(titre)}">
          <span>${ABX.Views.Tabs.ICONES[t.type] || "✉"}</span>
          <span class="tl">${F.esc(titre)}</span>
          ${t.type === "compo" && t.sale ? `<span class="dot">●</span>` : ""}
          <span class="tx" data-close="${F.esc(t.key)}">✕</span></div>`;
      }).join("");
    },
  };
})(window.ABX = window.ABX || {});
