import csv
import io
import json
from typing import Iterable, Mapping


def rows_to_csv(rows: Iterable[Mapping[str, object]]) -> str:
    rows = list(rows)
    output = io.StringIO()
    if not rows:
        return ""
    writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return output.getvalue()


def rows_to_json(rows: Iterable[Mapping[str, object]]) -> str:
    return json.dumps(list(rows), ensure_ascii=False, indent=2, default=str)
