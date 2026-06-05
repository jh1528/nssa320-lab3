"""
Script: filter_skus.py

Purpose:
    Reads Azure VM SKU JSON files for selected regions and prints a filtered list
    of small/low-cost VM sizes that may be useful for the Terraform Azure lab.

Preconditions:
    1. Azure CLI has already exported SKU data into JSON files:
           eastus-skus.json
           centralus-skus.json
           westus-skus.json

    2. The JSON files were created with commands like:
           az vm list-skus --location eastus --resource-type virtualMachines --all --output json > eastus-skus.json

Postconditions:
    1. Prints a table showing region, VM size, and restriction status.
    2. Marks unrestricted VM sizes as AVAILABLE.
    3. Reports missing, empty, or invalid JSON files instead of crashing.
    4. Does not modify Azure or Terraform resources.
"""

import json
from json import JSONDecodeError
from pathlib import Path


files = [
    ("eastus", "eastus-skus.json"),
    ("centralus", "centralus-skus.json"),
    ("westus", "westus-skus.json"),
]


wanted_prefixes = (
    "Standard_B1",
    "Standard_B2",
    "Standard_A1",
    "Standard_A2",
    "Standard_DS1",
    "Standard_D2",
    "Standard_F1",
    "Standard_F2",
)


def load_json_file(path):
    """
    Purpose:
        Safely load a JSON file.

    Preconditions:
        path is a pathlib.Path object pointing to a JSON file.

    Postconditions:
        Returns parsed JSON data if valid.
        Returns None if the file is missing, empty, or invalid JSON.
    """

    if not path.exists():
        print(f"ERROR: Missing file: {path}")
        return None

    if path.stat().st_size == 0:
        print(f"ERROR: Empty file: {path}")
        return None

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except JSONDecodeError as error:
        print(f"ERROR: Invalid JSON file: {path}")
        print(f"       JSON error: {error}")
        print("       First few lines of file:")
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            for line in lines[:5]:
                print(f"       {line}")
        except Exception as read_error:
            print(f"       Could not preview file: {read_error}")
        return None


print(f"{'REGION':<12} {'SIZE':<22} {'STATUS'}")
print("-" * 80)


for region, filename in files:
    path = Path(filename)
    data = load_json_file(path)

    if data is None:
        continue

    for sku in data:
        name = sku.get("name", "")
        restrictions = sku.get("restrictions", [])

        if not name.startswith(wanted_prefixes):
            continue

        if not restrictions:
            status = "AVAILABLE"
        else:
            status = "; ".join(
                r.get("reasonCode", "UnknownRestriction")
                for r in restrictions
            )

        print(f"{region:<12} {name:<22} {status}")
