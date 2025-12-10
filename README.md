# Scrapper

## Quick safety & etiquette checklist
Before scraping any website, you should:
1. Check robots.txt
 - Example: https://front9farm.com/robots.txt
 - If it explicitly disallows scraping certain paths, you should respect that.
2. Don’t hammer the server
  - Add a short time.sleep(1) between requests.
3. Keep it small and reasonable

## Tools you’ll use
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

## Minimal scraping example (one page)
Here’s a minimal “hello, scraper” to show the idea.
```python
import requests
from bs4 import BeautifulSoup

url = "https://front9farm.com/index.php/2017-csa-week-1-recipes"
resp = requests.get(url)
resp.raise_for_status()  # will error if the request failed

soup = BeautifulSoup(resp.text, "html.parser")

# Find all tables on the page
tables = soup.find_all("table")
print(f"Found {len(tables)} tables on {url}")

# Print the text of each row in the first table
if tables:
    first_table = tables[0]
    for row in first_table.find_all("tr"):
        cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
        print(cells)
```
Run with:
```bash
python3 test_scrape.py
```
You’ll see the first table’s rows printed out. That’s the core of scraping: fetch → parse → extract.

## Applying it to the CSA pattern
Each page 2017-csa-week-#-recipes has:
  - Table with CSA contents (week’s share).
  - Table with recipe names.
  - Table with additional ingredients.
The exact HTML order might be 2 or 3 tables; the safest approach is:
  - Grab all tables.
  - Print them once to see which index is which.
  - Then lock in those indexes in code.

## A scraper tailored to your CSA data
Save this as scrape_csa.py:
```python
import csv
import time
import re
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://front9farm.com/index.php/2017-csa-week-{}-recipes"

# Weeks you still need
WEEKS = list(range(10, 27))  # 10–26 inclusive

def clean_item(text: str) -> str:
    """
    Normalize ingredient or produce name like you did manually:
    - lowercase
    - remove commas and parentheses text
    - remove extra measurement words/numbers (roughly)
    - spaces -> underscores
    """
    text = text.strip().lower()

    # remove text in parentheses
    text = re.sub(r"\(.*?\)", "", text)

    # remove numbers and common measurement words
    # (you can refine this list as you see patterns)
    measurement_words = [
        "cup", "cups", "tbsp", "tablespoon", "tablespoons",
        "tsp", "teaspoon", "teaspoons", "pound", "pounds",
        "oz", "ounce", "ounces", "clove", "cloves", "bunch",
        "head", "heads", "large", "small", "medium"
    ]
    # remove digits
    text = re.sub(r"\d+", "", text)

    # remove commas and periods
    text = text.replace(",", " ").replace(".", " ")

    # remove measurement words
    parts = text.split()
    parts = [p for p in parts if p not in measurement_words]

    # collapse multiple spaces
    text = " ".join(parts)

    # spaces -> underscores
    text = text.replace(" ", "_")

    # strip stray underscores
    text = text.strip("_")

    return text


def extract_tables(url: str):
    """Download page and return all tables as list-of-rows (each row is list-of-cell-text)."""
    resp = requests.get(url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    tables_data = []
    for table in soup.find_all("table"):
        rows_data = []
        for row in table.find_all("tr"):
            cells = row.find_all(["td", "th"])
            row_text = [c.get_text(strip=True) for c in cells]
            # skip empty rows
            if any(row_text):
                rows_data.append(row_text)
        if rows_data:
            tables_data.append(rows_data)
    return tables_data


def get_csa_data_for_week(week: int):
    url = BASE_URL.format(week)
    print(f"Scraping week {week}: {url}")
    tables = extract_tables(url)

    if len(tables) < 2:
        raise ValueError(f"Unexpected table structure on {url}: found {len(tables)} tables")

    # --- Step 1: inspect for one week manually ---
    # For your first run, uncomment this block to see what's what:
    # for i, t in enumerate(tables):
    #     print(f"\n=== TABLE {i} ===")
    #     for row in t:
    #         print(row)
    # After you see the structure, set these indexes appropriately:

    # Here I'm *assuming*:
    # tables[0] -> CSA contents
    # tables[1] -> recipe names
    # tables[2] -> extra ingredients
    # If the site only has 2 tables, it might be:
    # 0 = CSA, 1 = extra ingredients, and recipe names come from headings instead.
    # Adjust as necessary after you inspect.

    csa_table_index = 0
    recipe_names_table_index = 1
    extra_ingredients_table_index = 2 if len(tables) > 2 else 1  # adjust if needed

    # CSA contents row(s)
    # Often it's a single row of items. Here we'll flatten all rows except header.
    csa_rows = tables[csa_table_index][1:]  # skip header row if present
    csa_items = []
    for row in csa_rows:
        for cell in row:
            if cell:
                csa_items.append(clean_item(cell))
    csa_items = [i for i in csa_items if i]  # remove empties

    # Recipe names:
    # If the recipe names table has a header then one row per recipe,
    # you might want to skip the header.
    recipe_rows = tables[recipe_names_table_index][1:]  # skip header
    recipe_names = []
    for row in recipe_rows:
        # sometimes a row may be [recipe_name] or [index, recipe_name]
        # so we take the last cell
        recipe_name = row[-1]
        recipe_names.append(recipe_name.strip())

    # Extra ingredients:
    extra_rows = tables[extra_ingredients_table_index][1:]  # skip header
    extra_items = []
    for row in extra_rows:
        for cell in row:
            if cell:
                extra_items.append(clean_item(cell))
    extra_items = [i for i in extra_items if i]

    return url, csa_items, recipe_names, extra_items


def main():
    # Write to a CSV file that you can merge with your existing one.
    # The layout here matches your pattern:
    # line 1: url
    # line 2: csa contents (comma separated)
    # line 3: recipe names
    # line 4: extra ingredients
    with open("csa_weeks_10_26_scraped.csv", "w", newline="") as f:
        writer = csv.writer(f)

        for week in WEEKS:
            try:
                url, csa_items, recipe_names, extra_items = get_csa_data_for_week(week)
            except Exception as e:
                print(f"Error on week {week}: {e}")
                continue

            # Line 1: URL (then empty columns to match your style)
            writer.writerow([url])

            # Line 2: CSA contents
            writer.writerow(csa_items)

            # Line 3: Recipe names (leave them as normal strings, not cleaned)
            writer.writerow(recipe_names)

            # Line 4: extra ingredients
            writer.writerow(extra_items)

            # Optional blank line between weeks for readability
            writer.writerow([])

            # Be polite to the server
            time.sleep(1)

    print("Done. See csa_weeks_10_26_scraped.csv")


if __name__ == "__main__":
    main()
```

## Dial it in
The one critical “tuning” step:
  - Run get_csa_data_for_week for a single week (e.g., 10).
  - Temporarily uncomment the “inspect tables” block:
```python
    # for i, t in enumerate(tables):
    #     print(f"\n=== TABLE {i} ===")
    #     for row in t:
    #         print(row)
```
  - Run the script for one week only (comment out others).
  - See which table index is CSA, which is recipes, which is extra ingredients.
  - Set:
```python
csa_table_index = ...
recipe_names_table_index = ...
extra_ingredients_table_index = ...
```
Once that’s correct for one week, it should be consistent for all weeks (if the site structure is consistent).
