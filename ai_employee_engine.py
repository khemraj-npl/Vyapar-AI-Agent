user_text = user_text.strip()

if not user_text:
    return "Message pathaunu hola."

text = user_text.lower().strip()

# Simple greetings
if text in ["hello", "hi", "namaste", "namaskar", "hey"]:
    return (
        "नमस्ते! 🙏 म Vyapar AI हुँ। "
        "हजुरको ISP व्यवसायलाई ग्राहक सेवा, बिक्री र जानकारी व्यवस्थापनमा सहयोग गर्न तयार छु।"
    )

# Thanks
if text in ["thanks", "thank you", "dhanyabad", "dhanyawaad"]:
    return (
        "स्वागत छ 😊। थप सहयोग चाहियो भने भन्नुहोस्।"
    )

# Single question mark
if text == "?":
    return (
        "कृपया आफ्नो प्रश्न अलि स्पष्ट रूपमा लेख्नुहोस् 😊"
    )
