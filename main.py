import json
import telebot
from config.auto_search_dir import data_config
from telebot.types import BotCommand, InlineKeyboardMarkup, InlineKeyboardButton

bot = telebot.TeleBot(data_config['my_telegram_bot']['bot_token'], parse_mode='HTML')


class Main:
    def __init__(self):
        self.list_commands = None
        self.data = None
        self.list_data = None
        self.select_command = None
        self.markup = None
        self.user_id = None
        self.call = None
        self.admin = False
        self.start_main()

    def load_data(self):
        with open('config/config.json', 'r', encoding='utf-8') as file:
            return json.load(file)

    def get_keys(self):
        return list(self.data.keys())  # Получаем список месяцев

    def start_main(self):
        bot.set_my_commands([BotCommand("start", "В начало"), BotCommand("back", "Назад")])

        @bot.message_handler(commands=['start'])
        def handle_start(message):
            self.user_id = message.chat.id
            if str(self.user_id) in list(self.load_data()["admins"].values()) or str(message.chat.username).replace(
                    '@',
                    '') in \
                    list(self.load_data()["admins"].values()):
                self.admin = True
                self.show_start_menu()
            elif str(self.user_id) in list(self.load_data()["users"].values()) or str(message.chat.username).replace('@',
                                                                                                                   '') in \
                    list(self.load_data()["users"].values()):
                self.admin = False
                self.show_start_menu()

            else:
                bot.send_message(self.user_id, "У вас нет доступа к данному боту")
                bot.delete_message(self.user_id, message.message_id)

        @bot.callback_query_handler(func=lambda call: True)
        def handle_query(call):
            self.call = call
            self.navigate()

    def show_start_menu(self):

        self.markup = InlineKeyboardMarkup()
        self.markup.add(InlineKeyboardButton("Начать", callback_data="Начать"))
        if self.admin:
            self.markup.add(InlineKeyboardButton("Управление", callback_data="Управление"))
        with open('Volley.jpg', 'rb') as photo:
            bot.send_photo(self.user_id, photo, reply_markup=self.markup)

    # Запуск бота
    def navigate(self):
        if str(self.user_id) in list(self.load_data()["users"].values()) or str(
                self.call.message.chat.username).replace('@',
                                                         '') in \
                list(self.load_data()["users"].values()) or str(self.user_id) in list(
            self.load_data()["admins"].values()) or str(self.call.message.chat.username).replace('@',
                                                                                                 '') in \
                list(self.load_data()["admins"].values()):
            keys = self.call.data.split("/") if self.call.data else []
            data = self.load_data()["commands"]
            for key in keys:
                data = data.get(key, {})
            if isinstance(data, dict) and data:
                markup = InlineKeyboardMarkup()
                for k, v in data.items():
                    if isinstance(v, str) and v.startswith("http"):
                        markup.add(InlineKeyboardButton(k, url=v))
                    else:
                        markup.add(
                            InlineKeyboardButton(k, callback_data=f"{self.call.data}/{k}" if self.call.data else k))

                # Формируем путь с подчёркиванием последнего ключа
                if keys:
                    last_key = f"<u>{keys[-1]}</u>"
                    section_path = " - ".join(keys[:-1] + [last_key])  # Все, кроме последнего, остаются обычными
                    full_path = f"Главное меню - {section_path}"  # Добавляем "Главное меню" в начало
                else:
                    full_path = "Главное меню"  # Если ключей нет, просто "Главное меню"

                bot.edit_message_text(
                    chat_id=self.call.message.chat.id,
                    message_id=self.call.message.message_id,
                    text=f"Вы находитесь в разделе: {full_path}\n\n"
                         f"Используй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. "
                         f"В начало /start \n\nВыберите раздел:",
                    reply_markup=markup,
                    parse_mode="HTML"  # Включаем поддержку HTML
                )

            else:
                # Удаляем сообщение с фото
                bot.delete_message(self.call.message.chat.id, self.call.message.message_id)
                self.data = self.load_data()["commands"]
                buttons = [InlineKeyboardButton(key, callback_data=key) for key in self.get_keys()]
                markup = InlineKeyboardMarkup([buttons])
                new_text = """Вы находитесь в разделе: "<u>Главное меню</u>".\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите команду:"""
                bot.send_message(self.call.message.chat.id, new_text, reply_markup=markup)
        else:
            bot.send_message(self.user_id, "У вас нет доступа к данному боту")
            bot.delete_message(self.user_id, self.call.message.message_id)


if __name__ == "__main__":
    while True:
        try:
            Main()
            bot.infinity_polling(timeout=90, long_polling_timeout=5)
        except Exception as e:
            print(f"Ошибка: {e}")
            continue
