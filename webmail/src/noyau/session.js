/* LA SESSION (D157) — qui est connecté, et dans quel monde.

   Une session est un jeton (D063) et un mode : « api » quand le serveur a répondu,
   « poc » quand l'utilisateur s'est présenté avec poc/poc. Le second n'est pas
   un secret : c'est LA porte d'entrée de la maquette — la même page, la même
   interface, et un monde simulé derrière. Rien du POC n'est chargé tant que la
   session n'est pas « poc » : c'est le chargeur qui s'en assure. */
(function (ABX) {
  "use strict";
  const CLE = "abx.session";
  const Session = {
    lire() { try { return JSON.parse(localStorage.getItem(CLE) || "null"); } catch (e) { return null; } },
    ouvrir(s) { try { localStorage.setItem(CLE, JSON.stringify(s)); } catch (e) {} },
    fermer() { try { localStorage.removeItem(CLE); } catch (e) {} },
    simulee() { const s = Session.lire(); return !!(s && s.mode === "poc"); },
    jeton() { const s = Session.lire(); return s ? s.jeton : null; },
    compte() { const s = Session.lire(); return s ? s.compte : null; },

    /* poc/poc ouvre la session simulée ; tout autre couple va au serveur (POST /session).
       Dans les deux cas l'appelant RECHARGE la page : c'est au chargement que le
       monde se choisit, jamais en cours de route. */
    connecter(utilisateur, mot_de_passe) {
      if (utilisateur === "poc" && mot_de_passe === "poc") {
        if (window.ABX_SANS_POC) return Promise.reject(new Error("le mode simulé n'est pas disponible sur cette page"));
        Session.ouvrir({ mode: "poc", jeton: "poc", compte: "poc" });
        return Promise.resolve({ mode: "poc" });
      }
      return ABX.Api.connecter(utilisateur, mot_de_passe).then(r => {
        if (!r || !r.jeton) throw new Error("identifiants refusés");
        Session.ouvrir({ mode: "api", jeton: r.jeton, compte: r.compte || utilisateur });
        return { mode: "api" };
      });
    },
  };
  /* LE WEBMAIL INTÉGRÉ À UNE APPLICATION (F148). La page de l'ERP l'affiche dans un cadre avec une
     session DÉLÉGUÉE dans le fragment : `#session=<jeton>&compte=<login>&integre=1`. Le fragment ne
     part jamais au serveur (aucun journal ne le voit) ; on l'enregistre AVANT que le chargeur ne
     choisisse son monde, puis on l'efface de l'adresse ET de l'historique. */
  Session.depuisFragment = (loc, hist) => {
    const h = new URLSearchParams(((loc && loc.hash) || "").replace(/^#/, ""));
    if (h.get("integre") === "1") { try { sessionStorage.setItem("abx.integre", "1"); } catch (e) {} }
    const jeton = h.get("session");
    if (!jeton) return false;
    Session.ouvrir({ mode: "api", jeton, compte: h.get("compte") || "" });
    ["session", "compte", "integre"].forEach(k => h.delete(k));
    const reste = h.toString();
    try { hist.replaceState(null, "", loc.pathname + loc.search + (reste ? "#" + reste : "")); } catch (e) {}
    return true;
  };
  Session.integre = () => { try { return sessionStorage.getItem("abx.integre") === "1"; } catch (e) { return false; } };
  if (typeof location !== "undefined" && typeof history !== "undefined") Session.depuisFragment(location, history);
  ABX.Session = Session;
})(window.ABX = window.ABX || {});
