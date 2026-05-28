# products.py
# Temporary in-memory product catalog.
# Replace this list with a database query when you scale up.

from typing import Optional

# ── Sample Product Catalog ────────────────────────────────────────────────────
# A realistic Nepali online clothing & accessories store.
# Fields: id, name, description, price, sizes, colors, stock, keywords

PRODUCTS: list[dict] = [
    {
        "id": 1,
        "name": "Nepali Dhaka Topi",
        "description": "Authentic handwoven Dhaka fabric topi. National pride, perfect for dashain, tihar, formal occasions.",
        "price": 350,
        "sizes": ["S", "M", "L", "XL"],
        "colors": ["Red/Black", "Green/Black", "Blue/White"],
        "stock": 50,
        "keywords": ["topi", "dhaka", "national", "hat", "टोपी", "ढाका"],
    },
    {
        "id": 2,
        "name": "Cotton Kurta Suruwal (Men)",
        "description": "Pure cotton kurta suruwal set. Comfortable for daily wear and festive occasions.",
        "price": 1200,
        "sizes": ["S", "M", "L", "XL", "XXL"],
        "colors": ["White", "Light Blue", "Cream", "Grey"],
        "stock": 30,
        "keywords": ["kurta", "suruwal", "daura", "men", "cotton", "कुर्ता", "सुरुवाल"],
    },
    {
        "id": 3,
        "name": "Pashmina Shawl",
        "description": "Soft 100% pure Pashmina shawl. Lightweight, warm, perfect gift. Made in Nepal.",
        "price": 2500,
        "sizes": ["Free Size"],
        "colors": ["Natural Beige", "Deep Red", "Charcoal Grey", "Teal", "Mustard"],
        "stock": 25,
        "keywords": ["pashmina", "shawl", "scarf", "wrap", "gift", "पश्मीना"],
    },
    {
        "id": 4,
        "name": "Lokta Paper Notebook",
        "description": "Handmade lokta paper notebook. Eco-friendly, durable, unique Nepali craft product.",
        "price": 280,
        "sizes": ["A5", "A4"],
        "colors": ["Natural Brown", "White", "Sky Blue"],
        "stock": 100,
        "keywords": ["lokta", "notebook", "diary", "paper", "craft", "लोक्ता"],
    },
    {
        "id": 5,
        "name": "Nepali Tea Collection (3-pack)",
        "description": "Premium Ilam and Kanchanjungha tea assortment. First flush, organic. Makes a perfect gift.",
        "price": 650,
        "sizes": ["50g per pack"],
        "colors": ["N/A"],
        "stock": 40,
        "keywords": ["tea", "ilam", "chiya", "chai", "organic", "gift", "चिया"],
    },
    {
        "id": 6,
        "name": "Thangka Painting (Small)",
        "description": "Hand-painted Buddhist Thangka art. 6x8 inch. Traditional Nepali/Tibetan spiritual art.",
        "price": 1800,
        "sizes": ["6x8 inch", "8x10 inch"],
        "colors": ["Traditional multicolor"],
        "stock": 15,
        "keywords": ["thangka", "painting", "buddhist", "art", "spiritual", "थांका"],
    },
    {
        "id": 7,
        "name": "Singing Bowl Set",
        "description": "Handcrafted 7-metal singing bowl with cushion and mallet. Meditation and healing use.",
        "price": 1500,
        "sizes": ["Small (3 inch)", "Medium (5 inch)", "Large (7 inch)"],
        "colors": ["Antique Bronze"],
        "stock": 20,
        "keywords": ["singing bowl", "bowl", "meditation", "spiritual", "tibetan", "काँसा"],
    },
    {
        "id": 8,
        "name": "Himalayan Pink Salt Lamp",
        "description": "Natural pink Himalayan salt lamp with bulb. Purifies air, creates calming ambiance.",
        "price": 900,
        "sizes": ["Small (1-2kg)", "Medium (3-4kg)", "Large (5-7kg)"],
        "colors": ["Natural Pink/Orange glow"],
        "stock": 35,
        "keywords": ["salt lamp", "himalayan", "lamp", "salt", "decor", "lamp"],
    },
    {
        "id": 9,
        "name": "Felt Wool Slippers",
        "description": "Handmade 100% wool felt slippers. Warm, cozy, eco-friendly. Popular export item.",
        "price": 450,
        "sizes": ["S (36-37)", "M (38-39)", "L (40-41)", "XL (42-43)"],
        "colors": ["Grey", "Brown", "Maroon", "Black"],
        "stock": 45,
        "keywords": ["slippers", "felt", "wool", "footwear", "shoes", "जुत्ता"],
    },
    {
        "id": 10,
        "name": "Khukuri (Souvenir)",
        "description": "Traditional Nepali khukuri knife — decorative souvenir grade. With wooden sheath.",
        "price": 850,
        "sizes": ["8 inch", "12 inch"],
        "colors": ["Natural Wood + Steel"],
        "stock": 18,
        "keywords": ["khukuri", "kukri", "knife", "souvenir", "gurkha", "खुकुरी"],
    },
]


# ── Search Logic ──────────────────────────────────────────────────────────────

def search_products(message: str) -> list[dict]:
    """
    Searches the product catalog based on keywords in the customer's message.
    
    Strategy:
    1. Check product keywords list (exact catalog tags)
    2. Check product name words
    3. Check color/size matches
    
    Returns a list of matching products (max 3) sorted by relevance.
    Does NOT fabricate products — only returns real catalog items.
    """
    msg_lower = message.lower().strip()
    
    scored: list[tuple[int, dict]] = []

    for product in PRODUCTS:
        score = 0

        # Check against catalog keywords (highest weight)
        for kw in product["keywords"]:
            if kw in msg_lower:
                score += 3

        # Check product name words
        for word in product["name"].lower().split():
            if len(word) > 3 and word in msg_lower:
                score += 2

        # Check color names
        for color in product["colors"]:
            if color.lower() in msg_lower:
                score += 1

        # Check size mentions
        for size in product["sizes"]:
            if size.lower() in msg_lower:
                score += 1

        if score > 0:
            scored.append((score, product))

    # Sort by score descending, return top 3
    scored.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in scored[:3]]


def format_product_for_ai(products: list[dict]) -> str:
    """
    Formats product data into a concise text block for injection into the AI prompt.
    Prevents hallucination by giving the AI exact, factual product data.
    """
    if not products:
        return "No matching products found in catalog."

    lines = []
    for p in products:
        color_str = ", ".join(p["colors"]) if p["colors"] != ["N/A"] else "N/A"
        size_str = ", ".join(p["sizes"])
        stock_status = "In Stock" if p["stock"] > 0 else "Out of Stock"
        lines.append(
            f"• {p['name']} — Rs {p['price']:,}\n"
            f"  Sizes: {size_str}\n"
            f"  Colors: {color_str}\n"
            f"  Status: {stock_status}\n"
            f"  About: {p['description']}"
        )
    return "\n\n".join(lines)


def get_product_by_id(product_id: int) -> Optional[dict]:
    """Returns a product dict by ID, or None if not found."""
    for p in PRODUCTS:
        if p["id"] == product_id:
            return p
    return None
