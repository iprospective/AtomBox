/* CONTRÔLEUR COMPOSITION. La saisie va dans l'onglet à chaque frappe, sans
   repeindre : sinon le champ perdrait le focus à chaque caractère. */
(function (ABX) {
  "use strict";
  const D = ABX.Dom, St = ABX.Store, Svc = ABX.ComposeService;
  const App = () => ABX.Controllers.App, Tabs = () => ABX.Controllers.Tabs;

  const Compose = {
    demarrer(mode, m) {
      const data = Svc.preparer(mode, m);
      Tabs().ouvrir({ type:"compo", data }, false);
      if (App().MOBILE()) App().setVue("detail");
    },

    /* Un brouillon enregistré se rouvre dans l'état où il a été laissé. */
    rouvrir(m) {
      Tabs().ouvrir({ type:"compo", data: m.compo, brouillon: m.id }, false);
      if (App().MOBILE()) App().setVue("detail");
    },

    peindre(t) {
      const el = D.paint("detail", ABX.Views.Compose.render(t, St.ui));
      App().bindRetour(el);
      const d = t.data;

      const lie = (sel, k) => { const n = el.querySelector(sel); n.oninput = () => {
        d[k] = n.value; t.sale = true;
        if (k === "sujet") ABX.Controllers.App.peindre("tabs"); }; };
      lie("#f_a", "a"); lie("#f_cc", "cc"); lie("#f_sujet", "sujet"); lie("#f_corps", "corps");

      el.querySelector("#f_de").onchange = e => { d.de = e.target.value; t.sale = true; };
      const ref = el.querySelector("#f_ref");
      if (ref) ref.onchange = e => { d.ref = e.target.checked; t.sale = true; };

      el.querySelector("#c_pj").onclick  = () => { Svc.joindre(d); t.sale = true;
                                                   App().peindre("detail"); };
      el.querySelector("#c_del").onclick = () => Tabs().fermer(t.key);
      el.querySelector("#c_br").onclick  = () => Compose.finir(t, false);
      el.querySelector("#c_env").onclick = () => Compose.finir(t, true);
    },

    finir(t, envoyer) {
      const cree = Svc.enregistrer(t.data, t.brouillon, envoyer);
      if (!cree) return alert("Aucun destinataire.");
      /* on attend la réponse de la couche d'accès avant d'ouvrir l'onglet du
         message créé : en prod c'est le POST qui donne l'identifiant (D141) */
      return cree.then(m => {
        Tabs().fermer(t.key);
        if (envoyer) Tabs().ouvrir({ type:"msg", id:m.id }, false);
        else App().peindre("all");
      });
    },
  };

  ABX.Controllers = ABX.Controllers || {};
  ABX.Controllers.Compose = Compose;
})(window.ABX = window.ABX || {});
