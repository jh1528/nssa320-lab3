"""
Script: filter_skus.py
Version: 1.2

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

    3. Python 3 is installed and can run from PowerShell.

Postconditions:
    1. Prints a table showing region, VM size, and restriction status.
    2. Marks unrestricted VM sizes as AVAILABLE.
    3. Reports missing, empty, invalid, or unreadable JSON files instead of crashing.
    4. Attempts multiple encodings because Windows PowerShell redirection may create UTF-16 files.
    5. Does not modify Azure resources, Terraform files, or JSON input files.
"""

import json
from json import JSONDecodeError
from pathlib import Path


SCRIPT_VERSION = "1.2"


FILES = [
    ("eastus", "eastus-skus.json"),
    ("centralus", "centralus-skus.json"),
    ("westus", "westus-skus.json"),
]


WANTED_PREFIXES = (
    "Standard_B1",
    "Standard_B2",
    "Standard_A1",
    "Standard_A2",
    "Standard_DS1",
    "Standard_D2",
    "Standard_F1",
    "Standard_F2",
)


ENCODINGS_TO_TRY = (
    "utf-8",
    "utf-8-sig",
    "utf-16",
    "utf-16-le",
)


def load_json_file(path):
    """
    Purpose:
        Safely load a JSON file exported from Azure CLI.

    Preconditions:
        path is a pathlib.Path object pointing to a JSON file.

    Postconditions:
        Returns parsed JSON data if valid.
        Returns None if the file is missing, empty, invalid JSON, or unreadable.
        Attempts multiple encodings because Windows PowerShell redirection may
        create UTF-16 files.
    """

    if not path.exists():
        print(f"ERROR: Missing file: {path}")
        return None

    if path.stat().st_size == 0:
        print(f"ERROR: Empty file: {path}")
        return None

    for encoding in ENCODINGS_TO_TRY:
        try:
            file_text = path.read_text(encoding=encoding)
            return json.loads(file_text)

        except UnicodeDecodeError:
            continue

        except JSONDecodeError as error:
            print(f"ERROR: Invalid JSON file: {path}")
            print(f"       Encoding tried: {encoding}")
            print(f"       JSON error: {error}")
            print("       First few lines of file:")

            try:
                preview_text = path.read_text(encoding=encoding, errors="replace")
                for line in preview_text.splitlines()[:5]:
                    print(f"       {line}")
            except Exception as preview_error:
                print(f"       Could not preview file: {preview_error}")

            return None

    print(f"ERROR: Could not decode file with supported encodings: {path}")
    print(f"       Tried encodings: {', '.join(ENCODINGS_TO_TRY)}")
    return None


def get_restriction_status(restrictions):
    """
    Purpose:
        Convert Azure SKU restriction data into a readable status string.

    Preconditions:
        restrictions is a list from an Azure SKU object.

    Postconditions:
        Returns AVAILABLE if no restrictions exist.
        Otherwise returns one or more Azure restriction reason codes.
    """

    if not restrictions:
        return "AVAILABLE"

    return "; ".join(
        restriction.get("reasonCode", "UnknownRestriction")
        for restriction in restrictions
    )


def print_matching_skus(region, sku_data):
    """
    Purpose:
        Print small/low-cost VM SKUs for one Azure region.

    Preconditions:
        region is a string such as eastus, centralus, or westus.
        sku_data is a parsed list of Azure SKU dictionaries.

    Postconditions:
        Prints one row per matching VM SKU.
    """

    for sku in sku_data:
        name = sku.get("name", "")
        restrictions = sku.get("restrictions", [])

        if not name.startswith(WANTED_PREFIXES):
            continue

        status = get_restriction_status(restrictions)
        print(f"{region:<12} {name:<22} {status}")


def main():
    """
    Purpose:
        Main script entry point.

    Preconditions:
        Azure SKU JSON export files exist in the same folder as this script.

    Postconditions:
        Prints filtered Azure VM SKU availability results to stdout.
    """

    print(f"filter_skus.py version {SCRIPT_VERSION}")
    print(f"{'REGION':<12} {'SIZE':<22} {'STATUS'}")
    print("-" * 80)

    for region, filename in FILES:
        path = Path(filename)
        sku_data = load_json_file(path)

        if sku_data is None:
            continue

        print_matching_skus(region, sku_data)


if __name__ == "__main__":
    main()
