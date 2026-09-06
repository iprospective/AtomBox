/* VUE ARBORESCENCE — engendrée depuis les axes (D077), jamais écrite à la main.
   Deux cents fournisseurs ne tiennent dans un panneau latéral qu'avec un filtre,
   un repli par axe et une pagination : c'est la cardinalité qui impose l'écran.

   Avant les axes, trois groupes : les ÉPINGLÉS (D144) en tête, dans l'ordre où
   l'utilisateur les a épinglés ; les DOSSIERS (spéciaux, puis les siens) ; et
   MES DOSSIERS — ses dossiers virtuels personnels (D143), des filtres sans action. */
(function (ABX) {
  "use strict";
  const R = ABX.Registry, F = ABX.Fmt;
  const PAGE = 12;   // valeurs affichées par axe avant « voir plus »

  ABX.Views = ABX.Views || {};
  ABX.Views.Nav = {
    PAGE,
    render(ui) {
      const f = ui.navq.trim().toLowerCase();
      const Ref = ABX.Ref, Api = ABX.Api, v0 = ABX.V0();
      const cptr = id => ({ unread: Api.cache.compteur(id).u, total: Api.cache.compteur(id).t });
      const epingles = v0 ? [] : Api.cache.epingles();
      const noeud = (o, cls, sel) =>
        R.render("nav.node", { o: { ...o, epingle: epingles.includes(o.id) }, cls, sel });
      let h = `<div class="navsearch"><input id="navq" placeholder="Filtrer les dossiers…"
         value="${F.esc(ui.navq)}">${ui.navq
           ? `<button class="navx" id="navx" title="Effacer le filtre (Échap)">✕</button>` : ""}</div>`;

      /* Les épinglés (D144) : le dossier ne bouge pas, il est AUSSI en haut. Une
         épingle vers un dossier disparu est ignorée, pas affichée. */
      if (!f && epingles.length) {
        h += `<div class="grp">Épinglés</div>`;
        epingles.map(id => ABX.Views.Nav.decrire(id)).filter(Boolean)
          .forEach(o => h += noeud({ ...o, ...cptr(o.id) }, "pin", ui.folder.id === o.id));
        if (epingles.includes(ui.folder.id)) h += R.contexte("nav.epingle", {});
      }

      if (!f) {
        h += `<div class="grp">Dossiers</div>`;
        Ref.speciaux.forEach(o => h += noeud({ ...o, kind:"special", ...cptr(o.id) }, "", ui.folder.id === o.id));
        Ref.util.forEach(o => h += noeud({ ...o, kind:"user", ...cptr(o.id) }, "", ui.folder.id === o.id));
      }

      /* V0 (D140b) : les dossiers IMAP sont ingérés comme tags d'origine et
         affichés comme dossiers — aucun axe métier, aucune arborescence engendrée
         encore. Ce qui reste est ce que Roundcube et Thunderbird montrent. */
      if (v0) return h + R.contexte("nav.v0", {});

      /* Mes dossiers (D143) : des filtres sans action, créés depuis un tag ou
         assemblés ici — filtrables par leur nom comme les valeurs d'un axe. */
      const virtuels = Api.cache.virtuels().filter(v => !f || v.label.toLowerCase().includes(f));
      if (!f || virtuels.length) {
        h += `<div class="grp">Mes dossiers${f ? "" : ` <button class="axop" id="v_new"
          title="Nouveau dossier virtuel : des tags, une famille de tags, ou les deux">+</button>`}</div>`;
        virtuels.forEach(v => h += noeud({ ...v, kind:"perso", icon:"◈", ...cptr(v.id) }, "", ui.folder.id === v.id));
        if (ui.formVirtuel && !f) h += R.render("nav.virtuel.form", { form: ui.formVirtuel });
      }

      /* L'ordre des axes appartient à l'utilisateur (D135). Un axe ajouté depuis
         son dernier réglage se range à la fin plutôt que de disparaître. */
      const ordre = ui.ordreAxes || [];
      const axes = Ref.axes.slice().sort((x, y) => {
        const i = ordre.indexOf(x.id), j = ordre.indexOf(y.id);
        return (i < 0 ? 999 : i) - (j < 0 ? 999 : j);
      });
      axes.forEach((a, rang) => {
        let vals = Ref.valeurs[a.id].filter(v => !f || v.label.toLowerCase().includes(f));
        if (f && !vals.length) return;
        /* Deux tris seulement, et le manuel n'en fait pas partie : ordonner deux
           cents fournisseurs à la main n'est pas une fonction, c'est une corvée. */
        if (ui.triAxe[a.id] === "alpha")
          vals = vals.slice().sort((x, y) => x.label.localeCompare(y.label));
        const ouvert = ui.ouverts[a.id] || !!f;
        /* Plus de titre de groupe : il répétait le nom de l'axe juste au-dessus
           d'un nœud « Tous — <axe> ». Le nœud porte le nom, un point c'est tout. */
        h += noeud({ id:"axe:" + a.id, label: a.label + (a.sub ? " · " + a.sub : ""),
                     icon:a.icon, ...cptr("axe:" + a.id),
                     tw: ouvert ? "▾" : "▸", kind:"axe", axe:a.id,
                     rang, dernier: rang === axes.length - 1,
                     triAxe: ui.triAxe[a.id] || "recent" },
                   "axe-tete", ui.folder.id === "axe:" + a.id);
        if (!ouvert) return;
        const lim = ui.plus[a.id] ? vals.length : PAGE;
        vals.slice(0, lim).forEach(v => h += noeud(
          { ...v, ...cptr(v.id),
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

    /* Retrouver un nœud par son identifiant, quel que soit son groupe : c'est ce
       qui permet d'épingler n'importe quoi (D144) sans dupliquer la définition. */
    decrire(id) {
      const Ref = ABX.Ref;
      let o = Ref.speciaux.find(x => x.id === id); if (o) return { ...o, kind:"special" };
      o = Ref.util.find(x => x.id === id);          if (o) return { ...o, kind:"user" };
      o = ABX.Api.cache.virtuels().find(x => x.id === id); if (o) return { ...o, kind:"perso", icon:"◈" };
      if (id.startsWith("axe:")) {
        const a = Ref.axes.find(x => "axe:" + x.id === id);
        return a ? { id, label: a.label, icon: a.icon, kind:"axe", axe: a.id } : null;
      }
      for (const a of Ref.axes) {
        o = (Ref.valeurs[a.id] || []).find(x => x.id === id);
        if (o) return { ...o, kind: a.derive ? "abo" : "virtuel", axe: a.id, icon: "•" };
      }
      return null;
    },
  };
})(window.ABX = window.ABX || {});
