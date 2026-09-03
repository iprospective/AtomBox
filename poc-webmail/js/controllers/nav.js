/* CONTRÔLEUR ARBORESCENCE. */
(function (ABX) {
  "use strict";
  const D = ABX.Dom, St = ABX.Store, App = () => ABX.Controllers.App;

  const Nav = {
    peindre() {
      const ui = St.ui;
      const el = D.paint("nav", ABX.Views.Nav.render(ui));
      const inp = el.querySelector("#navq");

      const viderFiltre = () => { ui.navq = ""; Nav.peindre(); D.byId("navq").focus(); };
      const croix = el.querySelector("#navx");
      if (croix) croix.onclick = viderFiltre;

      inp.onkeydown = e => { if (e.key === "Escape" && ui.navq) {
        e.stopPropagation();     // sinon l'Échap global fermerait le panneau des requêtes
        viderFiltre(); } };

      inp.oninput = e => {
        ui.navq = e.target.value;
        const pos = e.target.selectionStart;
        Nav.peindre();
        const i2 = D.byId("navq"); i2.focus(); i2.setSelectionRange(pos, pos);
        if (ui.navq.length === 1) ABX.log("Recherche dans l'arborescence",
`SELECT axe_id, valeur, count(*) FILTER (WHERE r.lu_le IS NULL)
  FROM tag t JOIN comm_tag mt USING (tag_id) JOIN rattachement r USING (comm_id)
 WHERE r.compte_id = :moi AND t.valeur ILIKE :q || '%'
 GROUP BY axe_id, valeur LIMIT 50;`,
          "index (valeur text_pattern_ops) — sinon balayage de tous les tags", true);
      };

      /* Réordonner (D135). Les boutons sont DANS le nœud : sans le stopPropagation,
         monter un axe l'ouvrirait aussi. */
      D.on(el, ".axop", "onclick", (n, e) => {
        if (e && e.stopPropagation) e.stopPropagation();
        const Fx = ABX.Fixtures;
        if (n.dataset.tri) {
          ui.triAxe[n.dataset.tri] = ui.triAxe[n.dataset.tri] === "alpha" ? "recent" : "alpha";
        } else {
          const ordre = ui.ordreAxes || Fx.AXES.map(a => a.id);
          const i = ordre.indexOf(n.dataset.axe);
          const j = n.dataset.mv === "up" ? i - 1 : i + 1;
          if (i < 0 || j < 0 || j >= ordre.length) return;
          ordre[i] = ordre[j]; ordre[j] = n.dataset.axe;
          ui.ordreAxes = ordre;
        }
        ABX.Store.save();
        Nav.peindre();
      });

      D.on(el, ".node", "onclick", n => {
        const id = n.dataset.id;
        if (n.dataset.kind === "axe") {
          const a = n.dataset.axe;
          if (ui.folder.id === id) { ui.ouverts[a] = !ui.ouverts[a]; return Nav.peindre(); }
          ui.ouverts[a] = true;
        }
        ABX.Controllers.List.ouvrir({ id, label: n.dataset.label,
                                      kind: n.dataset.kind, axe: n.dataset.axe });
      });

      D.on(el, ".more", "onclick", n => {
        ui.plus[n.dataset.more] = true;
        Nav.peindre();
        ABX.log("Charger le reste d'un axe",
`SELECT valeur, count(*) FROM tag t JOIN comm_tag mt USING (tag_id)
  JOIN rattachement r USING (comm_id)
 WHERE r.compte_id = :moi AND t.axe_id = :axe
 GROUP BY valeur ORDER BY max(r.recu_le) DESC OFFSET :n LIMIT 200;`,
          "index (axe_id, valeur) — pagination de l'arborescence elle-même");
      });
    },

    /* Les compteurs de toute l'arborescence : une requête, pas une par dossier (D78). */
    logCompteurs() {
      ABX.log("Compteurs de non-lus de TOUTE l'arborescence",
`-- une seule requête pour les ~300 branches, pas une par dossier
SELECT t.axe_id, t.valeur, count(*) AS non_lus
  FROM rattachement r
  JOIN comm_tag mt ON mt.comm_id = r.comm_id
  JOIN tag t          ON t.tag_id      = mt.tag_id
 WHERE r.compte_id = :moi AND r.lu_le IS NULL AND r.sorti_le IS NULL
 GROUP BY t.axe_id, t.valeur;`,
        "index (compte_id, lu_le) partiel + (tag_id, comm_id) — un seul parcours groupé");
    },
  };

  ABX.Controllers = ABX.Controllers || {};
  ABX.Controllers.Nav = Nav;
})(window.ABX = window.ABX || {});
