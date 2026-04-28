import email
import csv
import re
import glob
from bs4 import BeautifulSoup
from pathlib import Path


def extract_html(mhtml_path: str) -> str:
    with open(mhtml_path, "rb") as f:
        msg = email.message_from_bytes(f.read())
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            return part.get_payload(decode=True).decode("utf-8", errors="replace")
    return ""


def parse_listings(html: str, source_file: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    listings = soup.find_all(attrs={"data-cg-ft": "srp-listing-blade"})
    results = []

    for listing in listings:
        def text(testid):
            el = listing.find(attrs={"data-testid": testid})
            return el.get_text(strip=True) if el else ""

        title_el = listing.find(attrs={"data-cg-ft": "srp-listing-blade-title"})
        title = title_el.get("title", "") if title_el else text("srp-tile-listing-title")

        trim_el = listing.find(attrs={"data-cg-ft": "vehicle"})
        trim = trim_el.get("title", "") if trim_el else ""

        location = text("LocationSection-firstLine")
        distance = text("LocationSection-secondLine")

        msrp_raw = text("srp-tile-msrp")
        msrp = re.sub(r"[^\d$,.]", "", msrp_raw.replace("MSRP", "")).strip()

        price = text("srp-tile-price")
        monthly = text("srp-tile-payment")

        results.append({
            "Title": title,
            "Trim": trim,
            "Location": location,
            "Distance": distance,
            "MSRP": msrp,
            "Price": price,
            "Monthly Payment": monthly,
            "Source File": Path(source_file).name,
        })

    return results


def main():
    folder = Path(__file__).parent
    mhtml_files = sorted(folder.glob("*.mhtml"))

    if not mhtml_files:
        print("No .mhtml files found in", folder)
        return

    all_cars = []
    for path in mhtml_files:
        html = extract_html(str(path))
        cars = parse_listings(html, str(path))
        all_cars.extend(cars)
        print(f"{path.name}: {len(cars)} listings")

    output_csv = folder / "cars_output.csv"
    fieldnames = ["Title", "Trim", "Location", "Distance", "MSRP", "Price", "Monthly Payment", "Source File"]

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_cars)

    print(f"\nTotal: {len(all_cars)} cars extracted -> {output_csv}")


if __name__ == "__main__":
    main()
