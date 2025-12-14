import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

HAULS_IN = Path("csa_hauls.json")
HAULS_OUT = Path("csa_hauls.with_string_refs.json")

STRINGS_IN = Path("strings.json")
STRINGS_OUT = Path("strings.json")  # we overwrite safely by writing temp then replace

TMP_STRINGS = Path("strings.json.tmp")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def load_existing_strings() -> Tuple[Dict[str, str], Dict[str, str], int]:
    """
    Returns:
      - id_to_text: {"string_1": "...", ...}
      - text_to_id: {"...": "string_1", ...}
      - next_index: next numeric index to allocate (int)
    Accepts either:
      {"strings": [{"string_1": "..."}, {"string_2": "..."}]}
    or a more direct:
      {"strings": {"string_1": "...", "string_2": "..."}}
    """
    if not STRINGS_IN.exists():
        return {}, {}, 1

    data = load_json(STRINGS_IN)
    strings = data.get("strings")

    id_to_text: Dict[str, str] = {}

    if isinstance(strings, dict):
        # {"strings": {"string_1": "..."}}
        for k, v in strings.items():
            if isinstance(k, str) and isinstance(v, str):
                id_to_text[k] = v

    elif isinstance(strings, list):
        # {"strings": [{"string_1": "..."}, ...]}
        for entry in strings:
            if isinstance(entry, dict) and len(entry) == 1:
                k, v = next(iter(entry.items()))
                if isinstance(k, str) and isinstance(v, str):
                    id_to_text[k] = v

    # Build reverse lookup
    text_to_id = {v: k for k, v in id_to_text.items()}

    # Determine next index
    max_n = 0
    for sid in id_to_text.keys():
        if sid.startswith("string_"):
            try:
                n = int(sid.split("_", 1)[1])
                max_n = max(max_n, n)
            except ValueError:
                pass

    return id_to_text, text_to_id, max_n + 1


def alloc_string_id(next_index: int) -> str:
    return f"string_{next_index}"


def normalize_hauls_structure(data: Any) -> List[Dict[str, Any]]:
    """
    Accepts either:
      {"csa_hauls": [ ... ]}
    or:
      [ ... ]
    Returns the list of haul dicts.
    """
    if isinstance(data, dict) and "csa_hauls" in data:
        hauls = data["csa_hauls"]
    else:
        hauls = data

    if not isinstance(hauls, list):
        raise ValueError("Expected csa_hauls.json to be a list or {'csa_hauls': [...]}.")

    # Only keep dict entries (skip anything malformed)
    return [h for h in hauls if isinstance(h, dict)]


def main() -> None:
    if not HAULS_IN.exists():
        raise FileNotFoundError(f"Missing {HAULS_IN} in current directory.")

    raw = load_json(HAULS_IN)
    hauls = normalize_hauls_structure(raw)

    id_to_text, text_to_id, next_index = load_existing_strings()

    # Process each haul in order
    for haul in hauls:
        msg = haul.get("message")

        # If already a string reference like "string_5", leave it alone
        if isinstance(msg, str) and msg.startswith("string_"):
            continue

        # If message is missing or not a string, skip
        if not isinstance(msg, str):
            continue

        msg_clean = msg.strip()
        if not msg_clean:
            # empty message -> drop or leave as is; here we remove it
            haul["message"] = ""
            continue

        # Reuse existing ID if identical message already stored
        existing_id = text_to_id.get(msg_clean)
        if existing_id:
            haul["message"] = existing_id
            continue

        # Allocate new ID
        new_id = alloc_string_id(next_index)
        next_index += 1

        id_to_text[new_id] = msg_clean
        text_to_id[msg_clean] = new_id

        # Replace message with reference
        haul["message"] = new_id

    # Write updated hauls to output (non-destructive)
    if isinstance(raw, dict) and "csa_hauls" in raw:
        out_hauls_obj = {"csa_hauls": hauls}
    else:
        out_hauls_obj = hauls

    write_json(HAULS_OUT, out_hauls_obj)

    # Write strings.json in your requested format:
    # { "strings": [ {"string_1": "..."}, {"string_2": "..."} ] }
    # sorted by numeric id
    def sid_key(sid: str) -> int:
        try:
            return int(sid.split("_", 1)[1])
        except Exception:
            return 10**9

    strings_list = [{sid: id_to_text[sid]} for sid in sorted(id_to_text.keys(), key=sid_key)]
    strings_obj = {"strings": strings_list}

    write_json(TMP_STRINGS, strings_obj)
    TMP_STRINGS.replace(STRINGS_OUT)

    print(f"Wrote updated hauls to: {HAULS_OUT}")
    print(f"Wrote strings to: {STRINGS_OUT}")
    print(f"Total unique strings stored: {len(strings_list)}")


if __name__ == "__main__":
    main()
