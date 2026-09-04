def skill_reservation(skill: dict) -> int:
    return int(skill["billing"]["reservation"])

def skill_charge(skill: dict, input_tokens: int, output_tokens: int) -> int:
    b = skill["billing"]
    if b["mode"] == "fixed":
        return int(b["base_price"])
    total = int(b.get("base_price", 0))
    meters = b.get("meters", {})
    total += ((input_tokens + 999) // 1000) * int(meters.get("input_token_per_1000", 0))
    total += ((output_tokens + 999) // 1000) * int(meters.get("output_token_per_1000", 0))
    return total
