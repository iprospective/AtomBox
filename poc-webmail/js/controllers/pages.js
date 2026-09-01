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
    },
  };

  ABX.Controllers = ABX.Controllers || {};
  ABX.Controllers.Pages = Pages;
})(window.ABX = window.ABX || {});
