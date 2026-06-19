# Serveur Prévamceo — Émargement numérique

## Routes disponibles

- `GET /health` — vérification serveur
- `POST /creer-session` — Make.com envoie les données
- `GET /signer/{session_id}` — page de signature formateur
- `POST /soumettre-signature/{session_id}` — formateur soumet sa signature
- `GET /statut/{session_id}` — Make.com vérifie si signé
- `GET /telecharger-pdf/{session_id}` — Make.com télécharge le PDF
