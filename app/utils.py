import random

def generate_mock_phone_numbers(count=50):
    return [f"+26588{''.join(str(random.randint(0, 9)) for _ in range(7))}" for _ in range(count)]

def generate_mock_names(count=10):
    names = ["Alice", "Bob", "Charlie", "David", "Eve", "Frank", "Grace", "Hank", "Ivy", "Jack"]
    return [{"id": i + 1, "name": name} for i, name in enumerate(names[:count])]
