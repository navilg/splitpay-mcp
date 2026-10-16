"""Compact text serialization for MCP tool results."""

import csv
from io import StringIO


def to_tsv(rows: list[dict[str, str]], columns: tuple[str, ...]) -> str:
    """Serialize flat records with a stable header, including empty results."""
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=columns, delimiter="\t", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().rstrip("\n")