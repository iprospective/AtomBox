/* VUE ARBORESCENCE — engendrée depuis les axes (D77), jamais écrite à la main.
   Deux cents fournisseurs ne tiennent dans un panneau latéral qu'avec un filtre,
   un repli par axe et une pagination : c'est la cardinalité qui impose l'écran. */
(function (ABX) {
  "use strict";
  const R = ABX.Registry, F = ABX.Fmt, Fx = ABX.Fixtures, C = ABX.Corpus;
  const PAGE = 12;   // valeurs affichées par axe avant « voir plus »

  ABX.Views = ABX.Views || {};
  ABX.Views.Nav = {
    PAGE,
    render(ui) {
      const f = ui.navq.trim().toLowerCase();
      const noeud = (o, cls, sel) => R.render("nav.node", { o, cls, sel });
      let h = `<div class="navsearch"><input id="navq" placeholder="Filtrer les dossiers…"
         value="${F.esc(ui.navq)}">${ui.navq
           ? `<button class="navx" id="navx" title="Effacer le filtre (Échap)">✕</button>` : ""}</div>`;

      if (!f) {
        h += `<div class="grp">Dossiers</div>`;
        Fx.SPECIAUX.forEach(o => h += noeud(
          { ...o, kind:"special", unread: C.cnt(o.id).u, total: C.cnt(o.id).t },
          "", ui.folder.id === o.id));
        Fx.UTIL.forEach(o => h += noeud(
          { ...o, kind:"user", unread: C.cnt(o.id).u, total: C.cnt(o.id).t },
          "", ui.folder.id === o.id));
      }

      Fx.AXES.forEach(a => {
        const vals = Fx.valeurs[a.id].filter(v => !f || v.label.toLowerCase().includes(f));
        if (f && !vals.length) return;
        const ouvert = ui.ouverts[a.id] || !!f;
        h += `<div class="grp">${F.esc(a.label)}${a.sub ? " · " + a.sub : ""}</div>`;
        h += noeud({ id:"axe:" + a.id, label:"Tous — " + a.label, icon:a.icon,
                     unread: C.cnt("axe:" + a.id).u, total: C.cnt("axe:" + a.id).t,
                     tw: ouvert ? "▾" : "▸", kind:"axe", axe:a.id },
                   "", ui.folder.id === "axe:" + a.id);
        if (!ouvert) return;
        const lim = ui.plus[a.id] ? vals.length : PAGE;
        vals.slice(0, lim).forEach(v => h += noeud(
          { ...v, unread: C.cnt(v.id).u, total: C.cnt(v.id).t,
            icon: a.id === "client" && v.actif ? "🟢" : "•", kind:"virtuel" },
          "child", ui.folder.id === v.id));
        if (vals.length > lim)
          h += `<div class="more" data-more="${a.id}">voir les ${vals.length - lim} autres…</div>`;
      });
      return h;
    },
  };
})(window.ABX = window.ABX || {});
