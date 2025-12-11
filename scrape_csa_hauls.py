"""
Extended CSA scraper.

This script scrapes weekly CSA pages across multiple years (2017–2025) and
produces two JSON files:

* **csa_hauls.json** – a list of CSA share contents for each week with
  timestamps, titles, aliases, image paths and share item lists.
* **csa_recipes.json** – a list of recipes across all weeks with recipe
  identifiers, titles, image paths, CSA items used, extra ingredients
  required, and instructions split into paragraphs.

The script does not download images; it assumes images are already saved
according to the naming conventions described in the configuration
section.
"""

import json
import re
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

YEARS = list(range(2017, 2026))  # years to scrape (inclusive)
MAX_WEEKS = 28  # maximum weeks per year to attempt

# URL template for weekly CSA recipe pages
BASE_URL_TEMPLATE = "https://front9farm.com/index.php/{year}-csa-week-{week}-recipes"

# Output file names
CSA_HAULS_FILE = "csa_hauls.json"
CSA_RECIPES_FILE = "csa_recipes.json"

# Image path templates
CSA_IMAGE_TEMPLATE = "assets/imgs/csa/{year}/csa_haul_{year}_{week}.jpg"
RECIPE_IMAGE_TEMPLATE = "assets/imgs/recipes/{year}/csa_recipe_{year}_{week}_{index}.jpg"


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def clean_name(text: str) -> str:
    """
    Normalize item names by removing parentheses, numbers and common
    measurement words, converting to lower case, and replacing spaces with
    underscores.

    :param text: Raw item name from the table header
    :return: Sanitized identifier suitable as an alias
    """
    t = text.strip().lower()
    t = re.sub(r"\(.*?\)", "", t)  # remove parenthetical text
    t = re.sub(r"\d+", "", t)  # remove digits
    t = t.replace(",", " ").replace("/", " ")
    drop_words = {
        "about", "g", "lb", "lbs", "quart", "cup", "cups",
        "tsp", "tbsp", "pinches", "large", "small", "medium",
        "clove", "cloves", "of",
    }
    adjective_drop = {"baby"}
    words = [w for w in t.split() if w not in drop_words and w not in adjective_drop]
    normalized = "_".join(words).strip("_")
    return normalized


def get_first_monday_in_may(year: int) -> date:
    """Return the date of the first Monday in May for a given year."""
    d = date(year, 5, 1)
    while d.weekday() != 0:
        d += timedelta(days=1)
    return d


def compute_time_stamp(year: int, week: int) -> str:
    """Return a timestamp string (YYYY_MM_DD) for a given year and week."""
    first_monday = get_first_monday_in_may(year)
    week_date = first_monday + timedelta(days=7 * (week - 1))
    return week_date.strftime("%Y_%m_%d")


def fetch_page(year: int, week: int) -> Optional[BeautifulSoup]:
    """Fetch and parse a CSA week page. Return None if unavailable."""
    url = BASE_URL_TEMPLATE.format(year=year, week=week)
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code != 200:
            return None
        return BeautifulSoup(resp.text, "html.parser")
    except Exception:
        return None


def find_csa_and_ingredient_tables(soup: BeautifulSoup) -> Optional[Tuple[BeautifulSoup, BeautifulSoup]]:
    """
    Locate the two recipe tables on the page: the CSA contents table and
    the ingredients table.  Tables are identified by having a header row
    with at least three non‑empty `<td>` elements (recipe names).

    :param soup: Parsed HTML soup
    :return: (csa_table, ingredients_table) or None if not found
    """
    candidates: List[BeautifulSoup] = []
    for table in soup.find_all("table"):
        tr = table.find("tr")
        if not tr:
            continue
        td_texts = [td.get_text(strip=True) for td in tr.find_all("td") if td.get_text(strip=True)]
        if len(td_texts) >= 3:
            candidates.append(table)
    if len(candidates) < 2:
        return None
    return candidates[0], candidates[1]


def extract_recipe_names(table: BeautifulSoup) -> List[str]:
    """Return the list of recipe names from the first row of a table."""
    tr = table.find("tr")
    if not tr:
        return []
    names = [td.get_text(strip=True) for td in tr.find_all("td") if td.get_text(strip=True)]
    return names


def extract_row_labels(table: BeautifulSoup) -> List[str]:
    """Return cleaned row labels (from `<th>` elements) for a table."""
    labels: List[str] = []
    for tr in table.find_all("tr")[1:]:
        th = tr.find("th")
        if not th:
            continue
        label = clean_name(th.get_text(strip=True))
        if label:
            labels.append(label)
    return labels


def extract_usage_matrix(table: BeautifulSoup) -> List[List[bool]]:
    """
    Build a boolean matrix indicating which items or ingredients are used
    for each recipe.  A cell evaluates to True if it contains any text.
    """
    matrix: List[List[bool]] = []
    for tr in table.find_all("tr")[1:]:
        cells = tr.find_all(["td", "th"])
        usage_row: List[bool] = []
        for cell in cells[1:]:  # skip row label cell
            usage_row.append(bool(cell.get_text(strip=True)))
        matrix.append(usage_row)
    return matrix


def extract_recipe_instructions(soup: BeautifulSoup, recipe_name: str) -> List[str]:
    """
    Find paragraphs associated with a recipe.  The function searches for
    heading tags with text matching the recipe name and returns subsequent
    `<p>` texts until the next heading.
    """
    target = recipe_name.strip().lower()
    headings = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
    for h in headings:
        if h.get_text(strip=True).lower() == target:
            paragraphs: List[str] = []
            for sibling in h.find_all_next():
                if sibling.name and sibling.name.startswith("h") and sibling.name[1:].isdigit():
                    break
                if sibling.name == "p":
                    text = sibling.get_text(strip=True)
                    if text:
                        paragraphs.append(text)
            return paragraphs
    return []


