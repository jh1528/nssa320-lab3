"""
Script: filter_skus.py
Version: 1.4

Purpose:
    Reads Azure VM SKU JSON files for selected regions and creates a filtered
    report of small/lab-sized VM sizes that may be useful for the Terraform Azure lab.

Preconditions:
    1. Azure CLI has already exported SKU data into JSON files:
           eastus-skus.json
           centralus-skus.json
           westus-skus.json

    2. The JSON files were created with commands like:
           az vm list-skus --location eastus --resource-type virtualMachines --all --output json > eastus-skus.json

    3. Python 3 is installed and can run from PowerShell.

Postconditions:
    1. Prints a table showing region, VM size, lab-size classification, priority, and restriction status.
    2. Creates a fresh filtered-skus.txt report on each run.
    3. Writes the same report to filtered-skus.txt.
    4. Shows counts for total lab-sized SKUs checked, available SKUs, and restricted SKUs.
    5. Marks unrestricted VM sizes as AVAILABLE.
    6. Recommends the smallest available lab-sized VM based on a priority ranking.
    7. Reports missing, empty, invalid, or unreadable JSON files instead of crashing.
    8. Attempts multiple encodings because Windows PowerShell redirection may create UTF-16 files.
    9. Does not modify Azure resources, Terraform files, or JSON input files.
"""

import json
import re
from json import JSONDecodeError
from pathlib import Path


SCRIPT_VERSION = "1.4"
OUTPUT_FILE = "filtered-skus.txt"


FILES = [
    ("eastus", "eastus-skus.json"),
    ("centralus", "centralus-skus.json"),
    ("westus", "westus-skus.json"),
]


# Purpose:
#     Match only small/lab-sized VM SKUs.
#
# Why this matters:
#     A simple prefix check like "Standard_D2" accidentally matches large SKUs
#     such as "Standard_D21s_v7". This regex only allows B1/B2, A1/A2, DS1,
#     D2, F1/F2, and prevents the next character from being another digit.
#
# Examples that match:
#     Standard_B1s
#     Standard_B2ms
#     Standard_A1_v2
#     Standard_DS1_v2
#     Standard_D2d_v3
#     Standard_F2s_v2
#
# Examples that do not match:
#     Standard_B12ms
#     Standard_D21s_v7
#     Standard_D128s_v6
SMALL_LAB_SKU_PATTERN = re.compile(
    r"^Standard_(B[12]|A[12]|DS1|D2|F[12])([^0-9]|$)",
    re.IGNORECASE,
)


# Purpose:
#     Rank acceptable lab-sized VM SKUs from smallest/preferred to larger fallback.
#
# Why this matters:
#     Azure can report many SKUs as AVAILABLE. This ranking helps select the
#     smallest reasonable option for a student lab instead of manually scanning
#     the output.
#
# Lower number = higher preference.
SKU_PRIORITY_RULES = [
    (re.compile(r"^Standard_B1ls$", re.IGNORECASE), 10, "B1ls smallest burstable candidate"),
    (re.compile(r"^Standard_B1s$", re.IGNORECASE), 20, "B1s original lab candidate"),
    (re.compile(r"^Standard_B1ms$", re.IGNORECASE), 30, "B1ms small burstable fallback"),
    (re.compile(r"^Standard_A1_v2$", re.IGNORECASE), 40, "A1_v2 small fallback"),
    (re.compile(r"^Standard_DS1_v2$", re.IGNORECASE), 50, "DS1_v2 small fallback"),
    (re.compile(r"^Standard_B2s$", re.IGNORECASE), 60, "B2s two-vCPU burstable fallback"),
    (re.compile(r"^Standard_B2ms$", re.IGNORECASE), 70, "B2ms lab Activity 4 target"),
    (re.compile(r"^Standard_A2_v2$", re.IGNORECASE), 80, "A2_v2 two-vCPU fallback"),
    (re.compile(r"^Standard_D2.*", re.IGNORECASE), 90, "D2-family fallback"),
    (re.compile(r"^Standard_F1.*", re.IGNORECASE), 100, "F1-family fallback"),
    (re.compile(r"^Standard_F2.*", re.IGNORECASE), 110, "F2-family fallback"),
]


