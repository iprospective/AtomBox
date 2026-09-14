/* L'ÉCRAN DE CONNEXION (D157) — la seule vue qui existe sans session.
   Un formulaire, une ligne d'erreur, et le point de contexte « connexion » :
   l'aide y parle à l'utilisateur ; en session simulée, la surcouche CDC n'est
   pas encore chargée — la maquette commence APRÈS la porte, pas avant. */
(function (ABX) {
  "use strict";
  const R = ABX.Registry, F = ABX.Fmt;
  /* F129 — « mot de passe oublié » : demander, puis choisir. Trois écrans, une seule page, parce
     qu'il n'y a qu'un index (D157) ; l'écran voulu se déduit de l'état, jamais d'une URL cachée. */
  R.define("page.oubli", ({ erreur, message, occupe }) =>
    `<form class="cnx" id="cnxform">
       <div class="logo">Atom<span>Box</span></div>
       <p class="cnxint">Indiquez votre identifiant ou votre adresse. Si un compte y correspond et
         qu'une <b>adresse de secours</b> y est enregistrée, un lien vous y sera envoyé.</p>
       <label for="o_user">Identifiant ou adresse</label>
       <input id="o_user" name="username" autocomplete="username" autocapitalize="none" spellcheck="false" required>
       <div class="cnxerr" id="c_err"${erreur ? "" : " hidden"}>${F.esc(erreur || "")}</div>
       <div class="cnxok" id="c_msg"${message ? "" : " hidden"}>${F.esc(message || "")}</div>
       <button class="hbtn prim" id="o_ok" type="submit"${occupe ? " disabled" : ""}>${occupe ? "Envoi…" : "Envoyer le lien"}</button>
       <button class="hbtn" id="o_retour" type="button">Revenir à la connexion</button>
     </form>`);

  R.define("page.reinitialiser", ({ erreur, message, occupe }) =>
    `<form class="cnx" id="cnxform">
       <div class="logo">Atom<span>Box</span></div>
       <p class="cnxint">Choisissez un nouveau mot de passe. En le validant,
         <b>toutes les sessions ouvertes de ce compte seront fermées</b> — y compris celle de quelqu'un d'autre.</p>
       <label for="r_pass">Nouveau mot de passe</label>
       <input id="r_pass" name="password" type="password" autocomplete="new-password" required>
       <label for="r_pass2">Répétez-le</label>
       <input id="r_pass2" name="password2" type="password" autocomplete="new-password" required>
       <div class="cnxerr" id="c_err"${erreur ? "" : " hidden"}>${F.esc(erreur || "")}</div>
       <div class="cnxok" id="c_msg"${message ? "" : " hidden"}>${F.esc(message || "")}</div>
       <button class="hbtn prim" id="r_ok" type="submit"${occupe ? " disabled" : ""}>${occupe ? "Enregistrement…" : "Changer le mot de passe"}</button>
     </form>`);

  R.define("page.connexion", ({ erreur, message, occupe }) =>
    `<form class="cnx" id="cnxform" autocomplete="on">
       <div class="logo">Atom<span>Box</span></div>
       <label for="c_user">Identifiant</label>
       <input id="c_user" name="username" autocomplete="username" autocapitalize="none" spellcheck="false" required>
       <label for="c_pass">Mot de passe</label>
       <input id="c_pass" name="password" type="password" autocomplete="current-password" required>
       <div class="cnxerr" id="c_err"${erreur ? "" : " hidden"}>${F.esc(erreur || "")}</div>
       <div class="cnxok" id="c_msg"${message ? "" : " hidden"}>${F.esc(message || "")}</div>
       <button class="hbtn prim" id="c_ok" type="submit"${occupe ? " disabled" : ""}>${occupe ? "Connexion…" : "Se connecter"}</button>
       <button class="lien" id="c_oubli" type="button">Mot de passe oublié ?</button>
       ${R.contexte("connexion", {})}
     </form>`);
})(window.ABX = window.ABX || {});
