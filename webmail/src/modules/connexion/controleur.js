/* CONTRÔLEUR DE CONNEXION (D157). Après une connexion réussie, la page se
   RECHARGE : le chargeur choisit alors le monde (simulé ou réel) au chargement. */
(function (ABX) {
  "use strict";
  const D = ABX.Dom;
  const Connexion = {
    /* L'écran voulu se déduit de l'état : un jeton dans le fragment d'URL ouvre le choix du
       nouveau mot de passe (F129). Le fragment n'est PAS envoyé au serveur par le navigateur —
       c'est ce qui le rend préférable à un paramètre de requête, qui finirait dans les journaux
       d'accès et dans le Referer. */
    jetonDuLien() {
      try { const m = /(?:^|[#&])reinitialiser=([\w.~-]+)/.exec(String(location.hash || "")); return m ? m[1] : null; }
      catch (e) { return null; }
    },

    peindre(etat) {
      document.body.dataset.etat = "connexion";
      const e = etat || {};
      const page = e.page || (Connexion.jetonDuLien() ? "reinitialiser" : "connexion");
      const el = D.paint("connexion", ABX.Registry.render("page." + page, e));
      const form = el.querySelector("#cnxform");
      if (!form) return;
      if (page === "connexion") {
        form.onsubmit = ev => { if (ev && ev.preventDefault) ev.preventDefault(); Connexion.soumettre(); return false; };
        const o = D.byId("c_oubli"); if (o) o.onclick = () => Connexion.peindre({ page: "oubli" });
        const u = D.byId("c_user"); if (u && u.focus) u.focus();
      } else if (page === "oubli") {
        form.onsubmit = ev => { if (ev && ev.preventDefault) ev.preventDefault(); Connexion.demander(); return false; };
        const r = D.byId("o_retour"); if (r) r.onclick = () => Connexion.peindre({});
        const u = D.byId("o_user"); if (u && u.focus) u.focus();
      } else {
        form.onsubmit = ev => { if (ev && ev.preventDefault) ev.preventDefault(); Connexion.reinitialiser(); return false; };
        const u = D.byId("r_pass"); if (u && u.focus) u.focus();
      }
    },

    /* La réponse est la MÊME dans tous les cas (D164) : on l'affiche telle quelle, sans rien
       y ajouter — un « compte introuvable » ferait de ce formulaire un annuaire. */
    demander() {
      const u = (D.byId("o_user").value || "").trim();
      if (!u) return Connexion.peindre({ page: "oubli", erreur: "Identifiant ou adresse, s'il vous plaît." });
      Connexion.peindre({ page: "oubli", occupe: true });
      D.byId("o_user").value = u;
      return ABX.Api.demanderReinitialisation(u)
        .then(r => { Connexion.peindre({ page: "oubli", message: (r && r.message) || "Demande enregistrée." }); return true; })
        .catch(err => { Connexion.peindre({ page: "oubli", erreur: Connexion.motif(err) }); return false; });
    },

    reinitialiser() {
      const a = D.byId("r_pass").value || "", b = D.byId("r_pass2").value || "";
      if (a !== b) return Connexion.peindre({ page: "reinitialiser", erreur: "Les deux mots de passe diffèrent." });
      if (a.length < 10) return Connexion.peindre({ page: "reinitialiser", erreur: "Dix caractères au minimum." });
      Connexion.peindre({ page: "reinitialiser", occupe: true });
      return ABX.Api.reinitialiser(Connexion.jetonDuLien(), a)
        .then(() => {
          try { location.hash = ""; } catch (e) {}
          Connexion.peindre({ message: "Mot de passe changé. Connectez-vous." });
          return true;
        })
        .catch(err => { Connexion.peindre({ page: "reinitialiser", erreur: Connexion.motif(err) }); return false; });
    },

    motif(e) {
      const m = String(e && e.message || e);
      if (/sans-api|404/.test(m)) return "Aucun service à cette adresse : cette page ne sert que la maquette.";
      if (/400/.test(m)) return "Lien invalide ou périmé — redemandez-en un.";
      return "Service indisponible : " + m;
    },
    soumettre() {
      const u = (D.byId("c_user").value || "").trim(), p = D.byId("c_pass").value || "";
      if (!u || !p) return Connexion.peindre({ erreur: "Identifiant et mot de passe, s'il vous plaît." });
      Connexion.peindre({ occupe: true });
      D.byId("c_user").value = u; D.byId("c_pass").value = p;
      return ABX.Session.connecter(u, p)
        .then(() => { location.reload(); return true; })
        .catch(e => {
          const m = String(e && e.message || e);
          Connexion.peindre({ erreur:
            /sans-api|404/.test(m)
              ? "Aucun service à cette adresse : cette page ne sert que la maquette. Connectez-vous avec poc / poc."
              : /401|refus/.test(m) ? "Identifiants refusés."
              : "Service indisponible : " + m });
          return false;
        });
    },
  };
  ABX.Controllers = ABX.Controllers || {};
  ABX.Controllers.Connexion = Connexion;
})(window.ABX = window.ABX || {});
