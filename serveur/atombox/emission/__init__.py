"""L'ÉMISSION (F109 — D114, D099) : un module interne qui consomme l'événement message.a_envoyer,
remet le message au relais SMTP du client, écrit l'envoi et ses destinataires, et dépose une copie
dans Envoyés côté IMAP (F113 : IMAP reste la vérité jusqu'à la V3)."""
