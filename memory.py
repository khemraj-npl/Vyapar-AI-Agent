from memory_db import get_user, save_user_memory


user_memory = {}


def get_memory(user_id):
    user_id = str(user_id)

    db_memory = get_user(user_id)

    if user_id not in user_memory:
        user_memory[user_id] = {
            "name": db_memory.get("name"),
            "business_type": db_memory.get("business_type"),
            "last_topic": db_memory.get("last_topic"),
            "important_context": [],
        }

    return user_memory[user_id]


def update_memory(user_id, key, value):
    user_id = str(user_id)
    memory = get_memory(user_id)

    memory[key] = value

    if key == "name":
        save_user_memory(user_id, name=value)

    if key == "business_type":
        save_user_memory(user_id, business_type=value)

    if key == "last_topic":
        save_user_memory(user_id, last_topic=value)

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
