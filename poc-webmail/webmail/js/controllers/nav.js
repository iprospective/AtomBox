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

      const stop = e => { if (e && e.stopPropagation) e.stopPropagation(); };
      /* Épingler / désépingler (D144) : un réglage par compte, par la même route que
         tout paramètre personnel. L'ordre du groupe est l'ordre d'épinglage. */
      D.on(el, "[data-pin]", "onclick", (n, e) => { stop(e);
        const id = n.dataset.pin, cur = ABX.Api.cache.epingles();
        const suiv = cur.includes(id) ? cur.filter(x => x !== id) : cur.concat([id]);
        ABX.Api.regler("epingles", suiv).then(() => Nav.peindre());
      });
      /* Supprimer un dossier virtuel personnel (D143) : une définition, jamais un
         message — donc pas de confirmation. S'il était ouvert, on revient à la boîte. */
      D.on(el, "[data-delv]", "onclick", (n, e) => { stop(e);
        const id = n.dataset.delv;
        ABX.Api.supprimerDossier(id).then(() => ABX.Api.compteurs()).then(() => {
          if (ui.folder.id === id)
            return ABX.Controllers.List.ouvrir({ id: "inbox", label: "Boîte de réception", kind: "special" });
          Nav.peindre();
        });
      });
      const vnew = el.querySelector("#v_new");
      if (vnew) vnew.onclick = e => { stop(e);
        ui.formVirtuel = { label: "", criteres: [{ axe: ABX.Ref.axes[0].id, val: "" }] }; Nav.peindre(); };
      const form = el.querySelector("#vform");
      if (form) {
        const lire = () => { const fv = ui.formVirtuel; fv.label = D.byId("v_label").value;
          form.querySelectorAll(".v_axe").forEach(s => { fv.criteres[+s.dataset.i].axe = s.value; });
          form.querySelectorAll(".v_val").forEach(s => { fv.criteres[+s.dataset.i].val = s.value; }); };
        form.querySelectorAll(".v_axe").forEach(s => { s.onchange = () => { lire(); Nav.peindre(); }; });
        D.byId("v_plus").onclick = () => { lire(); ui.formVirtuel.criteres.push({ axe: ABX.Ref.axes[0].id, val: "" }); Nav.peindre(); };
        D.byId("v_non").onclick = () => { ui.formVirtuel = null; Nav.peindre(); };
        D.byId("v_ok").onclick = () => { lire(); Nav.creerVirtuel(ui.formVirtuel); };
      }
    },

    /* Créer un dossier virtuel personnel (D143) et l'ouvrir. Sans libellé, le
       libellé est le critère lui-même : « fournisseur = Acme », « famille client ». */
    creerVirtuel(def) {
      const criteres = ((def && def.criteres) || []).map(c => ({ axe: c.axe, val: (c.val || "").trim() }))
        .filter(c => c.axe).map(c => c.val ? c : { axe: c.axe });
      if (!criteres.length) return Promise.resolve(null);
      const label = ((def && def.label) || "").trim()
        || criteres.map(c => c.val ? c.axe + " = " + c.val : "famille " + c.axe).join(" · ");
      return ABX.Api.creerDossier({ label, criteres }).then(r => {
        St.ui.formVirtuel = null;
        return ABX.Api.compteurs().then(() => {
          ABX.Controllers.List.ouvrir({ id: r.dossier.id, label: r.dossier.label, kind: "perso" });
          return r.dossier; });
      });
    },

    /* Les compteurs de toute l'arborescence : une requête, pas une par dossier (D078). */
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
