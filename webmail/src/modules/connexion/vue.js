/* L'ÉCRAN DE CONNEXION (D157) — la seule vue qui existe sans session.
   Un formulaire, une ligne d'erreur, et le point de contexte « connexion » :
   l'aide y parle à l'utilisateur ; en session simulée, la surcouche CDC n'est
   pas encore chargée — la maquette commence APRÈS la porte, pas avant. */
(function (ABX) {
  "use strict";
  const R = ABX.Registry, F = ABX.Fmt;
  R.define("page.connexion", ({ erreur, occupe }) =>
    `<form class="cnx" id="cnxform" autocomplete="on">
       <div class="logo">Atom<span>Box</span></div>
       <label for="c_user">Identifiant</label>
       <input id="c_user" name="username" autocomplete="username" autocapitalize="none" spellcheck="false" required>
       <label for="c_pass">Mot de passe</label>
       <input id="c_pass" name="password" type="password" autocomplete="current-password" required>
       <div class="cnxerr" id="c_err"${erreur ? "" : " hidden"}>${F.esc(erreur || "")}</div>
       <button class="hbtn prim" id="c_ok" type="submit"${occupe ? " disabled" : ""}>${occupe ? "Connexion…" : "Se connecter"}</button>
       ${R.contexte("connexion", {})}
     </form>`);
})(window.ABX = window.ABX || {});
