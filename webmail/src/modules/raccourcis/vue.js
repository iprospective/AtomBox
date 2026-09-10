/* L'AIDE DES RACCOURCIS — engendrée de la table, jamais retapée (F111). */
(function (ABX) {
  "use strict";
  const R = ABX.Registry, F = ABX.Fmt;
  const TITRES = { global: "Partout", liste: "Dans la liste", message: "Sur le message ouvert" };

  R.define("raccourcis.aide", ({ table }) => {
    const groupes = ["global", "liste", "message"].map(c => {
      const l = table.filter(r => r.contexte === c);
      if (!l.length) return "";
      return `<section><h4>${F.esc(TITRES[c] || c)}</h4>` +
        l.map(r => `<div class="racl"><kbd>${F.esc(r.touche === "Escape" ? "Échap" : r.touche)}</kbd>` +
                   `<span>${F.esc(r.libelle)}</span></div>`).join("") + `</section>`;
    }).join("");
    return `<div class="racbox" role="dialog" aria-label="Raccourcis clavier">
        <div class="rachead"><b>Raccourcis clavier</b>
          <button id="rac_fermer" class="btn" type="button">Fermer</button></div>
        ${groupes}
        <p class="rachint">Les raccourcis se taisent pendant une saisie, et laissent au navigateur
          tout ce qui porte Ctrl, Cmd ou Alt.</p>
      </div>`;
  });

  ABX.Views = ABX.Views || {};
  ABX.Views.Raccourcis = { render: table => R.render("raccourcis.aide", { table }) };
})(window.ABX = window.ABX || {});
