#!/usr/bin/env python3
"""Regenere les epingles Pinterest EN ATTENTE a partir des images ACTUELLES du site.

A lancer depuis ~/agent-orchestrator :
    python3 refaire_epingles.py            # SIMULATION (par defaut)
    python3 refaire_epingles.py --apply    # remplace vraiment les epingles

Ce que le script fait :
  - lit data/pinterest_queue.json (sans jamais l'ecrire) ;
  - pour chaque entree "pending", prend l'image principale ACTUELLE de l'article
    (site/<langue>/<niche>/images/<slug>-0.jpg) et le titre de la file,
    puis regenere l'epingle avec orchestrator.pinterest_image.generate_pin_image ;
  - indique pour chaque epingle si le resultat est CHANGE ou IDENTIQUE a l'ancienne
    (identique = la photo de l'article n'a pas bouge, rien a refaire).

Ce que le script ne fait JAMAIS :
  - toucher a site/ (tes photos remplacees a la main restent exactement comme elles sont) ;
  - modifier la file d'attente ; toucher une entree qui n'est pas "pending".

Simulation : ecrit les nouvelles epingles dans ~/apercu_epingles/ seulement.
--apply    : sauvegarde les anciennes dans ~/sauvegarde_epingles/<horodatage heure de l'Est>/
             puis remplace data/pinterest_images/... (ecriture atomique).
Ne deploie rien (les epingles ne sont pas dans site/).
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

APPLY = "--apply" in sys.argv
root = Path.cwd().resolve()
queue_file = root / "data" / "pinterest_queue.json"


def fail(msg):
    print("ARRET :", msg)
    sys.exit(1)


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


if not queue_file.is_file() or not (root / "orchestrator").is_dir():
    fail("a lancer depuis ~/agent-orchestrator (file d'attente introuvable)")

try:
    queue = json.loads(queue_file.read_text(encoding="utf-8"))
except Exception as e:
    fail(f"file d'attente illisible : {e}")

sys.path.insert(0, str(root))
try:
    from orchestrator import pinterest_image, pinterest_queue
except Exception as e:
    fail(f"import des modules Pinterest impossible : {e}")

logo = pinterest_queue.LOGO_PATH if pinterest_queue.LOGO_PATH.exists() else None
print("Logo :", logo if logo else "absent (epingles sans logo)")

if APPLY and subprocess.run(["pgrep", "-f", "niche_manager.py cycle"],
                            capture_output=True).returncode == 0:
    fail("un cycle est en cours ; attendre sa fin puis relancer")

stamp = datetime.now(ZoneInfo("America/Toronto")).strftime("%Y-%m-%d_%Hh%M")
out_dir = (Path.home() / "sauvegarde_epingles" / stamp) if APPLY else (Path.home() / "apercu_epingles")
if not APPLY and out_dir.exists():
    shutil.rmtree(out_dir)
out_dir.mkdir(parents=True, exist_ok=True)

n_chg = n_same = n_skip = n_fail = n_other = 0
for e in queue:
    if e.get("status") != "pending":
        n_other += 1
        continue
    try:
        lang, niche = e["lang"], e["niche_slug"]
        slug = Path(e["url_path"]).stem
        title = e["title"]
        dest = root / e["image_path"]
    except KeyError as k:
        print(f"IGNORE (champ manquant {k}) : {e.get('id')}")
        n_skip += 1
        continue
    hero = root / "site" / lang / niche / "images" / f"{slug}-0.jpg"
    label = f"{lang}/{niche}/{slug}"
    if not hero.is_file():
        print(f"IGNORE (image principale introuvable) : {label}")
        n_skip += 1
        continue

    tmp = dest.parent / f"{slug}.nouvelle.jpg" if APPLY else out_dir / f"{lang}__{niche}__{slug}.jpg"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    try:
        ok = pinterest_image.generate_pin_image(hero, title, tmp, logo_path=logo)
    except Exception as ex:
        ok = False
        print(f"  erreur : {ex}")
    if not ok or not tmp.is_file():
        print(f"ECHEC (ancienne epingle conservee) : {label}")
        if APPLY and tmp.exists():
            tmp.unlink()
        n_fail += 1
        continue

    same = dest.is_file() and md5(tmp) == md5(dest)
    if same:
        n_same += 1
        print(f"identique : {label}")
        if APPLY:
            tmp.unlink()
        continue

    n_chg += 1
    print(f"CHANGEE   : {label}")
    if APPLY:
        if dest.is_file():
            bak = out_dir / lang / niche / dest.name
            bak.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dest, bak)
        dest.parent.mkdir(parents=True, exist_ok=True)
        os.replace(tmp, dest)

print("\n--- BILAN ---")
print(f"changees : {n_chg} | identiques : {n_same} | ignorees : {n_skip} | echecs : {n_fail} | non pending (non touchees) : {n_other}")
if APPLY:
    print(f"Anciennes epingles sauvegardees dans : {out_dir}")
    print("Epingles remplacees. File d'attente et site/ non modifies.")
else:
    print(f"SIMULATION : rien n'a ete modifie. Apercus dans : {out_dir}")
    print("Verifie quelques apercus (surtout les CHANGEES), puis relance avec --apply.")
