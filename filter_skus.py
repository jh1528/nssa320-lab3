"""
Script: filter_skus.py

Purpose:
    Reads Azure VM SKU JSON files for selected regions and prints a filtered list
    of small/low-cost VM sizes that may be useful for the Terraform Azure lab.

Preconditions:
    1. Azure CLI has already been used to export SKU data into JSON files.
       Expected files in the same folder as this script:
           - eastus-skus.json
           - centralus-skus.json
           - westus-skus.json

    2. The JSON files were created with commands similar to:
           az vm list-skus --location eastus --resource-type virtualMachines --all --output json > eastus-skus.json
           az vm list-skus --location centralus --resource-type virtualMachines --all --output json > centralus-skus.json
           az vm list-skus --location westus --resource-type virtualMachines --all --output json > westus-skus.json

    3. Python 3 is installed and can be run from PowerShell.

Postconditions:
    1. The script prints a table showing:
           - Azure region
           - VM size/SKU name
           - availability status

    2. VM sizes with no restrictions are printed as AVAILABLE.

    3. VM sizes with Azure subscription or location restrictions display the
       Azure restriction reason, such as NotAvailableForSubscription.

    4. The script does not modify Azure resources, Terraform files, or JSON files.
"""

import json
from pathlib import Path


# List of Azure region JSON files to inspect.
# Each tuple contains:
#   1. The human-readable Azure region name.
#   2. The JSON filename exported from Azure CLI.
files = [
    ("eastus", "eastus-skus.json"),
    ("centralus", "centralus-skus.json"),
    ("westus", "westus-skus.json"),
]


# Small/low-cost VM size prefixes worth checking for this lab.
# The lab originally uses Standard_B1s and later Standard_B2ms,
# but this list includes several similar small VM families in case
# the student's Azure subscription blocks the original sizes.
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


# Print table header.
# <12 and <22 mean left-align the text in fixed-width columns.
print(f"{'REGION':<12} {'SIZE':<22} {'RESTRICTIONS'}")
print("-" * 80)


# Process each region's SKU JSON file.
for region, filename in files:
    path = Path(filename)

    # If a JSON file is missing, report it and continue with the next region.
    if not path.exists():
        print(f"{region:<12} missing file: {filename}")
        continue

    # Load the Azure SKU data from the JSON file.
    data = json.loads(path.read_text())

    # Check each VM SKU returned by Azure CLI.
    for sku in data:
        name = sku.get("name", "")
        restrictions = sku.get("restrictions", [])

        # Skip VM sizes that are not in the small/low-cost families we care about.
        if not name.startswith(wanted_prefixes):
            continue

        # If the restrictions list is empty, Azure reports this SKU as usable.
        if not restrictions:
            restriction_text = "AVAILABLE"
        else:
            # Otherwise, extract Azure's restriction reason, such as:
            # NotAvailableForSubscription
            restriction_text = "; ".join(
                r.get("reasonCode", "UnknownRestriction")
                for r in restrictions
            )

        # Print one filtered result row.
        print(f"{region:<12} {name:<22} {restriction_text}")
