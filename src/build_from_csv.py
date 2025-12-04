from pathlib import Path
import msgspec
import polars as pl

from models.CustomData import ModConfig, ModEntry, parse_style, row_to_mod_entry

UPDATE_DURATION = 3600
NON_NAME_COLS = ["Beta", "Warning", "Badge", "Srcs", "BuiltIn", "Style"]
file = Path("ModsData.csv")
content = pl.read_csv(file, separator=",", has_header=True)
filtered = content.filter(
    pl.col("ModId").is_not_null()
    & (pl.col("ModId") != "")
    & pl.any_horizontal(
        [pl.col(c).is_not_null() & (pl.col(c) != "") for c in NON_NAME_COLS]
    )
)
splitted = filtered.with_columns(
    pl.when(pl.col("Srcs").is_not_null())
    .then(
        pl.col("Srcs")
        .str.split(";")
        .list.eval(pl.element().str.strip_chars())
        .list.eval(pl.element().filter(pl.element() != ""))
    )
    .otherwise(None)
    .alias("Srcs")
)
splitted = splitted.with_columns(
    pl.when(pl.col("Srcs").is_not_null() & (pl.col("Srcs").list.len() > 0))
    .then(True)
    .otherwise(pl.col("Badge"))
    .alias("Badge")
)
splitted = splitted.with_columns(
    pl.when(pl.col("Style").is_not_null() & (pl.col("Style") != ""))
    .then(pl.col("Style").map_elements(parse_style, return_dtype=pl.Object))
    .otherwise(None)
    .alias("Style")
)

mod_entries: list[ModEntry] = [row_to_mod_entry(row) for row in splitted.to_dicts()]
data_map = {e.id: e.data for e in mod_entries}
config = ModConfig(duration=UPDATE_DURATION, data=data_map)
json_bytes = msgspec.json.encode(config, order="sorted")
with open("CustomizableMenuData.json", "b+w") as f:
    f.write(json_bytes)
