def print_dict(d, indent=0):
    for key, value in d.items():
        print(' ' * indent + str(key) + ': ', end='')
        if isinstance(value, dict):
            print()  # Переход на новую строку для вложенного словаря
            print_dict(value, indent + 4)  # Увеличиваем отступ для вложенного словаря
        else:
            print(value)

# Пример вложенного словаря
nested_dict = {
    "Отметились": {
        "Админы": {
            "Кирилл(5444152518)": 0
        },
        "Reserve": {
            "Олеся(5444152518)": "+Буду",
            "Пеня(4214514)": "+Буду",
        }
    }
}

print_dict(nested_dict)

