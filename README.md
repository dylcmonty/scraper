# Scrapper

## Quick safety & etiquette checklist
Before scraping any website, you should:
1. Check robots.txt
 - Example: https://front9farm.com/robots.txt
 - If it explicitly disallows scraping certain paths, you should respect that.
2. Don’t hammer the server
  - Add a short time.sleep(1) between requests.
3. Keep it small and reasonable

## Tools used
We’ll use Python plus two very common libraries:
  - `requests` – to download the HTML.
  - `beautifulsoup4` – to parse the HTML and pull out tables.
On linux run:
```bash
sudo apt-get update
sudo apt-get install python3 python3-pip -y

pip3 install requests beautifulsoup4
```
Optionally use a virtualenv

## Applying it to the CSA pattern
Each page 2017-csa-week-#-recipes has:
  - Table with CSA contents (week’s share).
  - Table with recipe names.
  - Table with additional ingredients.
The exact HTML order might be 2 or 3 tables; the safest approach is:
  - Grab all tables.
  - Print them once to see which index is which.
  - Then lock in those indexes in code.

## Test scraper for CSA data
Save this as scrape_week1.py:
```python
import requests

url = "https://front9farm.com/index.php/2017-csa-week-1-recipes"
html_file = "week1.html"

response = requests.get(url)
response.raise_for_status()

with open(html_file, "w", encoding=response.encoding or "utf-8") as f:
    f.write(response.text)

print(f"Saved HTML for Week 1 to {html_file}")
```
Run it with `python parse_week1.py`

Open the file: `xdg-open week1.html`

## Test parser for CSA data
Save this as parse_week1.py:
```python
import json
import re
from bs4 import BeautifulSoup

URL_WEEK_1 = "https://front9farm.com/index.php/2017-csa-week-1-recipes"
HTML_FILE = "week1.html"


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
        "clove", "cloves", "russets", "potatoes", "potato",
        "of"
    }

    # Optionally drop adjectives like "baby" if you want to match your hand data
    # e.g. "baby oakleaf lettuce" -> "oakleaf lettuce"
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


def load_soup(html_file: str) -> BeautifulSoup:
    with open(html_file, "r", encoding="utf-8") as f:
        html = f.read()
    return BeautifulSoup(html, "html.parser")


def find_week1_tables(soup: BeautifulSoup):
    """
    Find the two tables that match the snippet you pasted:
    Both have a header row whose <td> cells include 'Lovage Soup'.
    We treat:
      - first such table  -> CSA contents
      - second such table -> extra ingredients
    """
    target_tables = []

    for table in soup.find_all("table"):
        first_row = table.find("tr")
        if not first_row:
            continue
        row_text = first_row.get_text(separator=" ", strip=True)
        if "Lovage Soup" in row_text:
            target_tables.append(table)

    if len(target_tables) != 2:
        raise RuntimeError(f"Expected 2 tables with 'Lovage Soup', found {len(target_tables)}")

    csa_table = target_tables[0]
    ingredients_table = target_tables[1]
    return csa_table, ingredients_table


def extract_recipes_from_header_row(table) -> list[str]:
    """
    From the first row of the table, grab recipe names from the <td> cells.
    This row looks like:
      <td></td>
      <td>Lovage Soup</td>
      <td>Spring Greens Salad</td>
      ...
    We ignore the first empty cell.
    """
    first_row = table.find("tr")
    if not first_row:
        return []

    tds = first_row.find_all("td")
    recipes = [td.get_text(strip=True) for td in tds if td.get_text(strip=True)]
    return recipes


def extract_csa_items(csa_table) -> list[str]:
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


def extract_ingredients(ingredients_table) -> list[str]:
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


def main():
    soup = load_soup(HTML_FILE)
    csa_table, ingredients_table = find_week1_tables(soup)

    recipes = extract_recipes_from_header_row(csa_table)
    csa_items = extract_csa_items(csa_table)
    ingredients = extract_ingredients(ingredients_table)

    data = {
        "2017_week_1": {
            "url": URL_WEEK_1,
            "csa_items": csa_items,
            "recipes": recipes,
            # if you really want to match your previous key spelling:
            # "ingrediants": ingredients
            "ingredients": ingredients,
        }
    }

    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
```
Run it with `python parse_week1.py`

Make sure the Json properly output in the terminal.

Then dial it in for weeks 1-26
