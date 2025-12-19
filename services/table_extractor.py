# services/table_extractor.py
from typing import List, Dict, Tuple, Optional
from PIL import Image
import pytesseract
import numpy as np


def _words_from_image(img: Image.Image, psm: int = 6) -> Dict:
    """
    Run image_to_data and return the dictionary result.
    """
    config = f"--psm {psm} --oem 3"
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT, config=config)
    return data


def _group_lines_by_y(data: Dict, y_tol: int = 12) -> List[List[int]]:
    """
    Group word indices into horizontal rows by 'top' coordinate proximity.
    Returns list of lists of indices (word index positions).
    """
    tops = []
    # build list of (idx, top, height, conf, text, left)
    entries = []
    n = len(data.get("text", []))
    for i in range(n):
        txt = data["text"][i].strip()
        if txt == "":
            continue
        entries.append({
            "i": i,
            "top": int(data["top"][i]),
            "height": int(data["height"][i]),
            "left": int(data["left"][i]),
            "conf": int(data["conf"][i]) if data["conf"][i] != '-1' else -1,
            "text": txt
        })

    if not entries:
        return []

    # sort entries by top then left
    entries.sort(key=lambda e: (e["top"], e["left"]))

    rows = []
    current_row = [entries[0]]
    for e in entries[1:]:
        if abs(e["top"] - current_row[-1]["top"]) <= y_tol:
            current_row.append(e)
        else:
            rows.append(current_row)
            current_row = [e]
    rows.append(current_row)

    # convert rows to index lists
    rows_idx = [[item["i"] for item in row] for row in rows]
    # But we also want access to full entries — return rows as list of entry dicts instead
    rows_entries = [[item for item in row] for row in rows]
    return rows_entries


def _find_header_columns(rows_entries: List[List[dict]], img_width: int) -> Optional[List[int]]:
    """
    Search rows for header keywords and return column x-boundaries list (left edges).
    Returns list of column left positions e.g. [x_item, x_qty, x_unit, x_price, x_total]
    """
    header_keywords = ["item", "description", "quantity", "qty", "unit", "price", "total", "unit price"]
    for row in rows_entries[:3]:  # header is typically in first three rows
        texts = " ".join([w["text"].lower() for w in row])
        if any(k in texts for k in ["item", "quantity", "unit price", "total"]):
            # sort row words by left
            row_sorted = sorted(row, key=lambda w: w["left"])
            # return list of left positions
            cols = [w["left"] for w in row_sorted]
            # ensure left extremes and add image width as last boundary
            cols_sorted = sorted(cols)
            # return boundaries by adding rightmost edge
            return cols_sorted
    return None


def _assign_words_to_columns(row: List[dict], col_boundaries: List[int], img_width: int) -> List[str]:
    """
    Given a single row (list of word dicts) and column left boundaries, return cell texts.
    We treat boundaries as list of left positions; last column uses img_width as right bound.
    """
    cols = []
    boundaries = sorted(col_boundaries)
    # build right bounds (midpoint between consecutive lefts), last right bound = img_width
    split_points = []
    for i in range(len(boundaries) - 1):
        mid = (boundaries[i] + boundaries[i + 1]) // 2
        split_points.append(mid)
    split_points.append(img_width)  # last boundary

    # initialize cells
    cell_texts = [""] * (len(boundaries))
    for w in sorted(row, key=lambda x: x["left"]):
        left = w["left"]
        # find column index
        col_idx = 0
        while col_idx < len(split_points) and left > split_points[col_idx]:
            col_idx += 1
        if col_idx >= len(cell_texts):
            col_idx = len(cell_texts) - 1
        if cell_texts[col_idx]:
            cell_texts[col_idx] += " " + w["text"]
        else:
            cell_texts[col_idx] = w["text"]
    # strip
    cell_texts = [c.strip() for c in cell_texts]
    return cell_texts


