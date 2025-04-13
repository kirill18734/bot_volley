import os


class Config:
    def __init__(self):
        self.BOT_TOKEN = "7892113140:AAHUz5IESaivcIFO8DiyKmc_i_jtoczpxaY"
        # Формируем пути относительно корня проекта
        self.IMG_VOLLEY_PATH = self.find_file_in_project("volley.jpg")
        self.IMG_FISH_PATH = self.find_file_in_project("fish.jpg")
        self.FILE_DATA = self.find_file_in_project("data.json")
        self.MONTH_NAMES = {
            1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
            5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
            9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
        }
        self.WEEK_DAYS = [
            "Понедельник", "Вторник", "Среда",
            "Четверг", "Пятница", "Суббота", "Воскресенье"
        ]

    # Объединенная функция для автоматического поиска файла
    def find_file_in_project(self, filename):
        for root_dir, dirs, files in os.walk(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))):
            for file in files:
                if file == filename or (
                        file.lower() == filename.lower() and
                        file[0].istitle()):  # два пробела перед символом '#'
                    return os.path.join(root_dir, file)


config = Config()
