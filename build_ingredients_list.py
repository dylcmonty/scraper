import json
import os

SOURCE_FILE = "csa_2017_weeks_1_26.json"
INGREDIENTS_FILE = "ingredients.json"


def load_source_data():
    """Load the CSA weeks JSON file."""
    with open(SOURCE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def load_existing_ingredients():
    """Load ingredients.json if it already exists, otherwise return an empty structure."""
    if not os.path.exists(INGREDIENTS_FILE):
        return {"ingredients": []}

    with open(INGREDIENTS_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            # Corrupted file or empty → start fresh
            return {"ingredients": []}


def build_lookup(existing_data):
    """
    Build a lookup dict: alias → ingredient_id.
    This allows stable IDs even across multiple runs.
    """
    lookup = {}
    for entry in existing_data.get("ingredients", []):
        lookup[entry["alias"]] = entry["ingredient_id"]
    return lookup


def next_id(existing_lookup):
    """Generate the next 3-digit ID."""
    if not existing_lookup:
        return "001"
    # Extract numeric parts
    nums = [int(v) for v in existing_lookup.values()]
    new_num = max(nums) + 1
    return f"{new_num:03d}"


def main():
    # Step 1: Load data
    source = load_source_data()
    existing = load_existing_ingredients()

    # Step 2: Build lookup of old ingredients
    lookup = build_lookup(existing)

    # Step 3: Gather new ingredients from source file
    all_new_ingredients = set()

    for week_key, week_obj in source.items():
        ing_list = week_obj.get("ingredients", [])
        for ing in ing_list:
            all_new_ingredients.add(ing)

    # Step 4: Add new ingredients to lookup
    for ing in sorted(all_new_ingredients):
        if ing not in lookup:
            lookup[ing] = next_id(lookup)

    # Step 5: Convert lookup back into the final JSON format
    final_list = []
    for alias, ingredient_id in sorted(lookup.items(), key=lambda x: int(x[1])):
        final_list.append({
            "ingredient_id": ingredient_id,
            "alias": alias
        })

    final_dict = {"ingredients": final_list}

    # Step 6: Write out the updated file
    with open(INGREDIENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(final_dict, f, indent=2)

    print(f"Completed. Indexed {len(final_list)} unique ingredients into {INGREDIENTS_FILE}.")


if __name__ == "__main__":
    main()
