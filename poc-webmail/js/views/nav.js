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

      /* V0 (D140b) : les dossiers IMAP sont ingérés comme tags d'origine et
         affichés comme dossiers — aucun axe métier, aucune arborescence engendrée
         encore. Ce qui reste est ce que Roundcube et Thunderbird montrent. */
      if (ABX.V0())
        return h + `<div class="hint" style="padding:8px 10px">V0 — les dossiers IMAP, ingérés
          comme tags d'origine et affichés tels quels ; synchronisés avec IMAP (D140b, D46)</div>`;
      /* L'ordre des axes appartient à l'utilisateur (D135). Un axe ajouté depuis
         son dernier réglage se range à la fin plutôt que de disparaître. */
      const ordre = ui.ordreAxes || [];
      const axes = Fx.AXES.slice().sort((x, y) => {
        const i = ordre.indexOf(x.id), j = ordre.indexOf(y.id);
        return (i < 0 ? 999 : i) - (j < 0 ? 999 : j);
      });
      axes.forEach((a, rang) => {
        let vals = Fx.valeurs[a.id].filter(v => !f || v.label.toLowerCase().includes(f));
        if (f && !vals.length) return;
        /* Deux tris seulement, et le manuel n'en fait pas partie : ordonner deux
           cents fournisseurs à la main n'est pas une fonction, c'est une corvée. */
        if (ui.triAxe[a.id] === "alpha")
          vals = vals.slice().sort((x, y) => x.label.localeCompare(y.label));
        const ouvert = ui.ouverts[a.id] || !!f;
        /* Plus de titre de groupe : il répétait le nom de l'axe juste au-dessus
           d'un nœud « Tous — <axe> ». Le nœud porte le nom, un point c'est tout. */
        h += noeud({ id:"axe:" + a.id, label: a.label + (a.sub ? " · " + a.sub : ""),
                     icon:a.icon,
                     unread: C.cnt("axe:" + a.id).u, total: C.cnt("axe:" + a.id).t,
                     tw: ouvert ? "▾" : "▸", kind:"axe", axe:a.id,
                     rang, dernier: rang === axes.length - 1,
                     triAxe: ui.triAxe[a.id] || "recent" },
                   "axe-tete", ui.folder.id === "axe:" + a.id);
        if (!ouvert) return;
        const lim = ui.plus[a.id] ? vals.length : PAGE;
        vals.slice(0, lim).forEach(v => h += noeud(
          { ...v, unread: C.cnt(v.id).u, total: C.cnt(v.id).t,
            icon: a.id === "client" && v.actif ? "🟢" : "•",
            /* Un axe dérivé ne se sélectionne pas par chemin : ses dossiers sont
               un prédicat sur le corpus, pas un rangement (D133). */
            kind: a.derive ? "abo" : "virtuel" },
          "child", ui.folder.id === v.id));
        if (vals.length > lim)
          h += `<div class="more" data-more="${a.id}">voir les ${vals.length - lim} autres…</div>`;
      });
      return h;
    },
  };
})(window.ABX = window.ABX || {});
