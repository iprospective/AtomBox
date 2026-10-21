# Certificat de TEST — et seulement de test

`test-only.crt` / `test-only.key` : un certificat auto-signé pour `127.0.0.1`, valable cent ans,
qui sert aux tests du TLS de l'écouteur IMAP (`tests/test_imap_tls.py`).

**La clé est publique, et c'est voulu** : elle est dans un dépôt miroité sur GitHub. Elle ne
protège rien et ne doit protéger rien. Elle est versionnée plutôt qu'engendrée pendant le test pour
que la suite ne dépende pas de la présence du binaire `openssl` — un test qui s'ignore faute
d'outil, en CI, ne garde rien.

Le certificat des machines servies se pose avec `server/tools/make-imapd-cert.sh` et ne quitte
jamais `~/.config/atombox/imapd/`.
