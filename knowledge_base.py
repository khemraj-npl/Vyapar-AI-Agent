SERVICE_CATALOG = [
    {
        "category": "ISP Package",
        "name": "Basic Internet Package",
        "description": "Small family or basic home usage ko lagi suitable package.",
        "price": None,
        "notes": "Exact price business owner le set garne.",
    },
    {
        "category": "ISP Package",
        "name": "High Speed Internet Package",
        "description": "Streaming, online class, office work ra multiple devices ko lagi suitable.",
        "price": None,
        "notes": "Exact Mbps and price business owner le set garne.",
    },
    {
        "category": "Service",
        "name": "New Internet Connection",
        "description": "Naya customer ko lagi internet connection inquiry handle garne.",
        "price": None,
        "notes": "Location, package preference, phone number collect garne.",
    },
    {
        "category": "Support",
        "name": "Internet Not Working Support",
        "description": "Customer ko internet chalena bhane first-level troubleshooting garne.",
        "price": None,
        "notes": "Router light, LOS light, WiFi only issue, payment status, location sodhne.",
    },
]


BUSINESS_FAQS = [
    {
        "question": "Internet chalena",
        "answer": (
            "पहिले router को power light, LOS light र WiFi signal check गर्नुपर्छ। "
            "यदि LOS red छ भने fiber line issue हुन सक्छ। Customer ID वा phone number लिएर technician लाई escalate गर्नुपर्छ।"
        ),
    },
    {
        "question": "New connection chahiyo",
        "answer": (
            "नयाँ connection को लागि customer को location, required speed/package, phone number र installation time preference collect गर्नुपर्छ।"
        ),
    },
    {
        "question": "Speed slow cha",
        "answer": (
            "पहिले WiFi distance, connected devices, router restart, speed test result र package speed check गर्नुपर्छ।"
        ),
    },
]


def catalog_to_prompt() -> str:
    services_text = "\n".join(
        [
            f"- {item['name']} ({item['category']}): {item['description']} Notes: {item['notes']}"
            for item in SERVICE_CATALOG
        ]
    )

    faq_text = "\n".join(
        [
            f"- Q: {item['question']}\n  A: {item['answer']}"
            for item in BUSINESS_FAQS
        ]
    )

    return f"""
Knowledge Base:

Services / Catalog:
{services_text}

Business FAQs:
{faq_text}

Important:
- Do not invent exact price if price is None.
- Ask for location, phone number, customer ID, or package preference when needed.
- For support issue, ask one troubleshooting question at a time.
"""
