/* VUE DE LA TRACE — la cascade d'un geste, du clic au rendu.

   Les étapes sont affichées dans l'ordre d'exécution, avec une barre de côté qui
   change au passage du réseau : ce qui est à gauche tourne dans le navigateur, ce
   qui est à droite tournera sur le serveur qu'il reste à écrire. */
(function (ABX) {
  "use strict";
  const F = ABX.Fmt, St = ABX.Store, QL = ABX.QueryLog;

  /* Les étapes dont le détail est du code, et non une phrase. */
  const CODE = { http:1, json:1, sql:1, blob:1, event:1 };

  function etape(e) {
    const T = QL.TYPES[e.t] || QL.TYPES.note;
    return `<li class="step ${e.t}${e.warn ? " w" : ""}">
      <span class="pic" title="${T.nom}">${T.ic}</span>
      <div class="body">
        ${e.label ? `<div class="et">${F.esc(e.label)}</div>` : ""}
        ${e.detail ? (CODE[e.t]
          ? `<code>${F.esc(e.detail)}</code>`
          : `<div class="det">${F.esc(e.detail)}</div>`) : ""}
        ${e.index ? `<div class="idx${e.warn ? " w" : ""}">${
          e.warn ? "⚠ " : "↳ "}${F.esc(e.index)}</div>` : ""}
      </div></li>`;
  }

  /* Un trait au moment où l'on quitte le navigateur, un autre au retour. */
  function cascade(etapes) {
    let cote = null, h = "";
    etapes.forEach(e => {
      const c = (QL.TYPES[e.t] || QL.TYPES.note).cote;
      if (c === "r" && cote !== "r") h += `<li class="fr">réseau — aller-retour</li>`;
      if (c === "s" && cote === "r") h += `<li class="fr srv">serveur</li>`;
      if (c === "c" && (cote === "s" || cote === "r")) h += `<li class="fr">retour navigateur</li>`;
      cote = c;
      h += etape(e);
    });
    return `<ol class="casc">${h}</ol>`;
  }

  ABX.Views = ABX.Views || {};
  ABX.Views.QueryLog = {
    cascade,
    render(entrees) {
      const nMut = Object.keys(St.ratt).length;
      return `<div class="qh"><b>Trace des gestes</b>
          <button class="hbtn" id="qclr">vider</button></div>
        <div class="note">Le livrable du POC, au-delà des écrans (D79) : chaque clic déroule
          la <b>cascade complète</b> — appel d'API, route, contrôleur, service, requêtes,
          magasin d'octets, JSON renvoyé, rendu. C'est cette succession qui décrit ce qu'il
          faudra écrire, et le JSON qui fixe le contrat d'API.<br>
          <b>Hypothèse de travail</b> : une API REST par ressource. <b>Q07 n'est pas
          tranchée</b> — un point d'entrée unique donnerait une autre cascade, et c'est
          justement ce que cette trace permet de comparer.<br>
          <b>État local</b> : ${nMut} rattachement(s) modifié(s), ${St.crees.length} message(s)
          écrit(s), ${St.tailleKo()} ko en localStorage.</div>
        ${entrees.map(i => `<div class="qi${i.warn ? " w" : ""}">
          <div class="lbl">${i.t.toTimeString().slice(0, 8)} — ${F.esc(i.label)}
            <span class="nsteps">${i.etapes.length} étapes</span></div>
          ${cascade(i.etapes)}
        </div>`).join("")}`;
    },
  };
})(window.ABX = window.ABX || {});
