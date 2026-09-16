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
      Tabs().ouvrir({ type:"compo", data: m.composition, brouillon: m.id }, false);
      if (App().MOBILE()) App().setVue("detail");
    },

    peindre(t) {
      const el = D.paint("detail", ABX.Views.Compose.render(t, St.ui));
      App().bindRetour(el);
      const d = t.data;

      const lie = (sel, k) => { const n = D.byId(sel.replace("#", "")); if (!n) return; n.oninput = () => {
        d[k] = n.value; t.sale = true;
        if (k === "sujet") ABX.Controllers.App.peindre("tabs"); }; };
      lie("#f_a", "a"); lie("#f_cc", "cc"); lie("#f_sujet", "sujet"); lie("#f_corps", "corps");

      D.byId("f_de").onchange = e => { d.de = e.target.value; t.sale = true; };
      /* Le bloc source a besoin du message COMPLET (corps, pièces) : la liste ne le porte pas, et
         un brouillon de transfert rouvert demain n'a plus rien en cache. On le charge une fois —
         `t._src` interdit d'y revenir en boucle si le message a été purgé (Q030). */
      if (d.mode === "tr" && d.src && !t._src) {
        const src = ABX.Api.cache.message(d.src);
        if (!src || !src._complet) {
          t._src = true;
          Promise.resolve(ABX.Api.message(d.src)).then(() => App().peindre("detail"), () => {});
        }
      }

      D.byId("c_pj").onclick  = () => { Svc.joindre(d); t.sale = true;
                                                   App().peindre("detail"); };
      D.byId("c_del").onclick = () => Tabs().fermer(t.key);
      D.byId("c_br").onclick  = () => Compose.finir(t, false);
      D.byId("c_env").onclick = () => Compose.finir(t, true);
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
