import json
import telebot
from telebot import types
from config.auto_search_dir import data_config
from telebot.types import BotCommand, InlineKeyboardMarkup, InlineKeyboardButton
import re

bot = telebot.TeleBot(data_config['my_telegram_bot']['bot_token'], parse_mode='HTML')


class Main:
    def __init__(self):
        self.list_commands = None
        self.open_contol = None
        self.selected_users = set()
        self.control = False
        self.keys = None
        self.data = None
        self.list_data = None
        self.select_command = None
        self.markup = None
        self.user_id = None
        self.select_usr_adm = None
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
            if message.message_id:
                for id_ in range(max(1, message.message_id - 10), message.message_id + 1):
                    try:
                        bot.delete_message(chat_id=message.chat.id, message_id=id_)
                    except Exception as error:
                        print(f"Ошибка при удалении сообщения в handle_start_main: {id_}: {error}")

            if str(self.user_id) in list(self.load_data()["admins"].values()) or str(message.chat.username).replace(
                    '@',
                    '') in \
                    list(self.load_data()["admins"].values()):
                self.admin = True
                self.show_start_menu()
            elif str(self.user_id) in [name.replace('@', '') for command in self.load_data()["commands"].keys() for name
                                       in self.load_data()["commands"][command]["users"].values()] or str(
                message.chat.username).replace('@', '') in [name.replace('@', '') for command in
                                                            self.load_data()["commands"].keys() for name in
                                                            self.load_data()["commands"][command]["users"].values()]:

                self.admin = False
                self.show_start_menu()

            else:
                bot.send_message(self.user_id, "У вас нет доступа к данному боту")
                bot.delete_message(self.user_id, message.message_id)

        @bot.callback_query_handler(func=lambda call: True)
        def handle_query(call):
            self.call = call
            if self.call.data == "Управление":
                self.control = True
                self.control_buttons()
            elif self.call.data == 'Доступ к боту':
                self.add_dell_users()
            elif self.call.data == 'Начать':
                self.control = False
                self.navigate()
            elif (self.call.data in self.load_data()[
                "commands"].keys() or self.call.data == 'admins') and self.control and not self.open_contol:
                self.select_command = self.call.data
                self.close()

            # Закрыть доступ
            elif self.call.data == 'close':
                self.del_buttons_commands()
                # открыть доступ
            elif self.call.data == 'open':
                self.del_buttons_commands()
            elif self.open_contol:
                self.select_command = self.call.data
                self.open()
            # сохраняем удаление
            elif self.call.data == "save_dell":
                self.dell_users_or_admins()
                if self.selected_users:
                    response_text = "Пользователи удалены" if len(self.selected_users) > 1 else "Пользователь удален"
                    bot.answer_callback_query(self.call.id, response_text,
                                              show_alert=True)
                self.selected_users = set()
                self.del_buttons_commands()
            # отмена сохранения
            elif self.call.data == "cancel_dell":
                self.selected_users = set()
                self.del_buttons_commands()

            elif self.call.data.startswith("toggle_"):
                user_key = '_'.join(self.call.data.split("_")[1:])  # Извлекаем имя пользователя

                if user_key in self.selected_users:
                    self.selected_users.remove(user_key)  # Убираем из списка
                else:
                    self.selected_users.add(user_key)  # Добавляем в список

                self.close()  # Перерисовываем кнопки с обновленными значениями

        @bot.message_handler(commands=['back'])
        def handle_back(message):
            if len(self.call.data.split("/")) > 1:
                bot.delete_message(message.chat.id, message.message_id)
                self.call.data = re.sub(r'\/[^\/]+$', '', self.call.data)
                self.navigate()
            elif len(self.call.data.split("/")) == 1 and self.call.data != "Начать":
                bot.delete_message(message.chat.id, message.message_id)
                self.call.data = "Начать"
                self.navigate()
            else:
                if message.message_id:
                    for id_ in range(max(1, message.message_id - 10), message.message_id + 1):
                        try:
                            bot.delete_message(chat_id=message.chat.id, message_id=id_)
                        except Exception as error:
                            print(f"Ошибка при удалении сообщения в handle_start_main: {id_}: {error}")

                handle_start(message)

    def show_start_menu(self):

        self.markup = InlineKeyboardMarkup()
        self.markup.add(InlineKeyboardButton("Начать", callback_data="Начать"))
        if self.admin:
            self.markup.add(InlineKeyboardButton("Управление", callback_data="Управление"))
        with open('Volley.jpg', 'rb') as photo:
            bot.send_photo(self.user_id, photo, reply_markup=self.markup)

    # Запуск бота
    def navigate(self):
        if str(self.user_id) in [name.replace('@', '') for command in self.load_data()["commands"].keys() for name
                                 in self.load_data()["commands"][command]["users"].values()] or str(
            self.call.message.chat.username).replace('@', '') in [name.replace('@', '') for command in
                                                                  self.load_data()["commands"].keys() for name in
                                                                  self.load_data()["commands"][command][
                                                                      "users"].values()] or str(self.user_id) in list(
            self.load_data()["admins"].values()) or str(self.call.message.chat.username).replace('@',
                                                                                                 '') in \
                list(self.load_data()["admins"].values()):

            self.keys = self.call.data.split("/") if self.call.data else []

            data = self.load_data()["commands"]
            for key in self.keys:
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
                if self.keys:
                    last_key = f"<u>{self.keys[-1]}</u>"
                    section_path = " - ".join(self.keys[:-1] + [last_key])  # Все, кроме последнего, остаются обычными
                    full_path = f"Главное меню - {section_path}"  # Добавляем "Главное меню" в начало
                else:
                    full_path = "Главное меню"  # Если ключей нет, просто "Главное меню"

                bot.edit_message_text(
                    chat_id=self.call.message.chat.id,
                    message_id=self.call.message.message_id,
                    text=f"""Вы находитесь в разделе: {full_path}\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:""",
                    reply_markup=markup,
                    parse_mode="HTML"  # Включаем поддержку HTML
                )

            else:
                # Удаляем сообщение с фото
                bot.delete_message(self.call.message.chat.id, self.call.message.message_id)
                self.data = self.load_data()["commands"]
                buttons = [InlineKeyboardButton(key, callback_data=key) for key in self.get_keys()]
                markup = InlineKeyboardMarkup([buttons])
                new_text = """Вы находитесь в разделе: <u>Главное меню</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"""
                bot.send_message(self.call.message.chat.id, new_text, reply_markup=markup)
        else:
            bot.send_message(self.user_id, "У вас нет доступа к данному боту")
            bot.delete_message(self.user_id, self.call.message.message_id)

    def control_buttons(self):
        bot.delete_message(self.call.message.chat.id, self.call.message.message_id)
        buttons = [InlineKeyboardButton(key, callback_data=key) for key in ["Доступ к боту", "Редактирование команд"]]
        markup = InlineKeyboardMarkup([buttons])
        new_text = """Вы находитесь в разделе: <u>Управление</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"""
        bot.send_message(self.call.message.chat.id, new_text, reply_markup=markup)

    def dell_users_or_admins(self):
        # Загружаем данные из файла
        data = self.load_data()

        # Удаляем пользователей
        for user in self.selected_users:
            data_user = user.split("_")
            if data_user[-1] != 'admins':
                # Удаляем пользователя из данных
                if data_user[0] in data["commands"][data_user[-1]]["users"]:
                    del data["commands"][data_user[-1]]["users"][data_user[0]]

        # Сохраняем обновленные данные обратно в файл
        self.write_data(data)  # Передаем измененные данные в функцию сохранения

    def write_data(self, data):
        # Сохраняем данные в файл
        with open('config/config.json', 'w', encoding='utf-8') as file:
            json.dump(data, file, ensure_ascii=False, indent=4)

    def add_dell_users(self):
        self.markup = InlineKeyboardMarkup()
        self.markup.add(InlineKeyboardButton("Открыть доступ", callback_data="open"))
        self.markup.add(InlineKeyboardButton("Закрыть доступ", callback_data="close"))
        new_text = """Вы находитесь в разделе: Управление - <u>Доступ к боту</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"""
        bot.edit_message_text(
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id,
            text=new_text,
            reply_markup=self.markup,
            parse_mode="HTML"  # Включаем поддержку HTML
        )

    def del_buttons_commands(self):
        if self.open_contol is None:
            text = "Закрыть доступ"
            self.open_contol = False
        elif self.call.data == "open":
            self.open_contol = True
            text = "Открыть доступ"
        self.data = self.load_data()["commands"]
        buttons = [InlineKeyboardButton(key, callback_data=key) for key in self.get_keys()]
        self.markup = InlineKeyboardMarkup([buttons])
        self.markup.add(InlineKeyboardButton("Админы", callback_data="admins"))

        new_text = f"Вы находитесь в разделе: Управление - Доступ к боту - <u>{text}</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"
        bot.edit_message_text(
            new_text,
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id,
            reply_markup=self.markup
        )

    def close(self):
        self.markup = InlineKeyboardMarkup()
        buttons = []
        count = 1
        if self.select_command != 'admins':
            for keys, value in self.load_data()["commands"][self.select_command]["users"].items():
                is_selected = f"{keys}_{value}_{self.select_command}" in self.selected_users  # Проверяем, выбран ли пользователь
                icon = "✅" if is_selected else "❌"  # Меняем иконку
                button_text = f"{icon} {keys}"
                item = types.InlineKeyboardButton(button_text,
                                                  callback_data=f"toggle_{keys}_{value}_{self.select_command}")
                buttons.append(item)
        else:
            for keys, value in self.load_data()[self.select_command].items():
                is_selected = f"{keys}_{value}_{self.select_command}" in self.selected_users  # Проверяем, выбран ли пользователь
                icon = "✅" if is_selected else "❌"  # Меняем иконку
                button_text = f"{icon} {keys}"
                item = types.InlineKeyboardButton(button_text,
                                                  callback_data=f"toggle_{keys}_{value}_{self.select_command}")
                buttons.append(item)

        self.markup.add(*buttons)

        save = InlineKeyboardButton("💾 Сохранить!", callback_data='save_dell')
        cancel = InlineKeyboardButton("Отмена!", callback_data='cancel_dell')
        self.markup.add(cancel, save)
        test = "Админы" if self.select_command == 'admins' else self.select_command
        new_text = f"Вы находитесь в разделе: Управление - Доступ к боту - Закрыть доступ -  <u>{self.select_command}</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"

        bot.edit_message_text(
            new_text,
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id,
            reply_markup=self.markup
        )

    def open(self):
        test = "Админы" if self.select_command == 'admins' else self.select_command
        # Редактируем текущее сообщение, чтобы запросить имя сотрудника
        bot.edit_message_text(
            f"Вы находитесь в разделе: Управление - Доступ к боту - Открыть доступ - <u>{test}</u>.\n\nИспользуй "
            f"кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start "
            f"\n\nНапишите Ник и id пользователя для добавления через двоеточие, пример:\n Вася:2938214371 или "
            f"Петя:@petya (можно без @). \nТакже можно добавлять списком нескольких пользователей через запятую, "
            f"пример:\nВася:2938214371, Петя:@petya, Lena:lenusik",
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id
        )

        # Устанавливаем состояние ожидания ответа от пользователя
        bot.register_next_step_handler(self.call.message,
                                       self.process_employee_name)

    def process_employee_name(self, message):
        text = "Пользователь добавлен"
        if message.text not in ['/back',
                                '/start']:
            employee_name = str(message.text).replace(' ', '').replace('\n', ',').replace(',,', '').split(
                ',')  # Получаем введенное имя сотрудника

            data = self.load_data()
            for new_name in employee_name:
                name, value = new_name.split(":")
                if self.select_command != 'admins':
                    data["commands"][self.select_command]["users"][name] = value

                else:
                    data["admins"][name] = value
            self.write_data(data)
            if len(employee_name) > 1:
                text = "Пользователи добавлены"
            bot.answer_callback_query(self.call.id, text,
                                      show_alert=True)
            bot.delete_message(chat_id=message.chat.id,
                               message_id=message.message_id)
            self.del_buttons_commands()
        else:
            if message.message_id:
                for id_ in range(max(1, message.message_id - 1), message.message_id + 1):
                    try:
                        bot.delete_message(chat_id=message.chat.id, message_id=id_)
                    except Exception as error:
                        print(f"Ошибка при удалении сообщения в process_employee_name: {id_}: {error}")

if __name__ == "__main__":
    while True:
        try:
            Main()
            bot.infinity_polling(timeout=90, long_polling_timeout=5)
        except Exception as e:
            print(f"Ошибка: {e}")
            continue
