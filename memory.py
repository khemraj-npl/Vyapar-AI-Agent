user_memory = {}


def get_memory(user_id):
    user_id = str(user_id)

    if user_id not in user_memory:
        user_memory[user_id] = {
            "name": None,
            "business_type": None,
            "last_topic": None,
            "important_context": [],
        }

    return user_memory[user_id]


def update_memory(user_id, key, value):
    memory = get_memory(user_id)
    memory[key] = value
    return memory


def add_context(user_id, context):
    memory = get_memory(user_id)

    if context not in memory["important_context"]:
        memory["important_context"].append(context)

    memory["important_context"] = memory["important_context"][-5:]

    return memory


def memory_to_prompt(user_id):
    memory = get_memory(user_id)

    return f"""
User Memory:
- Name: {memory.get("name")}
- Business Type: {memory.get("business_type")}
- Last Topic: {memory.get("last_topic")}
- Important Context: {memory.get("important_context")}
"""
