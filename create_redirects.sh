#!/bin/bash
set -e

make_redirect() {
  local slug="$1"
  mkdir -p "$slug"
  cat > "$slug/index.html" <<EOF
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <link rel="canonical" href="https://simonlinuxia.github.io/mes-niches-site/fr/${slug}/">
  <meta http-equiv="refresh" content="0; url=https://simonlinuxia.github.io/mes-niches-site/fr/${slug}/">
  <title>Redirection...</title>
</head>
<body>
  <p>Cette page a déménagé. <a href="https://simonlinuxia.github.io/mes-niches-site/fr/${slug}/">Cliquez ici si vous n'êtes pas redirigé automatiquement</a>.</p>
</body>
</html>
EOF
  echo "Créé : $slug/index.html"
}

make_redirect "entretien-de-base-auto-pour-non-mecaniciens"
make_redirect "entretien-de-plantes-d-interieur-pour-debutants"
make_redirect "repas-economiques-pour-etudiants"

echo ""
echo "=== Vérification encodage ==="
file -i entretien-de-base-auto-pour-non-mecaniciens/index.html \
        entretien-de-plantes-d-interieur-pour-debutants/index.html \
        repas-economiques-pour-etudiants/index.html

echo ""
echo "Prêt à committer. Lance ensuite :"
echo "  git add entretien-de-base-auto-pour-non-mecaniciens/index.html entretien-de-plantes-d-interieur-pour-debutants/index.html repas-economiques-pour-etudiants/index.html"
echo "  git commit -m 'Ajout de redirections pour les 3 anciennes URLs pré-multilingue'"
echo "  cd .. && ./deploy.sh"
