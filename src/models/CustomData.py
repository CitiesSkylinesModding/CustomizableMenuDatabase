from typing import List, Optional
import msgspec


class Item(msgspec.Struct, omit_defaults=True):
    builtIn: bool | None = None


class CustomData(msgspec.Struct, omit_defaults=True):
    badge: bool | None = None
    srcs: List[str] | None = None
    style: dict | None = None
    beta: bool | None = None
    warning: bool | None = None
    item: Item | None = None


class ModEntry(msgspec.Struct, omit_defaults=True):
    id: str
    data: CustomData


class ModConfig(msgspec.Struct, omit_defaults=True):
    duration: int
    data: dict[str, CustomData]


def parse_style(s: str) -> dict:
    result: dict[str, object] = {}
    for part in s.split(";"):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            continue

        k, v = part.split("=", 1)
        k = k.strip()
        v = v.strip()

        if v.lower() in ("true", "false"):
            v = v.lower() == "true"
        else:
            try:
                v = int(v)
            except ValueError:
                try:
                    v = float(v)
                except ValueError:
                    pass

        result[k] = v

    return result


def row_to_mod_entry(row: dict) -> ModEntry:
    mod_id = row["ModId"]

    badge = row.get("Badge")
    beta = row.get("Beta")
    warning = row.get("Warning")
    srcs = row.get("Srcs")
    built_in = row.get("BuiltIn")
    style = row.get("Style")

    item: Item | None = None
    if built_in is not None:
        item = Item(builtIn=built_in)

    data = CustomData(
        badge=badge,
        srcs=srcs,
        style=style,
        beta=beta,
        warning=warning,
        item=item,
    )

    return ModEntry(id=mod_id, data=data)
