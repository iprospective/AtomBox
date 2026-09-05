/* CONTRÔLEUR D'APPLICATION — ce qui est repeint, et quand.
   Les services n'appellent jamais une vue : ils émettent sur le bus, et c'est
   ici qu'on décide de la conséquence à l'écran. */
(function (ABX) {
  "use strict";
  const D = ABX.Dom, St = ABX.Store;

  const MOBILE = () => matchMedia("(max-width:760px)").matches;
  const TABLET = () => matchMedia("(max-width:980px)").matches;

  const App = {
    MOBILE, TABLET,

    /* Rend la promesse de ce qui arrive par la couche d'accès (la liste, D141) :
       l'amorçage et le harnais peuvent attendre que tout soit peint. */
    peindre(quoi) {
      const q = quoi || "all";
      let attente = Promise.resolve();
      if (q === "all" || q === "tabs")   ABX.Controllers.Tabs.peindre();
      if (q === "all" || q === "nav")    ABX.Controllers.Nav.peindre();
      if (q === "all" || q === "list")   attente = ABX.Controllers.List.charger();
      if (q === "all" || q === "detail") App.peindreDetail();
      if ((q === "all" || q === "q") && ABX.Views.QueryLog) App.peindreQ();
      return attente;
    },

    /* Le panneau de détail affiche l'onglet actif : un message, ou une composition. */
    peindreDetail() {
      const ui = St.ui, t = ui.tabs.find(x => x.key === ui.tab);
      if (!t) return void D.paint("detail", `<div class="empty">Aucun onglet ouvert.<br><br>
        <small>Clique un message pour l'ouvrir, double-clique pour l'épingler.<br>
        Chaque geste alimente le journal des requêtes : c'est lui qui dictera les index.</small></div>`);
      if (t.type === "compo") return ABX.Controllers.Compose.peindre(t);
      if (t.type === "admin") return ABX.Controllers.Admin.peindre(t);
      if (t.type === "pj")    return ABX.Controllers.Admin.peindrePJ();
      if (t.type === "page")  return ABX.Controllers.Pages.peindre(t);
      return ABX.Controllers.Message.peindre(t);
    },

    peindreQ() {
      const el = D.paint("qpanel", ABX.Views.QueryLog.render(ABX.QueryLog.entrees));
      D.byId("qn").textContent = ABX.QueryLog.entrees.length;
      el.querySelector("#qclr").onclick = () => ABX.QueryLog.vider();
    },

    /* ---- navigation responsive : tiroirs et vues ------------------------- */
    setVue(v) {
      const m = D.byId("main");
      m.dataset.vue = v;
      if (v !== "nav") App.fermerNav();
      const c = D.byId(v === "detail" ? "detail" : "list");
      if (c) c.scrollTop = 0;
    },
    ouvrirNav() { D.byId("main").classList.add("navopen"); D.byId("scrim").classList.add("on"); },
    fermerNav() { D.byId("main").classList.remove("navopen"); D.byId("scrim").classList.remove("on"); },

    bindRetour(root) {
      root.querySelectorAll(".backbar [data-vue]").forEach(b => b.onclick = () => {
        if (b.dataset.vue === "nav" && TABLET() && !MOBILE()) return App.ouvrirNav();
        App.setVue(b.dataset.vue);
      });
    },

    setQ(on) {
      D.byId("main").classList.toggle("qopen", on);
      D.byId("bq").classList.toggle("on", on);
      try { localStorage.setItem("abx.q", on ? "1" : "0"); } catch (e) {}
    },
    qOuvert: () => D.byId("main").classList.contains("qopen"),
  };

  ABX.Controllers = ABX.Controllers || {};
  ABX.Controllers.App = App;
})(window.ABX = window.ABX || {});
