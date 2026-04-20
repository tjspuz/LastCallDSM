#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "venues.json"


UPDATES = [
    {
        "id": "django-des-moines-metro-closed-2026-01-28",
        "name": "Django",
        "status": "closed",
        "eventDate": "2026-03-14",
        "sortDate": "2026-03-14",
        "dateLabel": "Mar 14, 2026",
        "datePrecision": "day",
        "venueType": "restaurant",
        "venueTypeLabel": "Restaurant",
        "cuisine": "French",
        "neighborhood": "Downtown",
        "story": "The French-inspired downtown restaurant Django permanently closed after an 18-year run, with March 14 serving as its final day.",
        "verificationLevel": "verified",
        "sources": [
            {
                "label": "KCCI",
                "url": "https://www.kcci.com/article/popular-french-inspired-restaurant-to-close-in-des-moines/70165649",
            },
            {
                "label": "Django",
                "url": "https://www.djangodesmoines.com/",
            },
        ],
        "openedDate": "2008-05-01",
        "openedDatePrecision": "month",
        "closedDate": "2026-03-14",
        "closedDatePrecision": "day",
        "publicDescription": "The French-inspired downtown staple closed after 18 years, ending its run on March 14, 2026.",
    },
    {
        "id": "panka-peruvian-closure",
        "name": "Panka Peruvian",
        "status": "closed",
        "eventDate": "2026-04-01",
        "sortDate": "2026-04-01",
        "dateLabel": "Apr 2026",
        "datePrecision": "month",
        "venueType": "restaurant",
        "venueTypeLabel": "Restaurant",
        "cuisine": "Peruvian",
        "neighborhood": "Ingersoll",
        "story": "Panka Peruvian announced it would close in early April after nearly seven years on Ingersoll, where it built a loyal following for its warm hospitality and Peruvian cooking.",
        "verificationLevel": "verified",
        "sources": [
            {
                "label": "KCCI",
                "url": "https://www.kcci.com/article/panka-peruvian-restaurant-in-des-moines-to-close-in-april/70260705",
            }
        ],
        "openedDate": "2019-02-01",
        "openedDatePrecision": "month",
        "closedDate": "2026-04-01",
        "closedDatePrecision": "month",
        "publicDescription": "Known for elevated Peruvian dishes and a warm Ingersoll dining room, Panka closed in early April 2026 after nearly seven years.",
    },
    {
        "id": "false-nine-social-club-opening",
        "name": "False Nine Social Club",
        "status": "opened",
        "eventDate": "2026-03-17",
        "sortDate": "2026-03-17",
        "dateLabel": "Mar 17, 2026",
        "datePrecision": "day",
        "venueType": "bar",
        "venueTypeLabel": "Bar",
        "cuisine": "Sports Bar / Soccer Pub",
        "neighborhood": "West Des Moines",
        "story": "Mitzi's reopened as False Nine Social Club, shifting the space toward a matchday-inspired soccer bar and social club atmosphere.",
        "verificationLevel": "verified",
        "sources": [
            {
                "label": "Axios Des Moines",
                "url": "https://www.axios.com/local/des-moines/2026/03/16/daves-hot-chicken-bonchon-restaurant-opening-des-moines",
            },
            {
                "label": "Mitzi's",
                "url": "https://www.findglocal.com/US/West-Des-Moines/112603317056810/Mitzi%27s",
            },
        ],
        "openedDate": "2026-03-17",
        "openedDatePrecision": "day",
        "closedDate": None,
        "closedDatePrecision": None,
        "publicDescription": "The former Mitzi's space reopened as a soccer-forward social club with a matchday bar feel in West Des Moines.",
    },
    {
        "id": "desi-fresh-opening",
        "name": "Desi Fresh",
        "status": "opened",
        "eventDate": "2026-03-01",
        "sortDate": "2026-03-01",
        "dateLabel": "Mar 2026",
        "datePrecision": "month",
        "venueType": "restaurant",
        "venueTypeLabel": "Restaurant",
        "cuisine": "Indian / South Asian",
        "neighborhood": "Waukee",
        "story": "Desi Fresh recently opened in Waukee as a combination Desi grocery and food outlet serving kabobs, tandoori, biryani, and other South Asian staples.",
        "verificationLevel": "verified",
        "sources": [
            {
                "label": "Axios Des Moines",
                "url": "https://www.axios.com/local/des-moines/2026/03/16/daves-hot-chicken-bonchon-restaurant-opening-des-moines",
            }
        ],
        "openedDate": "2026-03-01",
        "openedDatePrecision": "month",
        "closedDate": None,
        "closedDatePrecision": None,
        "publicDescription": "This Waukee newcomer blends a Desi grocery with a hot food counter serving kabobs, tandoori, and biryani.",
    },
    {
        "id": "scoops-by-beth-opening",
        "name": "Scoops by Beth",
        "status": "opened",
        "eventDate": "2026-02-21",
        "sortDate": "2026-02-21",
        "dateLabel": "Feb 21, 2026",
        "datePrecision": "day",
        "venueType": "cafe",
        "venueTypeLabel": "Cafe",
        "cuisine": "Ice Cream",
        "neighborhood": "Highland Park",
        "story": "Scoops by Beth opened in Highland Park as part of the district's comeback, serving small-batch ice cream inspired by family recipes.",
        "verificationLevel": "verified",
        "sources": [
            {
                "label": "Axios Des Moines",
                "url": "https://www.axios.com/local/des-moines/2026/02/20/scoops-beth-highland-park-comeback",
            }
        ],
        "openedDate": "2026-02-21",
        "openedDatePrecision": "day",
        "closedDate": None,
        "closedDatePrecision": None,
        "publicDescription": "A small-batch Highland Park ice cream shop that opened as part of the neighborhood's ongoing revival.",
    },
    {
        "id": "bar-martinez-opening",
        "name": "Bar Martinez",
        "status": "opened",
        "eventDate": "2026-02-03",
        "sortDate": "2026-02-03",
        "dateLabel": "Feb 3, 2026",
        "datePrecision": "day",
        "venueType": "bar",
        "venueTypeLabel": "Bar",
        "cuisine": "Cocktail Lounge",
        "neighborhood": "Highland Park",
        "story": "Bar Martinez opened in Highland Park as a polished cocktail lounge with a moody neighborhood-bar feel.",
        "verificationLevel": "verified",
        "sources": [
            {
                "label": "dsm magazine",
                "url": "https://dsmmagazine.com/2025/01/28/dsm-dish-restaurant-openings/",
            }
        ],
        "openedDate": "2026-02-03",
        "openedDatePrecision": "day",
        "closedDate": None,
        "closedDatePrecision": None,
        "publicDescription": "A polished Highland Park cocktail lounge that added a moodier late-night option to the neighborhood's dining strip.",
    },
    {
        "id": "toyo-ramen-opening",
        "name": "Toyo Ramen & Japanese Street Food",
        "status": "opened",
        "eventDate": "2026-01-01",
        "sortDate": "2026-01-01",
        "dateLabel": "Jan 1, 2026",
        "datePrecision": "day",
        "venueType": "restaurant",
        "venueTypeLabel": "Restaurant",
        "cuisine": "Japanese / Ramen",
        "neighborhood": "Prairie Trail",
        "story": "Toyo Ramen opened at Prairie Trail with Hakata-style ramen, Japanese street snacks, and a story shaped by the owner's Tibetan roots and training in Japan.",
        "verificationLevel": "verified",
        "sources": [
            {
                "label": "Axios Des Moines",
                "url": "https://www.axios.com/local/des-moines/2026/01/12/toyo-ramen-brings-authentic-japanese-cuisine-to-ankeny",
            },
            {
                "label": "Toyo Ramen",
                "url": "https://toyoramenia.com/",
            },
        ],
        "openedDate": "2026-01-01",
        "openedDatePrecision": "day",
        "closedDate": None,
        "closedDatePrecision": None,
        "publicDescription": "This Prairie Trail ramen shop brought Hakata-style broth, Japanese street food, and a distinct Japanese-Tibetan story to Ankeny.",
    },
    {
        "id": "bubbies-bbq-opening",
        "name": "Bubbies BBQ",
        "status": "opened",
        "eventDate": "2025-09-08",
        "sortDate": "2025-09-08",
        "dateLabel": "Sep 8, 2025",
        "datePrecision": "day",
        "venueType": "restaurant",
        "venueTypeLabel": "Restaurant",
        "cuisine": "BBQ",
        "neighborhood": "Pleasant Hill",
        "story": "Bubbies BBQ opened in Pleasant Hill with smoked meats, comfort sides, and a neighborhood pit-stop feel.",
        "verificationLevel": "verified",
        "sources": [
            {
                "label": "dsm magazine",
                "url": "https://dsmmagazine.com/2025/01/28/dsm-dish-restaurant-openings/",
            }
        ],
        "openedDate": "2025-09-08",
        "openedDatePrecision": "day",
        "closedDate": None,
        "closedDatePrecision": None,
        "publicDescription": "A Pleasant Hill barbecue spot built around smoked meats, comfort sides, and casual neighborhood energy.",
    },
    {
        "id": "palms-dsm-opening",
        "name": "Palms DSM",
        "status": "opened",
        "eventDate": "2025-06-01",
        "sortDate": "2025-06-01",
        "dateLabel": "Jun 2025",
        "datePrecision": "month",
        "venueType": "restaurant",
        "venueTypeLabel": "Restaurant",
        "cuisine": "Afro-Caribbean",
        "neighborhood": "Ingersoll",
        "story": "Palms DSM opened on Ingersoll with an upscale Afro-Caribbean approach, earning attention for dishes like braised oxtail and honey suya wings.",
        "verificationLevel": "verified",
        "sources": [
            {
                "label": "Black Iowa News",
                "url": "https://blackiowanews.com/palms-dsm/",
            }
        ],
        "openedDate": "2025-06-01",
        "openedDatePrecision": "month",
        "closedDate": None,
        "closedDatePrecision": None,
        "publicDescription": "An Ingersoll restaurant with an upscale Afro-Caribbean menu, known for dishes like braised oxtail and honey suya wings.",
    },
    {
        "id": "masao-opening",
        "name": "Masao",
        "status": "opened",
        "eventDate": "2025-06-05",
        "sortDate": "2025-06-05",
        "dateLabel": "Jun 5, 2025",
        "datePrecision": "day",
        "venueType": "restaurant",
        "venueTypeLabel": "Restaurant",
        "cuisine": "French-Japanese Fusion",
        "neighborhood": "East Village",
        "story": "Masao opened in the former Miyabi 9 space, blending sushi and modern French cooking in one of the metro's most distinctive new dining rooms.",
        "verificationLevel": "verified",
        "sources": [
            {
                "label": "Des Moines Register mirror",
                "url": "https://www.yahoo.com/lifestyle/articles/dig-comfort-food-italian-fare-110155860.html",
            },
            {
                "label": "Axios Des Moines",
                "url": "https://www.axios.com/local/des-moines/2025/02/12/waterfront-restaurant-family-miyabi-9-masao",
            },
        ],
        "openedDate": "2025-06-05",
        "openedDatePrecision": "day",
        "closedDate": None,
        "closedDatePrecision": None,
        "publicDescription": "An East Village spot pairing sushi with modern French cooking in the former Miyabi 9 space.",
    },
    {
        "id": "table-128-reopening",
        "name": "Table 128",
        "status": "opened",
        "eventDate": "2024-05-01",
        "sortDate": "2024-05-01",
        "dateLabel": "May 1, 2024",
        "datePrecision": "day",
        "venueType": "restaurant",
        "venueTypeLabel": "Restaurant",
        "cuisine": "Modern American",
        "neighborhood": "Downtown",
        "story": "Chef Lynn Pritchard brought Table 128 back to life downtown at Gray's Landing, reviving the restaurant after its Clive run ended in 2021.",
        "verificationLevel": "verified",
        "sources": [
            {
                "label": "Table 128",
                "url": "https://www.table128bistro.com/about-table-128",
            }
        ],
        "openedDate": "2024-05-01",
        "openedDatePrecision": "day",
        "closedDate": None,
        "closedDatePrecision": None,
        "publicDescription": "The modern American restaurant returned in a new downtown home at Gray's Landing after going dark in 2021.",
    },
    {
        "id": "lacheles-fitz-opening",
        "name": "Lachele's Fine Foods and The Fitz",
        "status": "opened",
        "eventDate": "2025-02-27",
        "sortDate": "2025-02-27",
        "dateLabel": "Feb 27, 2025",
        "datePrecision": "day",
        "venueType": "restaurant",
        "venueTypeLabel": "Restaurant",
        "cuisine": "American / Burgers / Cocktails",
        "neighborhood": "Highland Park",
        "story": "Cory Wendel's second Lachele's location opened in Highland Park, pairing the burger-focused Lachele's side with the more clubby cocktail-driven Fitz side.",
        "verificationLevel": "verified",
        "sources": [
            {
                "label": "Des Moines Register mirror",
                "url": "https://www.yahoo.com/lifestyle/articles/restaurants-opened-des-moines-metro-093625329.html",
            }
        ],
        "openedDate": "2025-02-27",
        "openedDatePrecision": "day",
        "closedDate": None,
        "closedDatePrecision": None,
        "publicDescription": "This Highland Park opening paired a second Lachele's burger outpost with The Fitz, a clubbier bar-and-cocktail sidecar next door.",
    },
]


def main() -> None:
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    items = {item["id"]: item for item in payload["items"]}

    for record in UPDATES:
        items[record["id"]] = record

    payload["updatedAt"] = "2026-04-20"
    payload["items"] = sorted(items.values(), key=lambda item: item["sortDate"], reverse=True)
    DATA_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
