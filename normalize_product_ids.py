import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

INPUT_FILE = Path("csa_hauls.json")
OUTPUT_FILE = Path("csa_hauls.normalized.json")

# Set to True if you want duplicates removed (preserves first occurrence order)
DEDUPLICATE = False


def normalize_product_id_item(item: Any) -> Tuple[str | None, str | None]:
    """
    Returns (normalized_value, error_message).
    Normalized value is always a string or None if item can't be normalized.
    """
    # Case 1: already a string
    if isinstance(item, str):
        val = item.strip()
        return (val if val else None), None

    # Case 2: number -> string
    if isinstance(item, (int, float)):
        # You likely only want ints, but we'll stringify safely.
        # Convert 5.0 -> "5" if it is integer-like.
        if isinstance(item, float) and item.is_integer():
            return str(int(item)), None
        return str(item), None

    # Case 3: dict-shaped entries
    if isinstance(item, dict):
        product_id = item.get("product_id")
        alias = item.get("alias")

        # If product_id is present and not the placeholder, use it.
        if isinstance(product_id, (str, int)):
            pid_str = str(product_id).strip()
            if pid_str and pid_str.lower() != "leave_empty":
                return pid_str, None

        # If product_id is leave_empty, use alias.
        if isinstance(alias, str):
            a = alias.strip()
            if a:
                return a, None

        # Fallback: if dict has only one key with a value, try that
        for v in item.values():
            if isinstance(v, str) and v.strip():
                return v.strip(), "Used fallback dict value (no product_id/alias)."

        return None, "Dict missing usable product_id/alias."

    return None, f"Unsupported type: {type(item)}"


def dedupe_preserve_order(items: List[str]) -> List[str]:
    seen = set()
    out = []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def main() -> None:
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Missing {INPUT_FILE} in current directory.")

    data = json.loads(INPUT_FILE.read_text(encoding="utf-8"))

    # Accept either {"csa_hauls":[...]} or a direct list
    hauls = data.get("csa_hauls") if isinstance(data, dict) else data
    if not isinstance(hauls, list):
        raise ValueError("Expected csa_hauls.json to contain a list or {'csa_hauls': [...]}.")

    warnings: List[Dict[str, Any]] = []

    for haul in hauls:
        if not isinstance(haul, dict):
            continue

        if "product_ids" not in haul:
            continue

        raw = haul["product_ids"]
        if not isinstance(raw, list):
            warnings.append({
                "title": haul.get("title"),
                "issue": "product_ids is not a list; skipping",
                "value_type": str(type(raw))
            })
            continue

        normalized: List[str] = []
        for idx, item in enumerate(raw):
            val, err = normalize_product_id_item(item)
            if val is not None:
                normalized.append(val)
            else:
                warnings.append({
                    "title": haul.get("title"),
                    "index": idx,
                    "issue": err or "Unknown normalization failure",
                    "original": item
                })

        if DEDUPLICATE:
            normalized = dedupe_preserve_order(normalized)

        haul["product_ids"] = normalized

    # Write output in same top-level shape as input
    if isinstance(data, dict) and "csa_hauls" in data:
        out_data = {"csa_hauls": hauls}
    else:
        out_data = hauls

    OUTPUT_FILE.write_text(json.dumps(out_data, indent=2), encoding="utf-8")

    print(f"Normalized file written to: {OUTPUT_FILE}")
    if warnings:
        print(f"\nWarnings ({len(warnings)}):")
        for w in warnings[:25]:
            print(json.dumps(w, ensure_ascii=False))
        if len(warnings) > 25:
            print(f"... plus {len(warnings) - 25} more warnings.")


if __name__ == "__main__":
    main()