def extract_table_from_image(img: Image.Image) -> List[Dict]:
    """
    High-level: take a PIL image, run image_to_data, reconstruct table rows
    and return list of item dictionaries: {'item','quantity','unit','unit_price','line_total'}.
    """
    data = _words_from_image(img, psm=6)
    entries = []
    n = len(data.get("text", []))
    for i in range(n):
        txt = data["text"][i].strip()
        if txt == "":
            continue
        try:
            conf = int(data["conf"][i])
        except:
            try:
                conf = int(float(data["conf"][i]))
            except:
                conf = -1
        entries.append({
            "i": i,
            "text": txt,
            "left": int(data["left"][i]),
            "top": int(data["top"][i]),
            "width": int(data["width"][i]),
            "height": int(data["height"][i]),
            "conf": conf
        })

    if not entries:
        return []

    img_width = img.width
    # group by rows
    rows_entries = _group_lines_by_y(data, y_tol=14)  # returns rows as lists of entry-dicts

    # try to find headers to compute column boundaries
    header_cols = _find_header_columns(rows_entries, img_width)
    if header_cols is None:
        # fallback: try using the first big textual row to infer columns by equal splits
        # assume 4 columns: item | qty | unit_price | total
        # compute approximate boundaries by content distribution
        # fallback: split into 4 equal columns
        header_cols = [int(img_width * f) for f in (0.02, 0.35, 0.62, 0.85)]
    else:
        # if header_cols found but too many words, reduce to 4 by taking equidistant ones
        if len(header_cols) > 6:
            # sample to 4 positions roughly
            header_cols = [header_cols[0]] + [header_cols[len(header_cols)//3]] + [header_cols[len(header_cols)*2//3]] + [header_cols[-1]]

    items = []
    # skip rows that contain header words, find data rows that have numeric or known pattern
    for row in rows_entries:
        # join row text
        row_text = " ".join([w["text"] for w in row]).lower()
        if any(k in row_text for k in ("item", "quantity", "unit", "price", "total", "subtotal", "tax", "amount")):
            # skip header or footer lines
            continue
        # assign words to columns
        cells = _assign_words_to_columns(row, header_cols, img_width)
        # normalize into expected keys
        # We expect cells roughly: [item, qty, unit, price, total] — actual length varies
        # Heuristic mapping:
        # if len(cells) >=4: map 0=item, 1=qty, 2=unit_price or unit, 3=line_total
        item = cells[0] if len(cells) >= 1 else ""
        # try to extract qty numeric from cell 1 (may contain 'kg')
        qty_raw = cells[1] if len(cells) >= 2 else ""
        # if qty_raw contains space, split
        unit = ""
        unit_price = ""
        line_total = ""
        # if third cell looks like a currency number => unit price
        if len(cells) >= 3:
            # choose heuristic: if contains digits and dot, treat as price
            if any(ch.isdigit() for ch in cells[2]):
                unit_price = cells[2]
            else:
                unit = cells[2]
        if len(cells) >= 4:
            line_total = cells[3]
        # handle case where qty contains both number and unit, like "38 kg"
        if qty_raw and any(ch.isdigit() for ch in qty_raw):
            # attempt to split number from trailing unit
            parts = qty_raw.split()
            if len(parts) >= 2 and any(ch.isdigit() for ch in parts[0]):
                qty = parts[0]
                maybe_unit = parts[1]
                if not unit:
                    unit = maybe_unit
            else:
                qty = qty_raw
        else:
            qty = qty_raw

        items.append({
            "material_name": item.strip() if item else None,
            "quantity": qty.strip() if qty else None,
            "unit": unit.strip() if unit else None,
            "unit_price": unit_price.strip() if unit_price else None,
            "line_total": line_total.strip() if line_total else None,
            "row_text": " ".join([w["text"] for w in row]),
            "conf_avg": float(np.mean([w["conf"] for w in row if w["conf"] >= 0])) if any(w["conf"] >= 0 for w in row) else None
        })

    # final cleanup: remove rows that look like subtotal/tax/total (they often have words "subtotal" etc.)
    cleaned = []
    for it in items:
        rt = (it.get("row_text") or "").lower()
        if any(k in rt for k in ("subtotal", "tax", "total amount", "total:")):
            continue
        # ignore rows that are tiny noise
        if not it.get("material_name") and not it.get("quantity") and not it.get("unit_price"):
            continue
        cleaned.append(it)

    return cleaned
