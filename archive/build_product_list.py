import json
import os

SOURCE_FILE = "csa_hauls.json"
PRODUCTS_FILE = "product_list.json"


def load_source_data():
    """
    Load csa_hauls.json and return the list of haul objects.

    Expected structure:
    {
      "csa_hauls": [
        {
          "time_stamp": "...",
          "title": "...",
          "alias": "...",
          "picture": "...",
          "csa_items": [
            {"product_id": "leave_empty", "alias": "lovage"},
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

    return data.get("csa_hauls", [])


def load_existing_products():
    """
    Load product_list.json if it already exists, otherwise return an empty structure.
    """
    if not os.path.exists(PRODUCTS_FILE):
        return {"products": []}

    with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            # Corrupted file or empty → start fresh
            return {"products": []}


def build_lookup(existing_data):
    """
    Build a lookup dict: alias → product_id.

    This allows stable IDs across multiple runs.
    """
    lookup = {}
    for entry in existing_data.get("products", []):
        product_id = entry.get("product_id")
        alias = entry.get("alias")
        if alias and product_id:
            lookup[alias] = product_id
    return lookup


def next_id(existing_lookup):
    """Generate the next 3-digit ID as a string ('001', '002', ...)."""
    if not existing_lookup:
        return "001"
    nums = [int(v) for v in existing_lookup.values()]
    new_num = max(nums) + 1
    return f"{new_num:03d}"


def main():
    # Step 1: Load source hauls and existing product list
    hauls = load_source_data()
    existing = load_existing_products()

    # Step 2: Build lookup of existing products (alias → id)
    lookup = build_lookup(existing)

    # Step 3: Gather product aliases from all hauls' csa_items
    all_new_products = set()

    for haul in hauls:
        for item in haul.get("csa_items", []):
            alias = item.get("alias")
            if not alias:
                continue
            all_new_products.add(alias)

    # Step 4: Add new product aliases to lookup with fresh IDs
    for alias in sorted(all_new_products):
        if alias not in lookup:
            lookup[alias] = next_id(lookup)

    # Step 5: Convert lookup to final JSON structure
    final_list = []
    for alias, product_id in sorted(lookup.items(), key=lambda x: int(x[1])):
        final_list.append(
            {
                "product_id": product_id,
                "alias": alias,
            }
        )

    final_dict = {"products": final_list}

    # Step 6: Write out the updated file
    with open(PRODUCTS_FILE, "w", encoding="utf-8") as f:
        json.dump(final_dict, f, indent=2)

    print(
        f"Completed. Indexed {len(final_list)} unique products into {PRODUCTS_FILE}."
    )


if __name__ == "__main__":
    main()
