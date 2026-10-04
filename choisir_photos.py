#!/usr/bin/env python3
"""choisir_photos.py : change la photo principale de quelques articles en la CHOISISSANT TOI-MEME
parmi des candidates Pexels, puis met a jour la mention de credit et refait l'epingle Pinterest.

A placer dans ~/agent-orchestrator et a lancer depuis ce dossier.

ETAPE 1 : chercher (ne modifie ni le site ni les epingles)
    python3 choisir_photos.py chercher                 # 3 candidates pour chaque article de la liste
    python3 choisir_photos.py chercher --seulement 7 15 23
    python3 choisir_photos.py chercher --seulement 1 --n 4 --requete "1=storage ottoman living room" --requete "1=stackable storage bins shelf"
       --requete N="..." remplace la requete de la liste pour l'article N ; donnee plusieurs fois pour le
       meme N, les candidates viennent tour a tour de chaque requete (plus de variete).
    -> ecrit dans ~/choix_photos/ : feuille_1.jpg, feuille_2.jpg... (une ligne par article :
       ACTUELLE | A | B | C) et index.txt (photographe, lien Pexels, description de chaque candidate).
       Les photos deja utilisees sur le site ne sont jamais proposees.

ETAPE 2 : appliquer (simulation par defaut)
    python3 choisir_photos.py appliquer 7=B 15=A 23=C            # SIMULATION
    python3 choisir_photos.py appliquer 7=B 15=A 23=C --apply    # pour de vrai
    Les articles que tu ne nommes pas ne changent pas. Simulation : apercus de la photo et de
    l'epingle dans ~/choix_photos/apercu/ ; rien n'est modifie.
    --apply, dans cet ordre pour chaque article :
      1. sauvegarde (photo -> ~/sauvegarde_images/, page -> ~/sauvegarde_pages/<horodatage>/,
         epingle -> ~/sauvegarde_epingles/<horodatage>/) ;
      2. remplace la photo principale (meme nom, meme taille, recadree au centre) ;
      3. met a jour la mention de credit sous la photo (« Photo: Nom / Pexels » + lien) ;
      4. refait l'epingle Pinterest a partir de la NOUVELLE photo.
    Ne deploie pas : lancer ensuite `bash deploy.sh`, puis Ctrl+F5.

Les numeros (#7, #15...) sont ceux de la planche d'epingles du 2 octobre. La liste TARGETS ci-dessous
(numero, identifiant, requete de recherche) est modifiable a la main (nano).
Refuse de toucher aux articles dont tu as deja remplace la photo a la main (PROTEGES).
"""
import argparse
import html as htmllib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
SITE = ROOT / "site"
QUEUE = DATA / "pinterest_queue.json"
WORK = Path.home() / "choix_photos"
CAND = WORK / "cand"
APERCU = WORK / "apercu"
STATE = WORK / "candidates.json"
TZ = ZoneInfo("America/Toronto")  # heure de l'Est du Quebec
PEXELS_BASE = os.environ.get("PEXELS_API_BASE", "https://api.pexels.com/v1")  # variable : tests seulement
LABELS = "ABCDE"

