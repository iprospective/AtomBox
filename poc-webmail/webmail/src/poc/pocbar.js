/* LA BARRE DU POC — chargée par le chargeur en session « poc » seulement (D157).
   Elle AJOUTE au produit ce que la maquette a en plus : la barre haute (pages
   Aide, Fonctionnalités, CDC, Feuille de route, interrupteur V0), le bouton de
   remise à zéro, le journal des requêtes et son panneau. Rien de tout cela n'est
   dans index.html : le produit ne connaît pas ces boutons. */
(function (ABX) {
  "use strict";
  const D = ABX.Dom, St = ABX.Store, App = () => ABX.Controllers.App;

  /* ---- le DOM en plus (absent du harnais, qui fabrique les éléments à la demande) */
  if (document.createElement && document.querySelector) {
    const app = document.querySelector(".app"), hdr = document.querySelector("header"), main = document.getElementById("main");
    if (app && hdr && main) {
      const bar = document.createElement("div"); bar.className = "pocbar";
      bar.innerHTML = `<span class="pocb">POC</span>
        <span class="poct">Session simulée — données inventées, aucun serveur.
          <b>Rien de ce que vous ferez ici n'a d'effet ailleurs.</b></span>
        <nav class="pocnav">
          <button data-page="aide">Aide</button>
          <button data-page="features">Fonctionnalités</button>
          <button data-page="cdc">CDC</button>
          <button data-page="roadmap">Feuille de route</button>
          <button class="pocv0" id="pocv0" title="Voir la maquette telle qu'elle sera en V0 (D140b)">V0</button>
        </nav>`;
      app.insertBefore(bar, app.firstChild);
      const sortir = document.getElementById("bsortir");
      const b1 = document.createElement("button"); b1.className = "hbtn dgr"; b1.id = "breset"; b1.title = "Oublier l'état local et repartir des fixtures"; b1.textContent = "⟲";
      const b2 = document.createElement("button"); b2.className = "hbtn on"; b2.id = "bq"; b2.title = "Journal des requêtes"; b2.innerHTML = '⟨/⟩ requêtes <span id="qn">0</span>';
      hdr.insertBefore(b1, sortir); hdr.insertBefore(b2, sortir);
      const q = document.createElement("div"); q.className = "col q"; q.id = "qpanel"; main.appendChild(q);
      main.classList.add("qopen");
    }
  }

  /* ---- les liaisons ---------------------------------------------------------- */
  ABX.Bus.on("querylog:changed", () => App().peindre("q"));
  D.byId("bq").onclick = () => App().setQ(!App().qOuvert());
  document.querySelectorAll(".pocnav [data-page]").forEach(b =>
    b.onclick = () => ABX.Controllers.Pages.ouvrir(b.dataset.page));
  /* La V0 (D140b) : un interrupteur. Tout ce qui demande une base rend vide, rien
     n'est réécrit — on repeint, c'est tout. */
  const bv0 = D.byId("pocv0");
  if (bv0) {
    const etat = () => bv0.classList && bv0.classList.toggle("on", ABX.V0());
    etat();
    bv0.onclick = () => { St.ui.jalon = ABX.V0() ? null : 0; St.save(); etat(); App().peindre(); };
  }
  D.byId("breset").onclick = () => {
    if (!confirm("Oublier l'état local (lectures, archivages, corbeille, brouillons, onglets) "
               + "et repartir des fixtures ?")) return;
    St.oublier(); location.reload();
  };
  /* le journal des requêtes OBSERVE la couche d'accès ; il n'est appelé à la main nulle part */
  if (ABX.QueryLog && ABX.Api.on) ABX.Api.on(a => { if (a.ms > 0) ABX.QueryLog.mesure && ABX.QueryLog.mesure(a); });
  ABX.PocBar = { chargee: true };
})(window.ABX = window.ABX || {});
