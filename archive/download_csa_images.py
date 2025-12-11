import os
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_DOMAIN = "https://front9farm.com"
IMG_PREFIX = "/sites/default/files/inline-images/"
RECIPE_URL_TEMPLATE = BASE_DOMAIN + "/index.php/{year}-csa-week-{week}-recipes"

YEARS = [2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]
MAX_WEEKS = 28  # we will attempt up to 28; missing weeks/images are handled gracefully

# Base folder where images should live: ~/Desktop/imgs
BASE_SAVE_DIR = Path.home() / "Desktop" / "imgs"


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def download_file(url: str, dest: Path) -> bool:
    """
    Download a file from url to dest (if dest does not already exist).
    Returns True on success, False on failure.
    """
    if dest.exists():
        print(f"  [SKIP] already exists: {dest}")
        return True

    try:
        print(f"  [DL] {url} -> {dest}")
        resp = requests.get(url, stream=True, timeout=15)
        if resp.status_code != 200:
            print(f"  [ERROR] HTTP {resp.status_code} for {url}")
            return False

        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        return True
    except Exception as e:
        print(f"  [ERROR] downloading {url}: {e}")
        return False


def get_recipe_page(year: int, week: int) -> BeautifulSoup | None:
    url = RECIPE_URL_TEMPLATE.format(year=year, week=week)
    print(f"  [PAGE] {url}")
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code != 200:
            print(f"  [WARN] HTTP {resp.status_code} for {url} (skipping week)")
            return None
        return BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        print(f"  [ERROR] fetching page {url}: {e}")
        return None


def extract_recipe_image_srcs(soup: BeautifulSoup) -> list[str]:
    """
    From the weekly recipe page, find <img> tags whose src:
      - starts with IMG_PREFIX
      - does NOT end with '-share.jpg'
    Return a list of unique src paths, in the order encountered.
    """
    seen = set()
    results: list[str] = []

    for img in soup.find_all("img"):
        src = img.get("src")
        if not src:
            continue

        # Normalize relative vs absolute
        if src.startswith("http://") or src.startswith("https://"):
            # Optionally only keep from this domain
            if BASE_DOMAIN not in src:
                continue
            rel = src.replace(BASE_DOMAIN, "")
        else:
            rel = src

        if not rel.startswith(IMG_PREFIX):
            continue
        if rel.endswith("-share.jpg"):
            # that's the haul/share image, skip for recipe images
            continue

        if rel not in seen:
            seen.add(rel)
            results.append(rel)

    return results


def main():
    # Prepare base directories
    csa_base = BASE_SAVE_DIR / "csa"
    recipes_base = BASE_SAVE_DIR / "recipes"
    ensure_dir(csa_base)
    ensure_dir(recipes_base)

    session = requests.Session()

    for year in YEARS:
        print(f"\n===== YEAR {year} =====")

        csa_year_dir = csa_base / str(year)
        recipes_year_dir = recipes_base / str(year)
        ensure_dir(csa_year_dir)
        ensure_dir(recipes_year_dir)

        for week in range(1, MAX_WEEKS + 1):
            print(f"\n--- Week {week} ---")

            # 1) Download CSA haul/share image
            share_name = f"{year}-csa-week-{week}-share.jpg"
            share_url = urljoin(BASE_DOMAIN, IMG_PREFIX + share_name)
            haul_dest = csa_year_dir / f"csa_haul_{year}_{week}.jpg"

            # Use the session for all HTTP calls
            try:
                resp = session.get(share_url, stream=True, timeout=10)
                if resp.status_code == 200:
                    if haul_dest.exists():
                        print(f"  [SKIP] CSA haul already exists: {haul_dest}")
                    else:
                        print(f"  [DL] CSA haul {share_url} -> {haul_dest}")
                        with open(haul_dest, "wb") as f:
                            for chunk in resp.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                else:
                    print(f"  [WARN] No CSA haul image for {year} week {week}: HTTP {resp.status_code}")
            except Exception as e:
                print(f"  [ERROR] downloading CSA haul for {year} week {week}: {e}")

            # 2) Fetch recipe page and download up to 5 recipe images
            soup = get_recipe_page(year, week)
            if soup is None:
                # Probably no page for this week/year; skip recipes
                continue

            recipe_srcs = extract_recipe_image_srcs(soup)
            if not recipe_srcs:
                print("  [WARN] No recipe images found on page.")
            else:
                # Only take first 5 images
                for idx, rel_src in enumerate(recipe_srcs[:5], start=1):
                    img_url = urljoin(BASE_DOMAIN, rel_src)
                    recipe_dest = recipes_year_dir / f"csa_recipe_{year}_{week}_{idx}.jpg"
                    download_file(img_url, recipe_dest)

            # be polite to server
            time.sleep(1)

    print("\nAll done.")


if __name__ == "__main__":
    main()