# (numero de la planche, identifiant de l'epingle, requete Pexels en anglais)
TARGETS = [
    (1,  "en:organisation-et-rangement-en-petit-espace:organizing-small-spaces-with-multi-function-storage-boxes", "storage boxes organized small apartment"),
    (7,  "en:organisation-et-rangement-en-petit-espace:creating-hidden-storage-spaces-in-your-small-apartment", "hidden storage furniture small apartment"),
    (9,  "en:repas-economiques-pour-etudiants:optimizing-your-food-budget-while-studying-kitchen-hacks-you-need", "student cooking budget meal prep"),
    (14, "es:organisation-et-rangement-en-petit-espace:5-pasos-para-optimizar-el-espacio-con-estanterias-moviles", "rolling shelf cart storage small space"),
    (15, "es:organisation-et-rangement-en-petit-espace:como-crear-espacio-oculto-en-tu-pequeno-apartamento", "secret storage compartment furniture"),
    (20, "fr:entretien-de-plantes-d-interieur-pour-debutants:comment-bien-arroser-ses-plantes-d-interieur-sans-les-noyer", "watering can houseplant"),
    (21, "fr:organisation-et-rangement-en-petit-espace:strategies-pour-creer-de-l-espace-cache-dans-votre-petit-appartement", "space saving furniture studio apartment"),
    (22, "fr:repas-economiques-pour-etudiants:comment-optimiser-son-budget-alimentaire-en-etudiant-avec-des-astuces-de-cuisine", "cheap groceries student budget cooking"),
    (23, "fr:soins-de-base-pour-nouveaux-proprietaires-d-animaux:comment-preparer-votre-logement-pour-l-accueil-de-votre-nouveau-chien-ou-chat", "new puppy home living room"),
    (24, "fr:soins-de-base-pour-nouveaux-proprietaires-d-animaux:les-aliments-adaptes-pour-une-alimentation-equilibree-de-votre-nouvel-animal", "pet food bowl feeding"),
    (26, "fr:organisation-et-rangement-en-petit-espace:comment-utiliser-des-etageres-mobiles-pour-maximiser-l-espace", "mobile shelving rack wheels home"),
    (27, "fr:repas-economiques-pour-etudiants:ingredients-essentiels-pour-des-repas-economiques-et-nutritifs", "pantry staples rice beans pasta"),
    (29, "fr:soins-de-base-pour-nouveaux-proprietaires-d-animaux:les-techniques-de-toilette-pour-entretenir-la-beaute-de-votre-animal-de-compagni", "grooming dog brushing at home"),
    (32, "es:organisation-et-rangement-en-petit-espace:formas-de-aprovechar-las-cajas-multifuncion-para-maximizar-el-espacio-en-tu-hoga", "storage boxes organized shelf home"),
    (35, "es:soins-de-base-pour-nouveaux-proprietaires-d-animaux:alimentos-adecuados-para-una-alimentacion-equilibrada-de-tu-nuevo-animal", "puppy eating from bowl"),
    (44, "es:soins-des-animaux:alimentos-para-un-equilibrio-nutricional-correcto-en-tu-perroquet", "parrot eating fruit and seeds"),
    (46, "en:organisation-et-rangement-en-petit-espace:steps-to-install-high-wall-shelves-for-efficient-space-organization", "installing floating wall shelf drill"),
]
PROTEGES = {
    "fr:entretien-de-base-auto-pour-non-mecaniciens:comment-nettoyer-et-lubrifier-correctement-les-essuie-glaces",
    "en:organisation-et-rangement-en-petit-espace:how-to-maximize-space-with-mobile-shelves",
}

CELL, GAP, HEADER, LABEL_H, ROWS_PER_SHEET = 300, 14, 30, 24, 4
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]


# ---------------------------------------------------------------- utilitaires
def fail(msg):
    print("ARRET :", msg)
    sys.exit(1)


def font(size):
    for p in FONT_CANDIDATES:
        if Path(p).is_file():
            return ImageFont.truetype(p, size)
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def stamp():
    return datetime.now(TZ).strftime("%Y-%m-%d_%Hh%M")


def parts(aid):
    try:
        lang, niche, slug = aid.split(":", 2)
    except ValueError:
        fail(f"identifiant invalide : {aid}")
    return lang, niche, slug


def article_paths(aid):
    lang, niche, slug = parts(aid)
    return {
        "lang": lang, "niche": niche, "slug": slug,
        "page": SITE / lang / niche / f"{slug}.html",
        "hero": SITE / lang / niche / "images" / f"{slug}-0.jpg",
        "src": f"images/{slug}-0.jpg",
    }


def load_queue():
    try:
        q = json.loads(QUEUE.read_text(encoding="utf-8"))
        return q if isinstance(q, list) else []
    except (OSError, ValueError):
        return []


def used_pexels_ids():
    ids = set()
    for p in SITE.rglob("*.html"):
        try:
            for m in re.finditer(r'pexels\.com/photo/[^"\s<>]*?-(\d+)/', p.read_text(encoding="utf-8", errors="ignore")):
                ids.add(int(m.group(1)))
        except OSError:
            pass
    return ids


