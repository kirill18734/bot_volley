import json
import telebot
from telebot import types
from config.auto_search_dir import data_config
from telebot.types import BotCommand, InlineKeyboardMarkup, InlineKeyboardButton

bot = telebot.TeleBot(data_config['my_telegram_bot']['bot_token'], parse_mode='HTML')


class Main:
    def __init__(self):
        self.state_stack = {}  # Стек для хранения состояний
        self.del_vd_stat = None
        self.selected_users = set()
        self.selected_video_stat = set()
        self.control = None
        self.keys = []
        self.data = None
        self.list_data = None
        self.select_command = None
        self.markup = None
        self.user_id = None
        self.select_usr_adm = None
        self.call = None
        self.admin = None
        self.start_main()

    def entry(self, message):
        # Изменить условия фильтрования доступа :

        admins = list(value for value in self.load_data()["admins"].values())
        users = [name for command in self.load_data()["commands"].keys() for name
                 in self.load_data()["commands"][command]["users"].values()]
        username = str(message.chat.username).replace('@', '')

        if any(user in admins for user in [message.chat.id, username]):
            self.admin = True
        elif any(user in users for user in [message.chat.id, username]):
            self.admin = False
        else:
            self.admin = None
            try:
                bot.send_message(message.chat.id, "У вас нет доступа к данному боту")
                bot.delete_message(message.chat.id, message.message_id)
            except:
                pass

    def delete_recent_messages(self, message, count=10):
        if message.message_id:
            for id_ in range(max(1, message.message_id - count), message.message_id + 1):
                try:
                    bot.delete_message(chat_id=message.chat.id, message_id=id_)
                except:
                    pass

    def load_data(self):
        with open('config/config.json', 'r', encoding='utf-8') as file:
            return json.load(file)

    def write_data(self, data):
        # Сохраняем данные в файл
        with open('config/config.json', 'w', encoding='utf-8') as file:
            json.dump(data, file, ensure_ascii=False, indent=4)

    def start_main(self):
        bot.set_my_commands([BotCommand("start", "В начало"), BotCommand("back", "Назад")])

        @bot.message_handler(commands=['start'])
        def handle_start(message):
            self.delete_recent_messages(message)
            self.entry(message)
            if self.admin is not None:
                # очищаем начальные значения
                self.keys = []
                self.state_stack = {}
                self.show_start_menu(message)

        @bot.message_handler(commands=['back'])
        def handle_back(message):
            if list(self.state_stack.keys())[0] == 'Управление' and len(self.state_stack.keys()) > 1:
                while self.state_stack:
                    self.delete_recent_messages(message)
                    last_key, last_function = self.state_stack.popitem()
                    last_function()
                    break
            elif list(self.state_stack.keys())[0] == 'Начать' and self.keys:
                while self.state_stack:
                    if message.message_id:
                        try:
                            bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
                        except:
                            pass
                    self.keys.pop()
                    self.navigate()
                    break
            else:
                if message.message_id:
                    for id_ in range(max(1, message.message_id - 10), message.message_id + 1):
                        try:
                            bot.delete_message(chat_id=message.chat.id, message_id=id_)
                        except:
                            pass
                self.state_stack.clear()
                self.show_start_menu(message)

        @bot.callback_query_handler(func=lambda call: True)
        def handle_query(call):
            self.call = call
            self.entry(call.message)
            if self.admin is None:
                return

            # разделяем разные режими доступа как для обычных пользователей, так и для админов
            if self.call.data == 'Начать':
                self.state_stack.clear()
                self.state_stack[self.call.data] = self.show_start_menu
                self.navigate()
            elif self.admin:
                if self.call.data == "Управление":
                    self.state_stack.clear()
                    self.state_stack[self.call.data] = self.show_start_menu
                    self.control_buttons()
                if list(self.state_stack.keys())[0] == 'Управление':
                    if self.call.data == 'Доступ к боту':
                        if self.call.data not in self.state_stack:
                            self.state_stack[self.call.data] = self.control_buttons
                        self.add_dell_users()
                    elif self.call.data == 'Открыть доступ':
                        if self.call.data not in self.state_stack:
                            self.state_stack[self.call.data] = self.add_dell_users
                        self.control = True
                        self.del_buttons_commands()
                    elif self.call.data == 'Закрыть доступ':
                        if self.call.data not in self.state_stack:
                            self.state_stack[self.call.data] = self.add_dell_users
                        self.control = False
                        self.del_buttons_commands()

                    elif (self.call.data in self.load_data()[
                        "commands"].keys() or self.call.data == 'Админы') and self.control is False:
                        self.select_command = self.call.data if self.call.data != 'Админы' else 'admins'
                        self.close()
                    elif self.call.data == "save_dell":
                        self.dell_users_or_admins()

                    elif (self.call.data in self.load_data()[
                        "commands"].keys() or self.call.data == 'Админы') and self.control:
                        self.select_command = self.call.data if self.call.data != 'Админы' else 'admins'
                        self.open()

                    elif self.call.data.startswith("toggle_"):
                        if self.call.data.split("_")[2] not in ('Видео', 'Статистика'):
                            user_key = '_'.join(self.call.data.split("_")[1:])  # Извлекаем имя пользователя
                            if user_key in self.selected_users:
                                self.selected_users.remove(user_key)  # Убираем из списка
                            else:
                                self.selected_users.add(user_key)  # Добавляем в список
                            self.close()  # Перерисовываем кнопки с обновленными значениями
                        else:
                            user_key = '_'.join(self.call.data.split("_")[1:])  # Извлекаем имя пользователя

                            if user_key in self.selected_video_stat:
                                self.selected_video_stat.remove(user_key)  # Убираем из списка
                            else:
                                self.selected_video_stat.add(user_key)  # Добавляем в список
                            self.dell_video_statis()
                    elif self.call.data == "cancel_dell":
                        self.selected_users = set()
                        self.del_buttons_commands()
                    elif self.call.data == 'Редактирование команд':
                        if self.call.data not in self.state_stack:
                            self.state_stack[self.call.data] = self.control_buttons
                        self.control = None
                        self.del_buttons_commands()
                    elif (self.call.data in self.load_data()[
                        "commands"].keys()) and self.control is None:
                        self.select_command = self.call.data
                        self.edit_command()
                    elif self.call.data == 'Редактировать видео':
                        self.edit_video()
                    elif self.call.data == 'Редактировать ститистику':
                        self.edit_statistic()
                    elif self.call.data in ('Добавить ститистику', 'Добавить видео'):
                        self.add_video_statis()
                    elif self.call.data in ('Удалить ститистику', 'Удалить видео'):
                        get_data = 'Видео' if self.call.data.split(' ')[-1] == 'видео' else 'Статистика'
                        if get_data == 'Видео':
                            self.del_vd_stat = True
                        else:
                            self.del_vd_stat = False
                        self.dell_video_statis()
                    elif self.call.data == 'save_dell_video_stats':
                        self.dell_users_or_admins()
                    elif self.call.data == 'cancel_dell_video_stats':
                        self.selected_video_stat = set()
                        self.edit_command()
                else:
                    self.keys.append(self.call.data)
                    self.navigate()
            else:
                self.keys.append(self.call.data)
                self.navigate()

    def show_start_menu(self, message):
        self.markup = InlineKeyboardMarkup()
        self.markup.add(InlineKeyboardButton("Начать", callback_data="Начать"))
        if self.admin:
            self.markup.add(InlineKeyboardButton("Управление", callback_data="Управление"))
        with open('Volley.jpg', 'rb') as photo:
            bot.send_photo(message.chat.id, photo, reply_markup=self.markup)

    # Запуск бота
    def navigate(self):
        data = self.load_data()["commands"]

        if self.keys:
            for key in self.keys:
                data = data.get(key, {})
                # убираем список игроков
                data.pop('users', None)
            if isinstance(data, dict) and data:
                self.markup = InlineKeyboardMarkup()

                # Сортируем ключи в алфавитном порядке
                sorted_keys = sorted(data.keys())

                for k in sorted_keys:  # Используем отсортированные ключи
                    v = data[k]
                    if isinstance(v, str) and v.startswith("http"):
                        self.markup.add(InlineKeyboardButton(k, url=v))
                    else:
                        self.markup.add(
                            InlineKeyboardButton(k, callback_data=f"{k}" if self.call.data else k))

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
                    reply_markup=self.markup,
                    parse_mode="HTML"  # Включаем поддержку HTML
                )

        else:
            try:
                # Удаляем сообщение с фото
                bot.delete_message(self.call.message.chat.id, self.call.message.message_id)
            except:
                pass
            buttons = [InlineKeyboardButton(key, callback_data=key) for key in
                       list(self.load_data()["commands"].keys())]
            self.markup = InlineKeyboardMarkup([buttons])
            new_text = """Вы находитесь в разделе: <u>Главное меню</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"""
            bot.send_message(self.call.message.chat.id, new_text, reply_markup=self.markup)

    def control_buttons(self):
        try:
            buttons = [InlineKeyboardButton(key, callback_data=key) for key in
                       ["Доступ к боту", "Редактирование команд"]]
            self.markup = InlineKeyboardMarkup([buttons])
            new_text = """Вы находитесь в разделе: <u>Управление</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"""
            bot.edit_message_text(
                chat_id=self.call.message.chat.id,
                message_id=self.call.message.message_id,
                text=new_text,
                reply_markup=self.markup,
                parse_mode="HTML"  # Включаем поддержку HTML
            )
        except:
            try:
                # Удаляем сообщение с фото
                bot.delete_message(self.call.message.chat.id, self.call.message.message_id)
            except:
                pass
            buttons = [InlineKeyboardButton(key, callback_data=key) for key in
                       ["Доступ к боту", "Редактирование команд"]]
            self.markup = InlineKeyboardMarkup([buttons])
            new_text = """Вы находитесь в разделе: <u>Управление</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"""
            bot.send_message(self.call.message.chat.id, new_text, reply_markup=self.markup)

    def add_dell_users(self):
        self.markup = InlineKeyboardMarkup()
        self.markup.add(InlineKeyboardButton("Открыть доступ", callback_data="Открыть доступ"))
        self.markup.add(InlineKeyboardButton("Закрыть доступ", callback_data="Закрыть доступ"))
        new_text = """Вы находитесь в разделе: Управление - <u>Доступ к боту</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"""
        bot.edit_message_text(
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id,
            text=new_text,
            reply_markup=self.markup,
            parse_mode="HTML"  # Включаем поддержку HTML
        )

    def del_buttons_commands(self):

        self.data = self.load_data()["commands"]
        text = ''
        buttons = [InlineKeyboardButton(key, callback_data=key) for key in self.load_data()["commands"].keys()]
        self.markup = InlineKeyboardMarkup([buttons])
        if self.call.data != 'Редактирование команд':
            text = ' Доступ к боту -'
            self.markup.add(InlineKeyboardButton("Админы", callback_data="Админы"))

        new_text = f"Вы находитесь в разделе: Управление -{text} <u>{self.call.data}</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"
        bot.edit_message_text(
            new_text,
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id,
            reply_markup=self.markup
        )

    def close(self):
        self.markup = InlineKeyboardMarkup()
        buttons = []
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
        new_text = f"Вы находитесь в разделе: Управление - Доступ к боту - Закрыть доступ -  <u>{self.select_command}</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"

        bot.edit_message_text(
            new_text,
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id,
            reply_markup=self.markup
        )

    def dell_users_or_admins(self):
        # Загружаем данные из файла
        data = self.load_data()
        if self.selected_users:
            # Удаляем пользователей
            for user in self.selected_users:
                data_user = user.split("_")
                if data_user[-1] != 'admins':
                    # Удаляем пользователя из данных
                    if data_user[0] in data["commands"][data_user[-1]]["users"]:
                        del data["commands"][data_user[-1]]["users"][data_user[0]]
                else:
                    if data_user[0] in data["admins"]:
                        del data["admins"][data_user[0]]
            # Сохраняем обновленные данные обратно в файл
            self.write_data(data)  # Передаем измененные данные в функцию сохранения
            response_text = 'Сотрудники удалены' if len(self.selected_users) > 1 else 'Сотрудник удален'
            bot.answer_callback_query(self.call.id, response_text,
                                      show_alert=True)
            self.selected_users = set()
            self.del_buttons_commands()
        else:
            self.del_buttons_commands()

        if self.selected_video_stat:
            # Удаляем пользователей
            for user in self.selected_video_stat:
                data_user = user.split("_")
                if data_user[0] in data["commands"][data_user[-1]][data_user[-2]]:
                    del data["commands"][data_user[-1]][data_user[-2]][data_user[0]]
            # Сохраняем обновленные данные обратно в файл
            self.write_data(data)  # Передаем измененные данные в функцию сохранения
            response_text = 'Ссылки удалены' if len(self.selected_video_stat) > 1 else 'Ссылка удалена'
            bot.answer_callback_query(self.call.id, response_text,
                                      show_alert=True)
            self.selected_video_stat = set()
            self.edit_command()
        else:
            self.edit_command()

    def open(self):
        text = self.select_command if self.select_command != 'admins' else 'Админы'
        # Редактируем текущее сообщение, чтобы запросить имя сотрудника
        bot.edit_message_text(
            f"Вы находитесь в разделе: Управление - Доступ к боту - Открыть доступ - <u>{text}</u>.\n\nИспользуй "
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
            employee_name = str(message.text).replace(' ', '').replace('\n', ',').replace(',,', '').replace('@',
                                                                                                            '').split(
                ',')  # Получаем введенное имя сотрудника

            data = self.load_data()
            if ":" not in employee_name:
                for new_name in employee_name:
                    name, value = new_name.split(":")

                    if self.select_command != 'admins' and value not in data["commands"][self.select_command][
                        "users"].values():
                        data["commands"][self.select_command]["users"][name] = value
                    elif self.select_command == 'admins' and value not in data["admins"].values():
                        data["admins"][name] = value
                    else:
                        text = f'Пользователь с id: {value} уже существует'
                        bot.answer_callback_query(self.call.id, text,
                                                  show_alert=True)
                        try:
                            bot.delete_message(chat_id=message.chat.id,
                                               message_id=message.message_id)
                        except:
                            pass

                self.write_data(data)
                if len(employee_name) > 1:
                    text = "Пользователи добавлены"
                bot.answer_callback_query(self.call.id, text,
                                          show_alert=True)
                try:
                    bot.delete_message(chat_id=message.chat.id,
                                       message_id=message.message_id)
                except:
                    pass
                self.del_buttons_commands()
            else:
                try:
                    bot.delete_message(chat_id=message.chat.id,
                                       message_id=message.message_id)
                except:
                    pass
                response_test = 'Некорректное добавление, ознакомьтесь с примерами и попробуйте еще раз'
                bot.answer_callback_query(self.call.id, response_test,
                                          show_alert=True)
        else:
            if message.message_id:
                for id_ in range(max(1, message.message_id - 1), message.message_id + 1):
                    try:
                        bot.delete_message(chat_id=message.chat.id, message_id=id_)
                    except:
                        pass
            self.del_buttons_commands()

    def edit_command(self):
        self.markup = InlineKeyboardMarkup()
        self.markup.add(InlineKeyboardButton("Редактировать видео", callback_data="Редактировать видео"))
        self.markup.add(InlineKeyboardButton("Редактировать ститистику", callback_data="Редактировать ститистику"))
        new_text = f"""Вы находитесь в разделе: Управление - Редактирование команд - <u>{self.select_command}</u>\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"""
        bot.edit_message_text(
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id,
            text=new_text,
            reply_markup=self.markup,
            parse_mode="HTML"  # Включаем поддержку HTML
        )

    def edit_video(self):
        self.markup = InlineKeyboardMarkup()
        self.markup.add(InlineKeyboardButton("Добавить видео", callback_data="Добавить видео"))
        self.markup.add(InlineKeyboardButton("Удалить видео", callback_data="Удалить видео"))
        new_text = f"""Вы находитесь в разделе: Управление - Редактирование команд - {self.select_command} - <u>Редактировать видео</u>\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"""
        bot.edit_message_text(
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id,
            text=new_text,
            reply_markup=self.markup,
            parse_mode="HTML"  # Включаем поддержку HTML
        )

    def edit_statistic(self):
        self.markup = InlineKeyboardMarkup()
        self.markup.add(InlineKeyboardButton("Добавить ститистику", callback_data="Добавить ститистику"))
        self.markup.add(InlineKeyboardButton("Удалить ститистику", callback_data="Удалить ститистику"))
        new_text = f"""Вы находитесь в разделе: Управление - Редактирование команд - {self.select_command} - <u>Редактировать ститистику</u>\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"""
        bot.edit_message_text(
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id,
            text=new_text,
            reply_markup=self.markup,
            parse_mode="HTML"  # Включаем поддержку HTML
        )

    def add_video_statis(self):
        # Редактируем текущее сообщение, чтобы запросить имя сотрудника
        bot.edit_message_text(
            f"Вы находитесь в разделе: Управление - Редактирование команд - {self.select_command} - Редактировать {self.call.data.split(' ')[-1]} - <u>{self.call.data}</u> .\n\nИспользуй "
            f"кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start "
            f"\n\nНапишите название  и ссылку на видео для добавления через двоеточие, пример:\nСезон 2024-2025:https://disk.yandex.ru/d/bWFMzczzg"
            f"\nТакже можно добавлять списком несколько ссылок через запятую, "
            f"пример:\nСезон 2024-2025:https://disk.yandex.ru/d/bWFMzczzg, Сезон 2025-2026:https://disk.yandex.ru/d/bW343Mzczzg",
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id
        )

        # Устанавливаем состояние ожидания ответа от пользователя
        bot.register_next_step_handler(self.call.message,
                                       self.add_list)

    def add_list(self, message):
        get_video_stats = 'Видео' if self.call.data.split(' ')[-1] == 'видео' else 'Статистика'
        if message.text not in ['/back',
                                '/start']:
            new_video_stats = str(message.text).replace(' ', '').replace('\n', ',').replace(',,', '').replace('@',
                                                                                                              '').split(
                ',')  # Получаем введенное имя сотрудника

            data = self.load_data()
            if ":" not in new_video_stats:
                for new_name in new_video_stats:
                    name, value = new_name.split(":", 1)

                    if value not in data["commands"][self.select_command][
                        get_video_stats].values():
                        data["commands"][self.select_command][get_video_stats][name] = value
                    else:
                        text = f'Ссылка {value} уже существует'
                        bot.answer_callback_query(self.call.id, text,
                                                  show_alert=True)
                        try:
                            bot.delete_message(chat_id=message.chat.id,
                                               message_id=message.message_id)
                        except:
                            pass

                self.write_data(data)
                text = 'Ссылка добавлена'
                if len(new_video_stats) > 1:
                    text = "Ссылки добавлены"
                bot.answer_callback_query(self.call.id, text,
                                          show_alert=True)
                try:
                    bot.delete_message(chat_id=message.chat.id,
                                       message_id=message.message_id)
                except:
                    pass

                if get_video_stats == 'Видео':
                    self.edit_video()
                else:
                    self.edit_statistic()
            else:
                try:
                    bot.delete_message(chat_id=message.chat.id,
                                       message_id=message.message_id)
                except:
                    pass
                response_test = 'Некорректное добавление, ознакомьтесь с примерами и попробуйте еще раз'
                bot.answer_callback_query(self.call.id, response_test,
                                          show_alert=True)
        else:
            if message.message_id:
                for id_ in range(max(1, message.message_id - 1), message.message_id + 1):
                    try:
                        bot.delete_message(chat_id=message.chat.id, message_id=id_)
                    except:
                        pass
            elif get_video_stats == 'Видео':
                self.edit_video()
            else:
                self.edit_statistic()

    def dell_video_statis(self):
        self.markup = InlineKeyboardMarkup()
        buttons = []
        text = ['Статистика', 'статистику']
        if self.del_vd_stat:
            text = ['Видео', 'видео']
        for keys, value in self.load_data()["commands"][self.select_command][text[0]].items():
            is_selected = f"{keys}_{text[0]}_{self.select_command}" in self.selected_video_stat  # Проверяем, выбран ли пользователь
            icon = "✅" if is_selected else "❌"  # Меняем иконку
            button_text = f"{icon} {keys}"
            item = types.InlineKeyboardButton(button_text,
                                              callback_data=f"toggle_{keys}_{text[0]}_{self.select_command}")
            buttons.append(item)

        self.markup.add(*buttons)

        save = InlineKeyboardButton("💾 Сохранить!", callback_data='save_dell_video_stats')
        cancel = InlineKeyboardButton("Отмена!", callback_data='cancel_dell_video_stats')
        self.markup.add(cancel, save)
        new_text = f"Вы находитесь в разделе: Управление - Редактирование команд - {self.select_command} - Редактировать {text[-1]} - <u>Удалить {text[-1]}</u> .\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"

        bot.edit_message_text(
            new_text,
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id,
            reply_markup=self.markup
        )


if __name__ == "__main__":
    while True:
        try:
            Main()
            bot.infinity_polling(timeout=90, long_polling_timeout=5)
        except:
            continue
