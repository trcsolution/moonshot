#!/usr/bin/env python3
"""Load the Mundo Coffee synthetic menu into an Odoo 20 database via the JSON-2 API.

Modes:
  --check     validate the CSVs and image manifest only (no Odoo connection)
  --dry-run   validate, then print what would be created
  (default)   validate, then create/update records in Odoo (idempotent)

Live mode reads ODOO_URL, ODOO_DB and ODOO_API_KEY from the environment.
Standard library only. Untested against a live Odoo 20 instance: run --dry-run
first and verify the JSON-2 request format against the 20.0 docs.
"""
import argparse
import base64
import csv
import json
import os
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
IMAGES = ROOT / "images"

CREATE_VARIANT = {"always", "dynamic", "no_variant"}
DISPLAY_TYPES = {"radio", "pills", "select", "color", "multi"}


def read_csv(name):
    with open(DATA / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_data():
    products = read_csv("products.csv")
    attributes = read_csv("attributes.csv")
    profiles = read_csv("attribute_profiles.csv")
    notes = read_csv("pos_notes.csv")
    with open(IMAGES / "MANIFEST.csv", newline="", encoding="utf-8") as f:
        manifest = list(csv.DictReader(f))
    return products, attributes, profiles, notes, manifest


def validate(products, attributes, profiles, notes, manifest):
    errors, warnings = [], []

    attr_meta, attr_values = {}, defaultdict(list)
    for a in attributes:
        name = a["attribute"]
        meta = (a["create_variant"], a["display_type"])
        if a["create_variant"] not in CREATE_VARIANT:
            errors.append(f"attribute {name}: bad create_variant {a['create_variant']}")
        if a["display_type"] not in DISPLAY_TYPES:
            errors.append(f"attribute {name}: bad display_type {a['display_type']}")
        if attr_meta.setdefault(name, meta) != meta:
            errors.append(f"attribute {name}: inconsistent create_variant/display_type")
        if a["value"] in attr_values[name]:
            errors.append(f"attribute {name}: duplicate value {a['value']}")
        attr_values[name].append(a["value"])
        float(a["price_extra"]), int(a["prep_delta_seconds"])
    for name, (cv, dt) in attr_meta.items():
        if dt == "multi" and cv != "no_variant":
            errors.append(f"attribute {name}: multi display requires no_variant")

    profile_lines = defaultdict(list)
    for p in profiles:
        attr = p["attribute"]
        if attr not in attr_values:
            errors.append(f"profile {p['attribute_profile']}: unknown attribute {attr}")
            continue
        vals = attr_values[attr] if p["values"] == "*" else p["values"].split("|")
        for v in vals:
            if v not in attr_values[attr]:
                errors.append(f"profile {p['attribute_profile']}: {attr} has no value {v}")
        profile_lines[p["attribute_profile"]].append((attr, vals))

    codes = set()
    for r in products:
        code = r["default_code"]
        if code in codes:
            errors.append(f"product {code}: duplicate default_code")
        codes.add(code)
        if float(r["list_price"]) <= 0:
            errors.append(f"product {code}: list_price must be > 0")
        prep, hold = int(r["prep_minutes"]), int(r["max_hold_minutes"])
        if prep < 0 or hold <= 0:
            errors.append(f"product {code}: prep must be >= 0 and hold > 0")
        if r["attribute_profile"] and r["attribute_profile"] not in profile_lines:
            errors.append(f"product {code}: unknown attribute_profile {r['attribute_profile']}")
        if not (IMAGES / r["image_file"]).exists():
            warnings.append(f"product {code}: image {r['image_file']} not yet downloaded")

    man_codes = {m["default_code"]: m for m in manifest}
    for r in products:
        m = man_codes.get(r["default_code"])
        if not m:
            errors.append(f"manifest: missing row for {r['default_code']}")
        elif m["image_file"] != r["image_file"]:
            errors.append(f"manifest: image_file mismatch for {r['default_code']}")
        elif (IMAGES / r["image_file"]).exists() and not (m["licence"] and m["source_url"]):
            errors.append(f"manifest: {r['default_code']} image present but licence/source_url blank")

    seen = set()
    for n in notes:
        if n["name"] in seen:
            errors.append(f"pos note: duplicate {n['name']}")
        seen.add(n["name"])

    return errors, warnings, attr_meta, profile_lines


class Json2:
    """Minimal JSON-2 client: POST /json/2/<model>/<method> with named arguments."""

    def __init__(self, url, db, key):
        self.url, self.db, self.key = url.rstrip("/"), db, key

    def call(self, model, method, **params):
        req = urllib.request.Request(
            f"{self.url}/json/2/{model}/{method}",
            data=json.dumps(params).encode(),
            headers={
                "Authorization": f"bearer {self.key}",
                "X-Odoo-Database": self.db,
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": "trc-mundo-menu-loader",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read() or "null")
        except urllib.error.HTTPError as e:
            sys.exit(f"{model}.{method} failed: HTTP {e.code} {e.read().decode(errors='replace')}")

    def upsert(self, model, domain, vals):
        ids = self.call(model, "search", domain=domain, limit=1)
        if ids:
            self.call(model, "write", ids=ids, vals=vals)
            return ids[0]
        return self.call(model, "create", vals_list=[vals])[0]

    def fields(self, model):
        return set(self.call(model, "fields_get", attributes=["type"]))

    def has_model(self, model):
        return bool(self.call("ir.model", "search", domain=[["model", "=", model]], limit=1))


def load(api, products, attributes, notes, attr_meta, profile_lines):
    # POS categories
    categ_ids = {}
    for seq, name in enumerate(dict.fromkeys(r["pos_category"] for r in products), 1):
        categ_ids[name] = api.upsert("pos.category", [["name", "=", name]], {"name": name, "sequence": seq})

    # Attributes and values; trc_* fields only exist once trc_order_release is installed
    value_fields = api.fields("product.attribute.value")
    attr_ids, value_ids = {}, {}
    for name, (cv, dt) in attr_meta.items():
        attr_ids[name] = api.upsert(
            "product.attribute", [["name", "=", name]],
            {"name": name, "create_variant": cv, "display_type": dt},
        )
    for a in attributes:
        vals = {"name": a["value"], "attribute_id": attr_ids[a["attribute"]], "sequence": int(a["sequence"])}
        if "default_extra_price" in value_fields:
            vals["default_extra_price"] = float(a["price_extra"])
        if "trc_prep_delta_seconds" in value_fields:
            vals["trc_prep_delta_seconds"] = int(a["prep_delta_seconds"])
        value_ids[(a["attribute"], a["value"])] = api.upsert(
            "product.attribute.value",
            [["attribute_id", "=", attr_ids[a["attribute"]]], ["name", "=", a["value"]]],
            vals,
        )
    price_extra = {(a["attribute"], a["value"]): float(a["price_extra"]) for a in attributes}

    # Products
    tmpl_fields = api.fields("product.template")
    for r in products:
        vals = {
            "name": r["name"],
            "default_code": r["default_code"],
            "list_price": float(r["list_price"]),
            "available_in_pos": True,
            "pos_categ_ids": [[6, 0, [categ_ids[r["pos_category"]]]]],
            "description_sale": r["description_sale"],
        }
        if "trc_prep_minutes" in tmpl_fields:
            vals["trc_prep_minutes"] = int(r["prep_minutes"])
            vals["trc_max_hold_minutes"] = int(r["max_hold_minutes"])
        if "trc_allergens" in tmpl_fields:
            vals["trc_allergens"] = r["allergens"].replace("|", ", ")
        img = IMAGES / r["image_file"]
        if img.exists():
            vals["image_1920"] = base64.b64encode(img.read_bytes()).decode()
        tmpl_id = api.upsert("product.template", [["default_code", "=", r["default_code"]]], vals)

        for attr, vals_list in profile_lines.get(r["attribute_profile"], []):
            ids = [value_ids[(attr, v)] for v in vals_list]
            api.upsert(
                "product.template.attribute.line",
                [["product_tmpl_id", "=", tmpl_id], ["attribute_id", "=", attr_ids[attr]]],
                {"product_tmpl_id": tmpl_id, "attribute_id": attr_ids[attr], "value_ids": [[6, 0, ids]]},
            )
            for v in vals_list:
                ptav = api.call(
                    "product.template.attribute.value", "search",
                    domain=[["product_tmpl_id", "=", tmpl_id], ["product_attribute_value_id", "=", value_ids[(attr, v)]]],
                )
                if ptav:
                    api.call("product.template.attribute.value", "write", ids=ptav,
                             vals={"price_extra": price_extra[(attr, v)]})
        print(f"loaded {r['default_code']} {r['name']}")

    # Predefined POS notes (free kitchen instructions)
    if api.has_model("pos.note"):
        for n in notes:
            api.upsert("pos.note", [["name", "=", n["name"]]], {"name": n["name"], "sequence": int(n["sequence"])})
        print(f"loaded {len(notes)} POS notes")
    else:
        print("WARNING: model pos.note not found; create kitchen notes manually (verify v20 model name)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    products, attributes, profiles, notes, manifest = load_data()
    errors, warnings, attr_meta, profile_lines = validate(products, attributes, profiles, notes, manifest)
    for w in warnings:
        print("WARN ", w)
    for e in errors:
        print("ERROR", e)
    if errors:
        sys.exit(1)
    variants = sum(
        len(next((v for a, v in profile_lines[r["attribute_profile"]] if attr_meta[a][0] == "always"), [None]))
        for r in products if r["attribute_profile"]
    )
    print(f"OK: {len(products)} products, {len(attr_meta)} attributes, {len(attributes)} values, "
          f"{len(notes)} POS notes, ~{variants} sellable size variants")
    if args.check:
        return
    if args.dry_run:
        for r in products:
            lines = "; ".join(f"{a}: {len(v)}" for a, v in profile_lines.get(r["attribute_profile"], []))
            print(f"would load {r['default_code']:7} {r['name']:32} ${r['list_price']:>5}  [{lines}]")
        return

    url, db, key = (os.environ.get(k) for k in ("ODOO_URL", "ODOO_DB", "ODOO_API_KEY"))
    if not all((url, db, key)):
        sys.exit("Set ODOO_URL, ODOO_DB and ODOO_API_KEY")
    load(Json2(url, db, key), products, attributes, notes, attr_meta, profile_lines)


if __name__ == "__main__":
    main()
