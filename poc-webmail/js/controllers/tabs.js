/* CONTRÔLEUR ONGLETS — plusieurs messages ouverts, conservés d'une session à l'autre. */
(function (ABX) {
  "use strict";
  const D = ABX.Dom, St = ABX.Store, C = ABX.Corpus;

  const Tabs = {
    peindre() {
      const ui = St.ui;
      const el = D.paint("tabs", ABX.Views.Tabs.render(ui));
      D.on(el, ".tab", "onclick", (d, e) => {
        const x = D.closest(e, "data-close");
        if (x) { e.stopPropagation(); return Tabs.fermer(x.dataset.close); }
        const t = ui.tabs.find(y => y.key === d.dataset.k);
        Tabs.ouvrir(t.type === "msg" ? { type:"msg", id:t.id } : t, false);
      });
      D.on(el, ".tab", "onauxclick", (d, e) => {
        if (e.button === 1) { e.preventDefault(); Tabs.fermer(d.dataset.k); }
      });
    },

    /* prov = onglet provisoire : remplacé par le clic suivant, épinglé au double-clic. */
    ouvrir(spec, prov) {
      const ui = St.ui;
      const key = spec.type === "msg"   ? "m:" + spec.id
                : spec.type === "admin" ? "admin"
                : spec.type === "pj"    ? "pj"
                : spec.type === "page"  ? "page"
                : (spec.key || "c:" + (++St.seq));
      let t = ui.tabs.find(x => x.key === key);
      if (!t) {
        if (prov) { const i = ui.tabs.findIndex(x => x.prov); if (i >= 0) ui.tabs.splice(i, 1); }
        t = { ...spec, key, prov: !!prov };
        ui.tabs.push(t);
      } else {
        /* Un onglet unique (admin, pièces jointes) est RÉUTILISÉ : le rouvrir sur
           un autre volet doit changer le volet, pas empiler un second onglet. */
        if (spec.type !== "msg") Object.assign(t, spec, { key });
        if (!prov) t.prov = false;
      }

      const avant = ui.tab;
      ui.tab = key;

      if (spec.type === "msg") {
        const m = C.par(spec.id);
        const dejaOuvert = !!t.vu;
        if (m && !dejaOuvert) { t.vu = true; ABX.Traces.ouvrirMessage(m, m.lu); }
        else if (m) ABX.log({ label:"Revenir sur l'onglet « " + m.subject + " »", etapes:[
          { t:"ui", label:"clic sur l'onglet", detail:"views/tabs.js → Controllers.Tabs.ouvrir" },
          { t:"cache", label:"aucune requête",
            detail:"le message est déjà en mémoire du client",
            index:"c'est tout l'intérêt d'un onglet — à condition d'avoir chargé le corps AVEC " +
                  "le message, une requête et non deux" },
          { t:"render", label:"Views.Message, sur les mêmes données",
            detail:"Controllers.App.peindre('detail')" },
        ]});
        if (m && !m.lu) ABX.MessageService.lire(m, true);    // émet, donc repeint
        else { St.save(); ABX.Controllers.App.peindre("tabs");
               ABX.Controllers.App.peindre("list"); ABX.Controllers.App.peindre("detail"); }
      } else {
        St.save();
        ABX.Controllers.App.peindre("tabs");
        ABX.Controllers.App.peindre("detail");
      }
      if (ABX.Controllers.App.MOBILE()) ABX.Controllers.App.setVue("detail");
    },

    fermer(key) {
      const ui = St.ui;
      const i = ui.tabs.findIndex(t => t.key === key);
      if (i < 0) return;
      ui.tabs.splice(i, 1);
      if (ui.tab === key)
        ui.tab = ui.tabs.length ? ui.tabs[Math.min(i, ui.tabs.length - 1)].key : null;
      St.save();
      ABX.Controllers.App.peindre("tabs");
      ABX.Controllers.App.peindre("list");
      ABX.Controllers.App.peindre("detail");
    },

    /* Restauration de session : une requête pour tous les onglets, pas une par onglet. */
    logRestauration(n) {
      if (n < 2) return;
      ABX.log("Rouvrir " + n + " onglets",
`SELECT m.*, r.lu_le FROM message m JOIN rattachement r USING (message_id)
 WHERE m.message_id = ANY (:ids) AND r.compte_id = :moi;`,
        "UNE requête pour tous les onglets — sinon la restauration de session coûte N " +
        "allers-retours au démarrage, le moment où l'on peut le moins se le permettre");
    },
  };

  ABX.Controllers = ABX.Controllers || {};
  ABX.Controllers.Tabs = Tabs;
})(window.ABX = window.ABX || {});