def get_key():
    sys.path.insert(0, str(ROOT))
    try:
        from orchestrator.strategies import niche_content
    except Exception as e:
        fail(f"import de niche_content impossible : {e}")
    key = getattr(niche_content, "PEXELS_API_KEY", "")
    if not key:
        fail("cle Pexels introuvable (niche_content.PEXELS_API_KEY vide)")
    return key


def http_get(url, headers=None, timeout=60):
    h = {"User-Agent": "gpq-photo-picker/1.0"}
    h.update(headers or {})
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        fail(f"HTTP {e.code} en appelant {url.split('?')[0]}" + (" (limite Pexels atteinte : reessaie plus tard)" if e.code == 429 else ""))
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        fail(f"erreur reseau : {type(e).__name__}")


def thumb_into(sheet, path, x, y):
    try:
        with Image.open(path) as im:
            im = im.convert("RGB")
            im.thumbnail((CELL, CELL), Image.LANCZOS)
            sheet.paste(im, (x + (CELL - im.width) // 2, y + (CELL - im.height) // 2))
    except (OSError, ValueError):
        d = ImageDraw.Draw(sheet)
        d.rectangle([x, y, x + CELL, y + CELL], fill=(200, 200, 200))
        d.text((x + 70, y + CELL // 2), "IMAGE ABSENTE", fill=(90, 0, 0), font=font(20))


# -------------------------------------------------------------------- chercher
def cmd_chercher(args):
    key = get_key()
    queue = {e.get("id"): e for e in load_queue()}
    overrides = {}
    for it in args.requete or []:
        m = re.fullmatch(r"(\d+)=(.+)", it.strip())
        if not m:
            fail(f"--requete invalide : « {it} » (format : 1=ma requete en anglais)")
        overrides.setdefault(int(m.group(1)), []).append(m.group(2).strip())
    for n in overrides:
        if n not in {t[0] for t in TARGETS}:
            fail(f"--requete : #{n} n'est pas dans la liste TARGETS")
    wanted = set(args.seulement) if args.seulement else None
    targets = [t for t in TARGETS if wanted is None or t[0] in wanted]
    if not targets:
        fail("aucun article correspondant dans la liste TARGETS")
    if WORK.exists():
        for p in [CAND, APERCU]:
            shutil.rmtree(p, ignore_errors=True)
        for p in list(WORK.glob("feuille_*.jpg")) + [STATE, WORK / "index.txt"]:
            if p.exists():
                p.unlink()
    CAND.mkdir(parents=True, exist_ok=True)

    used = used_pexels_ids()
    proposed = set()
    state, index_lines = [], []
    for n, aid, default_query in targets:
        queries = overrides.get(n) or [default_query]
        query = " + ".join(queries)
        if aid in PROTEGES:
            print(f"#{n} ignore (photo remplacee a la main, protegee)")
            continue
        ap = article_paths(aid)
        if not ap["hero"].is_file():
            print(f"#{n} ignore (photo principale introuvable : {ap['hero'].name})")
            continue
        with Image.open(ap["hero"]) as im:
            w, h = im.size
        orient = "landscape" if w >= h else "portrait"
        pools = []
        for q in queries:
            qs = urllib.parse.urlencode({"query": q, "per_page": 40, "orientation": orient})
            data = json.loads(http_get(f"{PEXELS_BASE}/search?{qs}", headers={"Authorization": key}).decode("utf-8"))
            pools.append([p for p in data.get("photos", [])
                          if p.get("id") not in used and p.get("width", 0) >= w and p.get("height", 0) >= h])
            if len(queries) > 1:
                time.sleep(0.3)
        picked, seen, i = [], set(), 0
        while len(picked) < args.n and any(i < len(pl) for pl in pools):
            for pl in pools:
                if i < len(pl) and pl[i]["id"] not in seen and pl[i]["id"] not in proposed:
                    picked.append(pl[i])
                    seen.add(pl[i]["id"])
                    if len(picked) == args.n:
                        break
            i += 1
        cands = []
        for i, p in enumerate(picked):
            label = LABELS[i]
            dest = CAND / f"n{n}_{label}.jpg"
            dest.write_bytes(http_get(p["src"]["large2x"]))
            try:
                with Image.open(dest) as test:
                    test.verify()
            except Exception:
                dest.unlink(missing_ok=True)
                continue
            proposed.add(p["id"])
            cand = {"label": label, "pexels_id": p["id"], "photographer": p.get("photographer", ""),
                    "photographer_url": p.get("photographer_url", ""), "url": p.get("url", ""),
                    "alt": p.get("alt", ""), "file": str(dest)}
            cands.append(cand)
            index_lines.append(f"#{n} {label} | {cand['photographer']} | {cand['url']} | {cand['alt']}")
        print(f"#{n} {ap['lang'].upper()} : {len(cands)} candidate(s)  [{query}]")
        state.append({"n": n, "id": aid, "query": query, "cands": cands})
        time.sleep(0.5)

    # feuilles : une ligne par article = ACTUELLE | A | B | C
    shown = [s for s in state if s["cands"]]
    f_head, f_lab = font(18), font(16)
    for si in range(0, len(shown), ROWS_PER_SHEET):
        chunk = shown[si: si + ROWS_PER_SHEET]
        ncols = 1 + max(len(s["cands"]) for s in chunk)
        W = ncols * (CELL + GAP) + GAP
        row_h = HEADER + LABEL_H + CELL + GAP
        sheet = Image.new("RGB", (W, GAP + len(chunk) * row_h), (240, 240, 240))
        d = ImageDraw.Draw(sheet)
        for r, s in enumerate(chunk):
            y0 = GAP + r * row_h
            ap = article_paths(s["id"])
            d.text((GAP, y0), f"#{s['n']}  {ap['lang'].upper()}  recherche : {s['query']}", fill=(0, 0, 0), font=f_head)
            cells = [("ACTUELLE", ap["hero"])] + [(c["label"], Path(c["file"])) for c in s["cands"]]
            for c, (lab, path) in enumerate(cells):
                x = GAP + c * (CELL + GAP)
                d.text((x, y0 + HEADER), lab, fill=(150, 0, 0) if lab == "ACTUELLE" else (0, 90, 0), font=f_lab)
                thumb_into(sheet, path, x, y0 + HEADER + LABEL_H)
        sheet.save(WORK / f"feuille_{si // ROWS_PER_SHEET + 1}.jpg", format="JPEG", quality=88)

    STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    (WORK / "index.txt").write_text("\n".join(index_lines) + "\n", encoding="utf-8")
    nsheets = math.ceil(len(shown) / ROWS_PER_SHEET) if shown else 0
    print(f"\n{len(shown)} article(s) avec candidates sur {nsheets} feuille(s) -> {WORK}/")
    sans = [s["n"] for s in state if not s["cands"]]
    if sans:
        print("Aucune candidate trouvee pour :", ", ".join(f"#{n}" for n in sans), "(change la requete dans TARGETS)")
    print("Telecharge le dossier (WinSCP), regarde les feuilles, puis lance par exemple :")
    print("  python3 choisir_photos.py appliquer 7=B 15=A")


# -------------------------------------------------------------------- appliquer
def credit_pattern(src):
    return re.compile(
        r'(<p><img [^>]*src="' + re.escape(src) + r'"[^>]*/></p>)'
        r'(\n<p style="font-size:0\.75em;color:#999;">[^\n]*</p>)?'
        r'(\n?)'
    )


def cmd_appliquer(args):
    choices = {}
    for it in args.choix:
        m = re.fullmatch(r"(\d+)=([A-Ea-e])", it)
        if not m:
            fail(f"choix invalide : « {it} » (format attendu : 7=B)")
        n = int(m.group(1))
        if n in choices:
            fail(f"le numero #{n} est donne deux fois")
        choices[n] = m.group(2).upper()
    try:
        state = {s["n"]: s for s in json.loads(STATE.read_text(encoding="utf-8"))}
    except (OSError, ValueError):
        fail("aucune recherche trouvee : lance d'abord `python3 choisir_photos.py chercher`")

    sys.path.insert(0, str(ROOT))
    try:
        from orchestrator import pinterest_image, pinterest_queue
    except Exception as e:
        fail(f"import des modules Pinterest impossible : {e}")
    logo = pinterest_queue.LOGO_PATH if pinterest_queue.LOGO_PATH.exists() else None
    queue = {e.get("id"): e for e in load_queue()}

    plan = []
    for n, label in sorted(choices.items()):
        s = state.get(n)
        if not s:
            fail(f"#{n} : pas dans la derniere recherche")
        if s["id"] in PROTEGES:
            fail(f"#{n} : article protege (photo deja remplacee a la main)")
        cand = next((c for c in s["cands"] if c["label"] == label), None)
        if not cand or not Path(cand["file"]).is_file():
            fail(f"#{n} : la candidate {label} n'existe pas")
        ap = article_paths(s["id"])
        if not ap["hero"].is_file() or not ap["page"].is_file():
            fail(f"#{n} : page ou photo principale introuvable")
        html = ap["page"].read_text(encoding="utf-8")
        found = list(credit_pattern(ap["src"]).finditer(html))
        if len(found) != 1:
            fail(f"#{n} : je trouve {len(found)} fois l'image {ap['src']} dans la page (il en faut exactement 1)")
        entry = queue.get(s["id"])
        title = (entry or {}).get("title")
        if not title:
            mt = re.search(r"<title>(.*?)</title>", html, re.S)
            title = htmllib.unescape(mt.group(1).split(" — ")[0].strip()) if mt else ap["slug"]
        pin = ROOT / entry["image_path"] if entry and entry.get("image_path") else DATA / "pinterest_images" / ap["lang"] / ap["niche"] / f"{ap['slug']}.jpg"
        pin_ok = entry is None or entry.get("status") == "pending"
        new_credit = (f'<p style="font-size:0.75em;color:#999;">Photo: <a href="{htmllib.escape(cand["url"], quote=True)}">'
                      f'{htmllib.escape(cand["photographer"])}</a> / Pexels</p>')
        plan.append({"n": n, "label": label, "s": s, "cand": cand, "ap": ap, "html": html, "match": found[0],
                     "title": title, "pin": pin, "pin_ok": pin_ok, "credit": new_credit})

    for p in plan:
        with Image.open(p["ap"]["hero"]) as old:
            p["size"] = old.size
        with Image.open(p["cand"]["file"]) as raw:
            p["fitted"] = ImageOps.fit(ImageOps.exif_transpose(raw).convert("RGB"), p["size"], Image.LANCZOS, centering=(0.5, 0.5))
        print(f"\n#{p['n']} {p['ap']['lang'].upper()} -> candidate {p['label']} ({p['cand']['photographer']})")
        print(f"   article : {p['ap']['lang']}/{p['ap']['niche']}/{p['ap']['slug']}.html")
        print(f"   credit  : {p['credit']}")
        if not p["pin_ok"]:
            print("   epingle : deja postee, non touchee")

    if not args.apply:
        APERCU.mkdir(parents=True, exist_ok=True)
        for p in plan:
            hero_prev = APERCU / f"n{p['n']}_photo.jpg"
            p["fitted"].save(hero_prev, format="JPEG", quality=85, optimize=True)
            try:
                ok = pinterest_image.generate_pin_image(hero_prev, p["title"], APERCU / f"n{p['n']}_epingle.jpg", logo_path=logo)
            except Exception:
                ok = False
            if not ok:
                print(f"   (apercu d'epingle impossible pour #{p['n']})")
        print(f"\nSIMULATION : rien n'a ete modifie. Apercus (photo + epingle) dans {APERCU}/")
        print("Si c'est bon, relance la meme commande avec --apply.")
        return

    if subprocess.run(["pgrep", "-f", "niche_manager.py cycle"], capture_output=True).returncode == 0:
        fail("un cycle est en cours ; attendre sa fin puis relancer")
    ts = stamp()
    bak_img = Path.home() / "sauvegarde_images"
    bak_pages = Path.home() / "sauvegarde_pages" / ts
    bak_pins = Path.home() / "sauvegarde_epingles" / ts
    for d in (bak_img, bak_pages, bak_pins):
        d.mkdir(parents=True, exist_ok=True)
    done, problems = 0, []
    for p in plan:
        ap = p["ap"]
        tag = f"#{p['n']}"
        # 1. sauvegardes
        shutil.copy2(ap["hero"], bak_img / f"{ap['lang']}__{ap['niche']}__{ap['slug']}-0_{ts}.jpg")
        shutil.copy2(ap["page"], bak_pages / f"{ap['lang']}__{ap['niche']}__{ap['page'].name}")
        if p["pin"].is_file():
            (bak_pins / ap["lang"] / ap["niche"]).mkdir(parents=True, exist_ok=True)
            shutil.copy2(p["pin"], bak_pins / ap["lang"] / ap["niche"] / p["pin"].name)
        # 2. photo principale
        tmp = ap["hero"].with_name(ap["hero"].name + ".tmp")
        p["fitted"].save(tmp, format="JPEG", quality=85, optimize=True)
        os.replace(tmp, ap["hero"])
        # 3. mention de credit dans la page (la page a ete relue juste avant d'ecrire)
        html = ap["page"].read_text(encoding="utf-8")
        found = list(credit_pattern(ap["src"]).finditer(html))
        if len(found) == 1:
            m = found[0]
            new_html = html[: m.start()] + m.group(1) + "\n" + p["credit"] + m.group(3) + html[m.end():]
            tmp = ap["page"].with_name(ap["page"].name + ".tmp")
            tmp.write_text(new_html, encoding="utf-8")
            os.replace(tmp, ap["page"])
        else:
            problems.append(f"{tag} : mention de credit NON mise a jour (page modifiee entre-temps ?)")
        # 4. epingle, a partir de la NOUVELLE photo
        if p["pin_ok"]:
            pin_tmp = p["pin"].with_name(p["pin"].stem + ".nouvelle.jpg")
            p["pin"].parent.mkdir(parents=True, exist_ok=True)
            try:
                ok = pinterest_image.generate_pin_image(ap["hero"], p["title"], pin_tmp, logo_path=logo)
            except Exception:
                ok = False
            if ok and pin_tmp.is_file():
                os.replace(pin_tmp, p["pin"])
            else:
                pin_tmp.unlink(missing_ok=True)
                problems.append(f"{tag} : epingle NON refaite (ancienne conservee) ; relance refaire_epingles.py --apply")
        with Image.open(ap["hero"]) as chk:
            if chk.size != p["size"]:
                problems.append(f"{tag} : la taille de la photo a change ({chk.size} au lieu de {p['size']})")
        done += 1
        print(f"{tag} fait : photo, credit, epingle")
    print(f"\n{done} article(s) traite(s). Sauvegardes : {bak_img}/ , {bak_pages}/ , {bak_pins}/")
    for pr in problems:
        print("ATTENTION :", pr)
    print("Suite : bash deploy.sh   puis Ctrl+F5 dans le navigateur.")


def main():
    ap = argparse.ArgumentParser(description="Choisir de nouvelles photos d'articles (voir l'en-tete du fichier).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("chercher")
    c.add_argument("--n", type=int, default=3)
    c.add_argument("--seulement", type=int, nargs="+")
    c.add_argument("--requete", action="append", metavar='N="requete"')
    c.set_defaults(fn=cmd_chercher)
    a = sub.add_parser("appliquer")
    a.add_argument("choix", nargs="+")
    a.add_argument("--apply", action="store_true")
    a.set_defaults(fn=cmd_appliquer)
    args = ap.parse_args()
    if getattr(args, "n", 3) < 1 or getattr(args, "n", 3) > 5:
        fail("--n entre 1 et 5")
    args.fn(args)


if __name__ == "__main__":
    main()
