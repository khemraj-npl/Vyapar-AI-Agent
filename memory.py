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
            "city": db_memory.get("city"),
            "company_name": db_memory.get("company_name"),
            "phone": db_memory.get("phone"),
            "package_interest": db_memory.get("package_interest"),
            "important_context": [],
        }

    return user_memory[user_id]


def update_memory(user_id, key, value):
    user_id = str(user_id)

    memory = get_memory(user_id)

    memory[key] = value

    save_user_memory(
        user_id=user_id,
        name=memory.get("name"),
        business_type=memory.get("business_type"),
        last_topic=memory.get("last_topic"),
        city=memory.get("city"),
        company_name=memory.get("company_name"),
        phone=memory.get("phone"),
        package_interest=memory.get("package_interest"),
    )

    return memory


def add_context(user_id, context):
    memory = get_memory(user_id)

    if context not in memory["important_context"]:
        memory["important_context"].append(context)

    memory["important_context"] = memory["important_context"][-10:]

    return memory


def memory_to_prompt(user_id):
    memory = get_memory(user_id)

    return f"""
User Memory:

Name:
{memory.get("name")}

Business Type:
{memory.get("business_type")}

City:
{memory.get("city")}

Company Name:
{memory.get("company_name")}

Phone:
{memory.get("phone")}

Package Interest:
{memory.get("package_interest")}

Last Topic:
{memory.get("last_topic")}

Important Context:
{memory.get("important_context")}
"""
