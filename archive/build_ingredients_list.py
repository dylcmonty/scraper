import json
import os

SOURCE_FILE = "csa_recipes.json"
INGREDIENTS_FILE = "ingredients.json"


def load_source_data():
    """
    Load csa_recipes.json and return the list of recipe objects.

    Expected structure:
    {
      "csa_recipes": [
        {
          "recipe_id": "...",
          "alias": "...",
          "csa_items": [
            {"product_id": "leave_empty", "alias": "lovage"},
            ...
          ],
          "ingredients": [
            {"product_id": "leave_empty", "alias": "olive_oil"},
            ...
          ],
          ...
        },
        ...
      ]
    }

    If the top-level is already a list, we just return it.
    """
    with open(SOURCE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return data

    return data.get("csa_recipes", [])


def load_existing_ingredients():
    """
    Load ingredients.json if it already exists, otherwise return an empty structure.

    We support both old field name 'ingredient_id' and new 'ingredients_id'
    when reading, but will write back using 'ingredients_id'.
    """
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
    Build a lookup dict: alias → ingredients_id.

    This allows stable IDs even across multiple runs. We accept both
    'ingredient_id' and 'ingredients_id' from any existing file.
    """
    lookup = {}
    for entry in existing_data.get("ingredients", []):
        if "ingredients_id" in entry:
            ingredients_id = entry["ingredients_id"]
        else:
            # Backwards compatibility with any older file
            ingredients_id = entry.get("ingredient_id")
        alias = entry.get("alias")
        if alias and ingredients_id:
            lookup[alias] = ingredients_id
    return lookup


def next_id(existing_lookup):
    """Generate the next 3-digit ID as a string ('001', '002', ...)."""
    if not existing_lookup:
        return "001"
    nums = [int(v) for v in existing_lookup.values()]
    new_num = max(nums) + 1
    return f"{new_num:03d}"


def main():
    # Step 1: Load source recipes and any existing ingredients file
    recipes = load_source_data()
    existing = load_existing_ingredients()

    # Step 2: Build lookup of existing ingredients (alias → id)
    lookup = build_lookup(existing)

    # Step 3: Gather new ingredient aliases from recipes
    all_new_ingredients = set()

    for recipe in recipes:
        for ing in recipe.get("ingredients", []):
            alias = ing.get("alias")
            if not alias:
                continue
            all_new_ingredients.add(alias)

    # Step 4: Add new ingredient aliases to lookup with fresh IDs
    for alias in sorted(all_new_ingredients):
        if alias not in lookup:
            lookup[alias] = next_id(lookup)

    # Step 5: Convert lookup into final JSON structure
    final_list = []
    # Sort by numeric ID
    for alias, ingredients_id in sorted(
        lookup.items(), key=lambda x: int(x[1])
    ):
        final_list.append(
            {
                "ingredients_id": ingredients_id,
                "alias": alias,
            }
        )

    final_dict = {"ingredients": final_list}

    # Step 6: Write out the updated file
    with open(INGREDIENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(final_dict, f, indent=2)

    print(
        f"Completed. Indexed {len(final_list)} unique ingredients into {INGREDIENTS_FILE}."
    )


if __name__ == "__main__":
    main()
