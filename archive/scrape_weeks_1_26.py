import json
import re
import time
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://front9farm.com/index.php/2017-csa-week-{}-recipes"
WEEKS = range(1, 27)  # 1 through 26 inclusive


def clean_name(text: str) -> str:
    """
    Normalize an item name like:
      'Baby oakleaf lettuce (about 96g)' -> 'oakleaf_lettuce'
      'Chicken breast (2-3 lb)'          -> 'chicken_breast'
    Rules:
      - lowercase
      - remove text in parentheses
      - remove digits
      - remove some filler/measurement words
      - replace spaces with underscores
      - strip stray punctuation/underscores

    You can tighten/relax the drop_words set if needed after seeing output.
    """
    t = text.strip().lower()

    # Remove text in parentheses: "(about 96g)"
    t = re.sub(r"\(.*?\)", "", t)

    # Remove digits
    t = re.sub(r"\d+", "", t)

    # Replace commas and slashes with spaces
    t = t.replace(",", " ").replace("/", " ")

    # Words we want to drop (tweak this as you inspect more data)
    drop_words = {
        "about", "g", "lb", "lbs", "quart", "cup", "cups",
        "tsp", "tbsp", "pinches", "large", "small", "medium",
        "clove", "cloves", "of"
        # NOTE: we intentionally do NOT drop "potato"/"potatoes" so we can get russet_potato.
    }

    # Optional adjectives to drop (e.g., "baby oakleaf lettuce" -> "oakleaf lettuce")
    adjective_drop = {"baby"}

    words = t.split()
    kept = []
    for w in words:
        if w in drop_words or w in adjective_drop:
            continue
        kept.append(w)

    t = "_".join(kept)
    t = t.strip("_")
    return t


def get_soup_for_week(week: int) -> BeautifulSoup:
    url = BASE_URL.format(week)
    print(f"Fetching week {week}: {url}")
    resp = requests.get(url)
    # If the page doesn't exist or errors, this will raise
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def find_csa_and_ingredient_tables(soup: BeautifulSoup):
    """
    Generalized version of your week-1 logic:

    - We look for tables whose first row is a header row with multiple <td> entries
      (the recipe names).
    - On these CSA pages there should be exactly 2 such tables:
        1) CSA contents table
        2) Extra ingredients table
    - We treat:
        first  -> CSA table
        second -> ingredients table

    If this assumption breaks for a specific week, you’ll see an error printed.
    """
    candidate_tables = []

    for table in soup.find_all("table"):
        first_row = table.find("tr")
        if not first_row:
            continue

        tds = first_row.find_all("td")
        # Collect texts of non-empty <td> cells
        td_texts = [td.get_text(strip=True) for td in tds if td.get_text(strip=True)]

        # Heuristic: header row with multiple recipe names tends to have >= 3 non-empty td cells
        if len(td_texts) >= 3:
            candidate_tables.append(table)

    if len(candidate_tables) != 2:
        raise RuntimeError(
            f"Expected 2 recipe-header-style tables, found {len(candidate_tables)}"
        )

    csa_table = candidate_tables[0]
    ingredients_table = candidate_tables[1]
    return csa_table, ingredients_table


def extract_recipes_from_header_row(table) -> list:
    """
    From the first row of the table, grab recipe names from the <td> cells.

    Row shape:
      <td></td>
      <td>Recipe 1</td>
      <td>Recipe 2</td>
      ...
    We ignore the first empty cell.
    """
    first_row = table.find("tr")
    if not first_row:
        return []

    tds = first_row.find_all("td")
    recipes = [td.get_text(strip=True) for td in tds if td.get_text(strip=True)]
    return recipes


def extract_csa_items(csa_table) -> list:
    """
    CSA items come from the <th> cells in the first table (excluding the header row).
    For each row, we take the text of the <th> in column 0.
    """
    items = []
    rows = csa_table.find_all("tr")[1:]  # skip header row
    for tr in rows:
        th = tr.find("th")
        if not th:
            continue
        raw = th.get_text(strip=True)
        cleaned = clean_name(raw)
        if cleaned:
            items.append(cleaned)
    return items


def extract_ingredients(ingredients_table) -> list:
    """
    Ingredients come from the <th> cells in the second table (excluding the header row).
    Similar logic to extract_csa_items.
    """
    items = []
    rows = ingredients_table.find_all("tr")[1:]  # skip header row
    for tr in rows:
        th = tr.find("th")
        if not th:
            continue
        raw = th.get_text(strip=True)
        cleaned = clean_name(raw)
        if cleaned:
            items.append(cleaned)
    return items


def scrape_week(week: int) -> dict | None:
    """
    Scrape a single week.
    Returns a dict of the form:

    {
      "url": ...,
      "csa_items": [...],
      "recipes": [...],
      "ingredients": [...]
    }

    or None if something goes wrong (404 or unexpected structure).
    """
    try:
        soup = get_soup_for_week(week)
    except Exception as e:
        print(f"  [ERROR] Week {week}: HTTP error: {e}")
        return None

    try:
        csa_table, ingredients_table = find_csa_and_ingredient_tables(soup)
    except Exception as e:
        print(f"  [ERROR] Week {week}: table structure error: {e}")
        return None

    recipes = extract_recipes_from_header_row(csa_table)
    csa_items = extract_csa_items(csa_table)
    ingredients = extract_ingredients(ingredients_table)

    url = BASE_URL.format(week)
    return {
        "url": url,
        "csa_items": csa_items,
        "recipes": recipes,
        "ingredients": ingredients,
    }


def main():
    data = {}

    for week in WEEKS:
        print(f"\n=== WEEK {week} ===")
        week_data = scrape_week(week)
        if week_data is None:
            print(f"  Skipping week {week} due to errors.")
            continue

        key = f"2017_week_{week}"
        data[key] = week_data

        # be polite to the server
        time.sleep(1)

    # Write everything to a JSON file
    output_file = "csa_2017_weeks_1_26.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"\nDone. Wrote {len(data)} weeks to {output_file}")


if __name__ == "__main__":
    main()
