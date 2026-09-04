/* CONTRÔLEUR DES PAGES — aide, fonctionnalités, CDC, feuille de route.
   Un seul onglet, réutilisé : ces pages se lisent, elles ne s'empilent pas. */
(function (ABX) {
  "use strict";
  const D = ABX.Dom, St = ABX.Store;

  const Pages = {
    ouvrir(page) {
      St.ui.page = page || St.ui.page || "aide";
      ABX.Controllers.Tabs.ouvrir({ type:"page", page: St.ui.page }, false);
    },
    peindre(t) {
      const el = D.paint("detail", ABX.Views.Pages.render(t.page));
      ABX.Controllers.App.bindRetour(el);
      D.on(el, ".chip[data-page]", "onclick", c => {
        t.page = St.ui.page = c.dataset.page; St.save(); Pages.peindre(t);
      });
      /* Navigation DANS le CDC : un chapitre, ou une section (décision, question,
         conseil). Un identifiant cliqué depuis n'importe quelle page mène à la
         page CDC — c'est ce qui rend le texte consultable d'où qu'on soit. */
      D.on(el, ".cdc-lien", "onclick", (a, e) => {
        if (e && e.preventDefault) e.preventDefault();
        St.ui.cdc = St.ui.cdc || {};
        if ("sec" in a.dataset) { St.ui.cdc.sec = a.dataset.sec || null; if (!a.dataset.sec) St.ui.cdc.chap = St.ui.cdc.chap || null; }
        if ("chap" in a.dataset) { St.ui.cdc.chap = a.dataset.chap || null; St.ui.cdc.sec = null; St.ui.cdc.modele = null; }
        if ("modele" in a.dataset) { St.ui.cdc.modele = a.dataset.modele || null; St.ui.cdc.sec = null; St.ui.cdc.chap = null; }
        t.page = St.ui.page = "cdc"; Pages.peindre(t);
        const zone = el.querySelector && el.querySelector(".lecture");
        if (zone && zone.scrollIntoView) zone.scrollIntoView({ block: "start" });
      });
      /* Tri des fonctionnalités : un clic trie, un second inverse. Persisté. */
      D.on(el, "th[data-trif]", "onclick", th => {
        const k = th.dataset.trif;
        if (St.ui.triFeat === k) St.ui.triFeatDesc = !St.ui.triFeatDesc;
        else { St.ui.triFeat = k; St.ui.triFeatDesc = false; }
        St.save(); Pages.peindre(t);
      });
      D.on(el, ".chip[data-dict]", "onclick", c => {
        St.ui.dictTable = c.dataset.dict; Pages.peindre(t);
      });
    },
  };

  ABX.Controllers = ABX.Controllers || {};
  ABX.Controllers.Pages = Pages;
})(window.ABX = window.ABX || {});
