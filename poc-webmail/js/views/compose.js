/* VUE COMPOSITION — nouveau message, réponse, transfert.
   Chaque écran affiche la décision qui le rend particulier plutôt que de la
   subir en silence : l'identité d'envoi (Q026), le mode de transfert (D058/D066),
   la livraison interne hors SMTP (D012). */
(function (ABX) {
  "use strict";
  const F = ABX.Fmt, Fx = ABX.Fixtures, C = ABX.Corpus;

  ABX.Views = ABX.Views || {};
  ABX.Views.Compose = {
    render(t, ui) {
      const d = t.data, src = d.src ? C.par(d.src) : null;
      const titre = d.mode === "tr" ? "Transférer"
                  : d.mode === "new" ? "Nouveau message" : "Répondre";
      return `
        <div class="backbar"><button data-vue="liste">‹ ${F.esc(ui.folder.label)}</button></div>
        <div class="dhead"><div class="dsubj">${titre}</div>
          <div class="dmeta">${d.mode === "new" ? "message sortant"
            : "en " + (d.mode === "tr" ? "transfert" : "réponse") + " de « " +
              F.esc(src ? src.subject : "message supprimé") + " »"}</div></div>
        <div class="compo">
          <div class="frow"><label>De</label><select id="f_de">${Fx.MOI.boites.map(b =>
            `<option value="${F.esc(b.adresse)}"${d.de === b.adresse ? " selected" : ""}>${
              F.esc(b.adresse)} — ${F.esc(b.label)}</option>`).join("")}</select></div>
          ${d.mode !== "new" && d.de !== Fx.MOI.boites[0].adresse
            ? `<div class="hint">↳ présélectionné sur la boîte qui a <b>reçu</b> le message —
                 répondre depuis une autre identité ampute le fil pour les collègues qui partagent
                 la boîte (Q026).</div>` : ""}
          <div class="frow"><label>À</label><input id="f_a" value="${F.esc(d.a)}"
            placeholder="destinataires, séparés par des virgules"></div>
          <div class="frow"><label>Cc</label><input id="f_cc" value="${F.esc(d.cc)}"></div>
          <div class="frow"><label>Sujet</label><input id="f_sujet" value="${F.esc(d.sujet)}"></div>
          <textarea id="f_corps">${F.esc(d.corps)}</textarea>
          ${d.mode === "tr" && src ? `<div class="lien">
            <label class="chk"><input type="checkbox" id="f_ref"${d.ref ? " checked" : ""}>
              <span>Transférer <b>par référence</b> — destinataires internes</span></label>
            <div class="hint" style="margin-top:5px">Coché : aucune copie. Le message reçu porte un
              <b>lien</b> vers l'original et une ACL de lecture (D058/D067) — le fil reste unique, et
              une purge de l'original laissera un lien mort assumé (Q030).<br>
              Décoché : l'original est <b>encapsulé</b> en <code>message/rfc822</code>, donc
              matérialisé — seule forme envoyable à l'extérieur, et dédupliquée comme un
              message (D066).</div></div>` : ""}
          ${d.pjs.length ? `<div class="hint">📎 ${d.pjs.length} pièce(s) jointe(s) :
            ${d.pjs.map(p => F.esc(p.nom) + " (" + F.poids(p.b.ko) + ")").join(", ")}</div>` : ""}
          <div class="cbar">
            <button class="hbtn prim" id="c_env">✈ Envoyer</button>
            <button class="hbtn" id="c_br">💾 Enregistrer le brouillon</button>
            <button class="hbtn" id="c_pj">📎 Joindre un fichier</button>
            <button class="hbtn dgr" id="c_del">✕ Abandonner</button>
          </div>
          <div class="hint">Les destinataires <b>internes</b> (@iprospective.eu / .fr) ne passent pas
            par le SMTP : le message est livré en base, en un seul exemplaire (D010/D012). Le piège est
            le mélange interne + externe — le relais ne doit pas re-livrer ce qui l'a déjà été.</div>
        </div>`;
    },
  };
})(window.ABX = window.ABX || {});
