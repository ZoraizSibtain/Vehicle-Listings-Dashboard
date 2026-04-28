import email
import csv
import re
import time
import urllib.request
import urllib.parse
from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import urljoin


def extract_html_and_base_url(mhtml_path: str) -> tuple[str, str]:
    with open(mhtml_path, "rb") as f:
        msg = email.message_from_bytes(f.read())

    base_url = (
        msg.get("Snapshot-Content-Location", "")
        or msg.get("Content-Location", "")
        or ""
    )

    for part in msg.walk():
        if part.get_content_type() == "text/html":
            html = part.get_payload(decode=True).decode("utf-8", errors="replace")
            if not base_url:
                base_url = part.get("Content-Location", "")
            return html, base_url

    return "", base_url


def extract_listing_url(listing, base_url: str) -> str:
    el = listing.parent
    for _ in range(8):
        if el is None or el.name in ("body", "html", "[document]"):
            break
        if el.name == "a":
            href = el.get("href", "")
            if href:
                return href if href.startswith("http") else urljoin(base_url or "", href)
        el = el.parent

    link = listing.find("a", href=re.compile(r"detail|listing|vehicledetail", re.I))
    if link:
        href = link.get("href", "")
        if href:
            return href if href.startswith("http") else urljoin(base_url or "", href)

    return ""


def parse_listings(html: str, base_url: str = "") -> list[dict]:
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
        listing_url = extract_listing_url(listing, base_url)

        results.append({
            "Title": title,
            "Trim": trim,
            "Location": location,
            "Distance": distance,
            "MSRP": msrp,
            "Price": price,
            "Monthly Payment": monthly,
            "Listing URL": listing_url,
        })

    return results


def fetch_listing_details(url: str) -> dict:
    empty = {
        "VIN": "", "Stock Number": "", "Body Type": "", "Fuel Type": "",
        "History": "", "Dealer": "", "Dealer Phone": "",
        "Dealer Address": "", "Dealer Website": "", "Dealer Rating": "",
    }
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f" [error: {e}]", end="")
        return empty

    soup = BeautifulSoup(html, "html.parser")

    def t(testid):
        el = soup.find(attrs={"data-testid": testid})
        return el.get_text(strip=True) if el else ""

    def cg(ft):
        el = soup.find(attrs={"data-cg-ft": ft})
        return el.get_text(strip=True) if el else ""

    vin = re.sub(r"^VIN:\s*", "", cg("vin"))
    stock = re.sub(r"^Stock number:\s*", "", cg("stockNumber"), flags=re.IGNORECASE)

    # Body type and fuel type from spec list
    body_type = ""
    fuel_type = ""
    for li in soup.find_all("li"):
        txt = li.get_text(strip=True)
        if re.match(r"(Sedan|SUV|Truck|Coupe|Convertible|Wagon|Van|Hatchback|Pickup)", txt, re.I):
            body_type = txt
        if re.match(r"(Gasoline|Diesel|Electric|Hybrid|Plug-in Hybrid)", txt, re.I):
            fuel_type = txt

    # History (clean title, accidents)
    history_parts = []
    for el in soup.find_all(string=re.compile(r"(clean title|accident)", re.I)):
        s = el.strip()
        if s:
            history_parts.append(s)
    history = "; ".join(dict.fromkeys(history_parts))

    # Dealer website — decode from CarGurus redirect
    dealer_website = ""
    dw_el = soup.find(attrs={"data-testid": "dealer-website-link"})
    if dw_el and dw_el.get("href"):
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(dw_el["href"]).query)
        dealer_website = qs.get("url", [""])[0]

    # Dealer rating
    rating_el = soup.find(attrs={"data-testid": "dealer-rating"})
    dealer_rating = rating_el.get_text(strip=True) if rating_el else ""

    return {
        "VIN": vin,
        "Stock Number": stock,
        "Body Type": body_type,
        "Fuel Type": fuel_type,
        "History": history,
        "Dealer": t("dealerName"),
        "Dealer Phone": t("dealer-phone-link"),
        "Dealer Address": t("dealerAddress"),
        "Dealer Website": dealer_website,
        "Dealer Rating": dealer_rating,
    }


def main():
    folder = Path(__file__).parent
    mhtml_files = sorted(folder.rglob("**/*.mhtml"))

    if not mhtml_files:
        print("No .mhtml files found in", folder)
        return

    all_cars = []
    for path in mhtml_files:
        html, base_url = extract_html_and_base_url(str(path))
        cars = parse_listings(html, base_url)
        all_cars.extend(cars)
        print(f"{path.relative_to(folder)}: {len(cars)} listings")

    print(f"\nFetching details for {len(all_cars)} listings...")
    for i, car in enumerate(all_cars, 1):
        print(f"  [{i}/{len(all_cars)}] {car['Title'][:50]}", end="", flush=True)
        if car["Listing URL"]:
            car.update(fetch_listing_details(car["Listing URL"]))
        print()
        time.sleep(0.5)

    output_csv = folder / "cars_output.csv"
    fieldnames = [
        "Title", "Trim", "Location", "Distance", "MSRP", "Price", "Monthly Payment",
        "VIN", "Stock Number", "Body Type", "Fuel Type", "History",
        "Dealer", "Dealer Phone", "Dealer Address", "Dealer Website", "Dealer Rating",
        "Listing URL",
    ]

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_cars)

    print(f"\nTotal: {len(all_cars)} cars extracted -> {output_csv}")


if __name__ == "__main__":
    main()