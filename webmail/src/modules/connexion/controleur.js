/* CONTRÔLEUR DE CONNEXION (D157). Après une connexion réussie, la page se
   RECHARGE : le chargeur choisit alors le monde (simulé ou réel) au chargement. */
(function (ABX) {
  "use strict";
  const D = ABX.Dom;
  const Connexion = {
    peindre(etat) {
      document.body.dataset.etat = "connexion";
      const el = D.paint("connexion", ABX.Registry.render("page.connexion", etat || {}));
      const form = el.querySelector("#cnxform");
      if (!form) return;
      form.onsubmit = e => { if (e && e.preventDefault) e.preventDefault(); Connexion.soumettre(); return false; };
      const u = D.byId("c_user"); if (u && u.focus) u.focus();
    },
    soumettre() {
      const u = (D.byId("c_user").value || "").trim(), p = D.byId("c_pass").value || "";
      if (!u || !p) return Connexion.peindre({ erreur: "Identifiant et mot de passe, s'il vous plaît." });
      Connexion.peindre({ occupe: true });
      D.byId("c_user").value = u; D.byId("c_pass").value = p;
      return ABX.Session.connecter(u, p)
        .then(() => { location.reload(); return true; })
        .catch(e => { Connexion.peindre({ erreur: /401|refus/.test(String(e && e.message)) ? "Identifiants refusés." : "Service indisponible : " + String(e && e.message || e) }); return false; });
    },
  };
  ABX.Controllers = ABX.Controllers || {};
  ABX.Controllers.Connexion = Connexion;
})(window.ABX = window.ABX || {});
