# business_settings.py
# All configurable business rules in one place.
# Edit these values to match your actual store — no code changes needed elsewhere.

BUSINESS_SETTINGS: dict = {

    # ── Store Identity ────────────────────────────────────────────────────────
    "business_name": "Nepal Online Store",

    # ── Discount / Negotiation Rules ─────────────────────────────────────────
    # Maximum discount the AI is allowed to offer (as a percentage of price)
    "max_discount_percent": 10,

    # ── COD Settings ─────────────────────────────────────────────────────────
    "cod_available": True,
    "cod_note": "COD available for orders Rs 500 maathi. Kathmandu Valley ma COD free cha.",

    # ── Exchange & Return Policy ──────────────────────────────────────────────
    "exchange_policy": (
        "7 din bhitra exchange milcha. "
        "Condition: unused, original packaging intact. "
        "Damage, used, वा washed items exchange/return hudaina. "
        "Defective items bhaye full exchange दिनेछौं।"
    ),

    # ── Human Handover ────────────────────────────────────────────────────────
    "human_handover_message": (
        "Real staff sanga kura garna: 9800000000 (Viber/WhatsApp). "
        "Office hours: 10am–6pm, Sunday–Friday."
    ),

    # ── Default Delivery Note (when no area matched) ──────────────────────────
    "default_delivery_note": (
        "Delivery Nepal-wide huncha. "
        "Kathmandu Valley: 1-2 din. "
        "Outside valley: 3-5 din. "
        "Exact charge confirm garna location pathaunu hos."
    ),

    # ── Delivery Areas ────────────────────────────────────────────────────────
    # Each area has: name, keywords (to match in message), days, fee (Rs), note
    "delivery_areas": {
        "kathmandu_valley": {
            "name": "Kathmandu Valley (KTM / Lalitpur / Bhaktapur)",
            "keywords": ["ktm", "kathmandu", "lalitpur", "bhaktapur", "patan", "valley"],
            "days": "1-2",
            "fee": 0,
            "note": "Free delivery! 12pm bhanda agaadi order garey same-day possible.",
        },
        "pokhara": {
            "name": "Pokhara",
            "keywords": ["pokhara", "kaski", "lekhnath"],
            "days": "2-3",
            "fee": 150,
            "note": "",
        },
        "biratnagar": {
            "name": "Biratnagar / Jhapa / Morang",
            "keywords": ["biratnagar", "jhapa", "morang", "birtamod"],
            "days": "3-4",
            "fee": 150,
            "note": "",
        },
        "chitwan": {
            "name": "Chitwan / Bharatpur",
            "keywords": ["chitwan", "bharatpur", "narayanghat", "ratnanagar"],
            "days": "2-3",
            "fee": 150,
            "note": "",
        },
        "butwal": {
            "name": "Butwal / Rupandehi",
            "keywords": ["butwal", "palpa", "rupandehi", "bhairahawa", "siddharthanagar"],
            "days": "3-4",
            "fee": 150,
            "note": "",
        },
        "nepalgunj": {
            "name": "Nepalgunj / Banke",
            "keywords": ["nepalgunj", "banke", "kohalpur"],
            "days": "4-5",
            "fee": 200,
            "note": "",
        },
        "dhangadhi": {
            "name": "Dhangadhi / Kailali",
            "keywords": ["dhangadhi", "kailali", "tikapur"],
            "days": "4-6",
            "fee": 200,
            "note": "",
        },
        "ilam": {
            "name": "Ilam / Taplejung / Hills",
            "keywords": ["ilam", "taplejung", "terhathum", "sankhuwasabha"],
            "days": "4-6",
            "fee": 200,
            "note": "Hills area delivery time vary gar_sakcha.",
        },
        "remote": {
            "name": "Remote / Mountain Districts",
            "keywords": ["humla", "jumla", "dolpa", "mugu", "mountain", "himal", "remote"],
            "days": "7-14",
            "fee": 400,
            "note": "Remote area delivery time weather ma depend garcha.",
        },
    },
}