def extract_haul_intro(soup: BeautifulSoup) -> Optional[str]:
    """
    Attempt to extract a welcome or introductory message for the weekly haul.
    The function checks for a heading containing the word "week" before the
    first table, falling back to the first `<p>` before the table if
    necessary.  Returns None if no message can be extracted.
    """
    tables = soup.find_all("table")
    if not tables:
        return None
    first_table = tables[0]
    for tag in first_table.find_all_previous():
        if tag.name and tag.name.lower() in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            text = tag.get_text(strip=True)
            if "week" in text.lower():
                return text
    for tag in first_table.find_all_previous():
        if tag.name == "p":
            return tag.get_text(strip=True)
    return None


# ---------------------------------------------------------------------------
# Scraping functions
# ---------------------------------------------------------------------------

def scrape_week(year: int, week: int) -> Optional[Tuple[Dict, List[Dict]]]:
    """
    Scrape a CSA week page and return both haul and recipe data.  If the
    page is missing or malformed, return None.

    :param year: Year of the CSA
    :param week: Week number (1‑based)
    :return: (haul_entry, recipe_entries) or None
    """
    soup = fetch_page(year, week)
    if soup is None:
        return None
    tables = find_csa_and_ingredient_tables(soup)
    if not tables:
        return None
    csa_table, ing_table = tables
    recipe_names = extract_recipe_names(csa_table)
    if not recipe_names:
        return None
    csa_labels = extract_row_labels(csa_table)
    ing_labels = extract_row_labels(ing_table)
    csa_usage = extract_usage_matrix(csa_table)
    ing_usage = extract_usage_matrix(ing_table)
    time_stamp = compute_time_stamp(year, week)
    haul_entry: Dict = {
        "time_stamp": time_stamp,
        "title": f"csa_haul_{year}_{week}",
        "alias": f"{year} CSA Week {week}",
        "picture": CSA_IMAGE_TEMPLATE.format(year=year, week=week),
        "csa_items": [
            {"product_id": "leave_empty", "alias": item} for item in csa_labels
        ],
    }
    intro = extract_haul_intro(soup)
    if intro:
        haul_entry["message"] = intro
    recipe_entries: List[Dict] = []
    for idx, name in enumerate(recipe_names):
        used_csa_items: List[Dict[str, str]] = []
        for label, usage_row in zip(csa_labels, csa_usage):
            if idx < len(usage_row) and usage_row[idx]:
                used_csa_items.append(
                    {"product_id": "leave_empty", "alias": label}
                )
        used_ingredients: List[Dict[str, str]] = []
        for label, usage_row in zip(ing_labels, ing_usage):
            if idx < len(usage_row) and usage_row[idx]:
                used_ingredients.append(
                    {"product_id": "leave_empty", "alias": label}
                )
        paragraphs = extract_recipe_instructions(soup, name)
        if paragraphs:
            message_dict = {f"paragraph_{i+1}": p for i, p in enumerate(paragraphs)}
            message_list = [message_dict]
        else:
            message_list = []
        entry: Dict = {
            "alias": name,
            "picture": RECIPE_IMAGE_TEMPLATE.format(year=year, week=week, index=idx + 1),
            "csa_items": used_csa_items,
            "ingredients": used_ingredients,
        }
        if message_list:
            entry["message"] = message_list
        recipe_entries.append(entry)
    return haul_entry, recipe_entries


def build_recipe_lookup(existing: Optional[Dict]) -> Dict[str, str]:
    """Build a mapping from recipe alias to recipe_id from existing data."""
    lookup: Dict[str, str] = {}
    if existing and "csa_recipes" in existing:
        for rec in existing["csa_recipes"]:
            alias = rec.get("alias")
            rid = rec.get("recipe_id")
            if alias and rid:
                lookup[alias] = rid
    return lookup


def assign_recipe_ids(entries: List[Dict], lookup: Dict[str, str], start_counter: int) -> int:
    """
    Assign sequential recipe IDs to entries, reusing existing IDs when
    possible.  Returns the next available counter after assignment.
    """
    counter = start_counter
    for entry in entries:
        alias = entry["alias"]
        if alias in lookup:
            entry["recipe_id"] = lookup[alias]
        else:
            entry["recipe_id"] = f"{counter:03d}"
            lookup[alias] = entry["recipe_id"]
            counter += 1
    return counter


def main() -> None:
    # Load existing recipes to preserve IDs across runs
    try:
        existing_recipes = json.load(open(CSA_RECIPES_FILE, "r", encoding="utf-8"))
    except Exception:
        existing_recipes = None
    lookup = build_recipe_lookup(existing_recipes)
    next_counter = (
        max((int(v) for v in lookup.values()), default=0) + 1 if lookup else 1
    )
    hauls: List[Dict] = []
    recipes: List[Dict] = []
    for year in YEARS:
        for week in range(1, MAX_WEEKS + 1):
            result = scrape_week(year, week)
            if not result:
                continue
            haul, recipe_entries = result
            hauls.append(haul)
            next_counter = assign_recipe_ids(recipe_entries, lookup, next_counter)
            recipes.extend(recipe_entries)
    with open(CSA_HAULS_FILE, "w", encoding="utf-8") as f:
        json.dump({"csa_hauls": hauls}, f, indent=2)
    with open(CSA_RECIPES_FILE, "w", encoding="utf-8") as f:
        json.dump({"csa_recipes": recipes}, f, indent=2)
    print(
        f"Finished scraping: {len(hauls)} haul entries and {len(recipes)} recipes written."
    )


if __name__ == "__main__":
    main()
