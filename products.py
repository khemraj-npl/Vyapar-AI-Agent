from __future__ import annotations

PRODUCTS = [
    {
        "name": "100 Mbps Internet Package",
        "price": "NPR 10,000",
        "duration": "13 months",
        "description": "100 Mbps internet package from Himalayan Online Service Pvt. Ltd. Installation and Router/ONU are free.",
        "tags": ["100mbps", "100 mbps", "internet", "package", "isp"],
    },
    {
        "name": "150 Mbps Internet Package",
        "price": "NPR 12,000",
        "duration": "13 months",
        "description": "150 Mbps internet package from Himalayan Online Service Pvt. Ltd. Installation and Router/ONU are free.",
        "tags": ["150mbps", "150 mbps", "internet", "package", "isp"],
    },
    {
        "name": "200 Mbps Internet Package",
        "price": "NPR 15,000",
        "duration": "13 months",
        "description": "200 Mbps internet package from Himalayan Online Service Pvt. Ltd. Installation and Router/ONU are free.",
        "tags": ["200mbps", "200 mbps", "internet", "package", "isp"],
    },
]


def search_products(query: str, top_n: int = 3):
    query_lower = (query or "").lower()
    results = []

    for product in PRODUCTS:
        score = 0

        for tag in product["tags"]:
            if tag in query_lower:
                score += 2

        if product["name"].lower() in query_lower:
            score += 3

        if "price" in query_lower or "kati" in query_lower or "package" in query_lower:
            score += 1

        if score > 0:
            results.append((score, product))

    results.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in results[:top_n]]


def products_to_prompt(items):
    if not items:
        return """
Available internet packages:
- 100 Mbps: NPR 10,000 for 13 months
- 150 Mbps: NPR 12,000 for 13 months
- 200 Mbps: NPR 15,000 for 13 months
Installation: Free
Router/ONU: Free
"""

    lines = ["Relevant internet packages:"]
    for item in items:
        lines.append(
            f"- {item['name']}: {item['price']} for {item['duration']}. {item['description']}"
        )

    return "\n".join(lines)
