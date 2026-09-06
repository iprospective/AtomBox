/* Formatage et échappement — aucune dépendance, aucun état. */
(function (ABX) {
  "use strict";
  const XML = { "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;" };

  ABX.Fmt = {
    esc: s => String(s == null ? "" : s).replace(/[&<>"]/g, c => XML[c]),

    slug: s => s.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "")
                .replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, ""),

    /* Date de liste : heure aujourd'hui, jour dans la semaine, date au-delà. */
    dt: t => { const d = new Date(t), j = 864e5, now = Date.now();
      if (now - t < j) return d.toTimeString().slice(0, 5);
      if (now - t < 6 * j) return ["dim","lun","mar","mer","jeu","ven","sam"][d.getDay()];
      return d.toLocaleDateString("fr-FR", { day:"2-digit", month:"2-digit", year:"2-digit" }); },

    /* Les tailles du POC sont en kilo-octets — décodés, jamais base64. */
    poids: k => k < 1024 ? k + " ko"
      : (k / 1024).toFixed(k < 10240 ? 1 : 0).replace(".", ",") + " Mo",

    euro: n => n.toLocaleString("fr-FR") + " €",

    /* Les MIME OOXML débordent de toute colonne : abrégés à l'affichage,
       le type complet reste dans le title. */
    mimeC: t => t.replace("application/vnd.openxmlformats-officedocument.", "…ooxml.")
                 .replace("spreadsheetml.sheet", "xlsx")
                 .replace("wordprocessingml.document", "docx"),
  };
})(window.ABX = window.ABX || {});