ENCODINGS_TO_TRY = (
    "utf-8",
    "utf-8-sig",
    "utf-16",
    "utf-16-le",
)


report_lines = []


summary_counts = {
    "total_checked": 0,
    "available": 0,
    "restricted": 0,
}


available_candidates = []


def add_report_line(line=""):
    """
    Purpose:
        Add a line to the report and print it to stdout.

    Preconditions:
        line is a string.

    Postconditions:
        The line is printed to the terminal and stored for output file writing.
    """

    print(line)
    report_lines.append(line)


def reset_report_file():
    """
    Purpose:
        Remove the previous report file before generating a new one.

    Preconditions:
        OUTPUT_FILE is the configured report filename.

    Postconditions:
        Deletes the old report file if it exists.
        Does nothing if the report file does not exist.
    """

    output_path = Path(OUTPUT_FILE)

    if output_path.exists():
        output_path.unlink()


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
        add_report_line(f"ERROR: Missing file: {path}")
        return None

    if path.stat().st_size == 0:
        add_report_line(f"ERROR: Empty file: {path}")
        return None

    for encoding in ENCODINGS_TO_TRY:
        try:
            file_text = path.read_text(encoding=encoding)
            return json.loads(file_text)

        except UnicodeDecodeError:
            continue

        except JSONDecodeError as error:
            add_report_line(f"ERROR: Invalid JSON file: {path}")
            add_report_line(f"       Encoding tried: {encoding}")
            add_report_line(f"       JSON error: {error}")
            add_report_line("       First few lines of file:")

            try:
                preview_text = path.read_text(encoding=encoding, errors="replace")
                for line in preview_text.splitlines()[:5]:
                    add_report_line(f"       {line}")
            except Exception as preview_error:
                add_report_line(f"       Could not preview file: {preview_error}")

            return None

    add_report_line(f"ERROR: Could not decode file with supported encodings: {path}")
    add_report_line(f"       Tried encodings: {', '.join(ENCODINGS_TO_TRY)}")
    return None


def is_small_lab_sku(sku_name):
    """
    Purpose:
        Determine whether an Azure VM SKU name is appropriate for a small lab test.

    Preconditions:
        sku_name is a string from an Azure SKU object.

    Postconditions:
        Returns True if the SKU matches the small/lab-sized SKU pattern.
        Returns False otherwise.
    """

    return SMALL_LAB_SKU_PATTERN.search(sku_name) is not None


def get_sku_priority(sku_name):
    """
    Purpose:
        Assign a priority score to a lab-sized SKU.

    Preconditions:
        sku_name is a string from an Azure SKU object.

    Postconditions:
        Returns a tuple of:
            priority score as an integer
            priority reason as a string

        Lower priority score means the SKU is preferred as a smaller lab option.
    """

    for pattern, priority, reason in SKU_PRIORITY_RULES:
        if pattern.search(sku_name):
            return priority, reason

    return 999, "Lab-sized pattern matched, but no priority rule was found"


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


def update_summary_counts(status):
    """
    Purpose:
        Update summary counters for lab-sized SKU results.

    Preconditions:
        status is a string returned by get_restriction_status().

    Postconditions:
        Increments total_checked.
        Increments available if status is AVAILABLE.
        Otherwise increments restricted.
    """

    summary_counts["total_checked"] += 1

    if status == "AVAILABLE":
        summary_counts["available"] += 1
    else:
        summary_counts["restricted"] += 1


def record_available_candidate(region, sku_name, priority, reason):
    """
    Purpose:
        Store an available lab-sized SKU candidate for recommendation.

    Preconditions:
        region is a string.
        sku_name is the Azure VM SKU name.
        priority is an integer where lower is preferred.
        reason describes why the SKU has that priority.

    Postconditions:
        Adds the candidate to available_candidates.
    """

    available_candidates.append(
        {
            "region": region,
            "sku_name": sku_name,
            "priority": priority,
            "reason": reason,
        }
    )


