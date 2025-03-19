from datetime import datetime

# Заданная дата
target_date = datetime.strptime("19-03-2025 20:30", "%d-%m-%Y %H:%M")

# Текущая дата и время
current_date = datetime.now()

# Проверяем, меньше ли текущая дата
if current_date < target_date:
    print("Текущая дата меньше указанной.")
else:
    print("Текущая дата больше или равна указанной.")