def print_matching_skus(region, sku_data):
    """
    Purpose:
        Add small/lab-sized VM SKUs for one Azure region to the report.

    Preconditions:
        region is a string such as eastus, centralus, or westus.
        sku_data is a parsed list of Azure SKU dictionaries.

    Postconditions:
        Adds one report row per matching lab-sized VM SKU.
        Updates summary counts.
        Records available candidates for final recommendation.
    """

    for sku in sku_data:
        name = sku.get("name", "")
        restrictions = sku.get("restrictions", [])

        if not is_small_lab_sku(name):
            continue

        lab_size = "SMALL"
        status = get_restriction_status(restrictions)
        priority, reason = get_sku_priority(name)

        update_summary_counts(status)

        if status == "AVAILABLE":
            record_available_candidate(region, name, priority, reason)

        add_report_line(
            f"{region:<12} {name:<22} {lab_size:<10} {priority:<8} {status}"
        )


def print_summary():
    """
    Purpose:
        Print summary counts for the filtered report.

    Preconditions:
        summary_counts has been updated while processing SKU files.

    Postconditions:
        Adds summary totals to stdout and filtered-skus.txt.
    """

    add_report_line("")
    add_report_line("Summary")
    add_report_line("-" * 80)
    add_report_line(f"Total lab-sized SKUs checked: {summary_counts['total_checked']}")
    add_report_line(f"Available lab-sized SKUs:     {summary_counts['available']}")
    add_report_line(f"Restricted lab-sized SKUs:    {summary_counts['restricted']}")


def print_recommendation():
    """
    Purpose:
        Recommend the smallest available lab-sized SKU.

    Preconditions:
        available_candidates contains all available lab-sized SKUs found.

    Postconditions:
        Prints the best available candidate based on priority ranking.
        If no available candidates exist, prints a clear message.
    """

    add_report_line("")
    add_report_line("Recommended Smallest Available SKU")
    add_report_line("-" * 80)

    if not available_candidates:
        add_report_line("No available lab-sized SKU was found in the checked regions.")
        add_report_line("Consider checking another Azure region or asking the instructor for an approved fallback size.")
        return

    sorted_candidates = sorted(
        available_candidates,
        key=lambda candidate: (
            candidate["priority"],
            candidate["region"],
            candidate["sku_name"],
        ),
    )

    best_candidate = sorted_candidates[0]

    add_report_line(f"Region:   {best_candidate['region']}")
    add_report_line(f"VM Size:  {best_candidate['sku_name']}")
    add_report_line(f"Priority: {best_candidate['priority']}")
    add_report_line(f"Reason:   {best_candidate['reason']}")
    add_report_line("")
    add_report_line("Terraform setting:")
    add_report_line(f'vm_size = "{best_candidate["sku_name"]}"')


def write_report_file():
    """
    Purpose:
        Write the collected report lines to a text file.

    Preconditions:
        report_lines contains the report output.

    Postconditions:
        Creates or overwrites filtered-skus.txt using UTF-8 encoding.
    """

    output_path = Path(OUTPUT_FILE)
    output_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print(f"\nReport written to: {output_path}")


def main():
    """
    Purpose:
        Main script entry point.

    Preconditions:
        Azure SKU JSON export files exist in the same folder as this script.

    Postconditions:
        Removes the previous filtered-skus.txt file if it exists.
        Prints filtered Azure VM SKU availability results to stdout.
        Prints a recommendation for the smallest available lab-sized SKU.
        Writes the results to a fresh filtered-skus.txt report.
    """

    reset_report_file()

    add_report_line(f"filter_skus.py version {SCRIPT_VERSION}")
    add_report_line(
        f"{'REGION':<12} {'SIZE':<22} {'LAB_SIZE':<10} {'PRIORITY':<8} {'STATUS'}"
    )
    add_report_line("-" * 100)

    for region, filename in FILES:
        path = Path(filename)
        sku_data = load_json_file(path)

        if sku_data is None:
            continue

        print_matching_skus(region, sku_data)

    print_summary()
    print_recommendation()
    write_report_file()


if __name__ == "__main__":
    main()
