import json
import telebot
from telebot import types
from config.auto_search_dir import data_config, path_to_config_json, path_to_img_volley, path_to_img_fish
from telebot.types import BotCommand, InlineKeyboardMarkup, InlineKeyboardButton
from telebot.apihelper import ApiException

bot = telebot.TeleBot(data_config['my_telegram_bot']['bot_token'], parse_mode='HTML')


class Main:
    def __init__(self):
        self.state_stack = {}  # Стек для хранения состояний
        self.selected_users = set()
        self.selected_video_stat = set()
        self.keys = []
        self.select_command = None
        self.markup = None
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

    def load_data(self):
        with open(path_to_config_json, 'r', encoding='utf-8') as file:
            return json.load(file)

    def write_data(self, data):
        # Сохраняем данные в файл
        with open(path_to_config_json, 'w', encoding='utf-8') as file:
            json.dump(data, file, ensure_ascii=False, indent=4)

    def start_main(self):
        bot.set_my_commands([BotCommand("start", "В начало"), BotCommand("back", "Назад")])

        @bot.message_handler(commands=['start'])
        def handle_start(message):
            if message.message_id:
                try:
                    bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
                except:
                    pass
            self.entry(message)
            if self.admin is not None:
                # очищаем начальные значения
                self.keys.clear()
                self.state_stack.clear()
                self.show_start_menu(message)

        @bot.message_handler(commands=['back'])
        def handle_back(message):
            self.entry(message)
            if message.message_id:
                try:
                    bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
                except:
                    pass
            if self.admin is None:
                return
            elif 'Начать' in self.state_stack.keys() and self.keys:
                self.keys.pop()
                self.navigate()
            elif 'Управление' in self.state_stack.keys():
                if len(self.state_stack) == 1:
                    self.state_stack.clear()
                    self.show_start_menu(message)
                    return
                elif list(self.state_stack.keys())[-1] in ('Редактировать статистику', 'Редактировать видео'):
                    del self.state_stack[str(list(self.state_stack.keys())[-1])]
                    self.edit_command()
                else:
                    while self.state_stack:
                        # Получаем последний ключ
                        last_key = next(reversed(self.state_stack))
                        last_function = self.state_stack[last_key]
                        try:

                            # Попытка вызвать функцию
                            last_function()
                            break  # Выход из цикла, если вызов завершился успешно
                        except:
                            # Если произошла ошибка, удаляем элемент и продолжаем цикл
                            del self.state_stack[last_key]

                            # Если возникла ошибка, продолжаем цикл, чтобы вызвать следующую функцию
            else:
                self.keys.clear()
                self.state_stack.clear()
                self.show_start_menu(message)

        @bot.callback_query_handler(func=lambda call: True)
        def handle_query(call):
            self.call = call
            self.entry(call.message)
            if self.admin is None:
                return

            elif 'Начать' in [self.call.data] + list(self.state_stack.keys()):
                if not self.state_stack:
                    self.state_stack[self.call.data] = self.show_start_menu
                else:
                    self.keys.append(self.call.data)
                self.navigate()
            actions = {
                "Управление": self.control_buttons,
                "Доступ к боту": self.add_dell_users,
                "Открыть доступ": self.del_buttons_commands,
                "Закрыть доступ": self.del_buttons_commands,
                "Редактирование команд": self.del_buttons_commands,
                "💾 Закрыть доступ!": self.dell_users_or_admins,
                "cancel_dell": self.dell_users_or_admins,
                "Редактировать статистику": self.edit_statistic,
                "Редактировать видео": self.edit_video,
                "Добавить видео": self.add_video_statis,
                "Добавить статистику": self.add_video_statis,
                "Удалить видео": self.dell_video_statis,
                "Удалить статистику": self.dell_video_statis,
                "save_dell_video_stats": self.dell_users_or_admins,
                "cancel_dell_video_stats": self.dell_users_or_admins
            }
            if self.admin:
                if 'Управление' in [self.call.data] + list(self.state_stack.keys()):
                    if self.call.data in (actions.keys()):
                        self.state_stack[self.call.data] = actions[self.call.data]
                        actions[self.call.data]()

                    elif self.call.data in list(self.load_data()["commands"].keys()) + ['admins']:
                        if list(self.state_stack.keys())[-1] == 'Закрыть доступ':
                            self.select_command = self.call.data
                            self.close()
                        elif list(self.state_stack.keys())[-1] == 'Открыть доступ':
                            self.select_command = self.call.data
                            self.open()
                        elif list(self.state_stack.keys())[-1] == 'Редактирование команд':
                            self.select_command = self.call.data
                            self.edit_command()
                    elif self.call.data.startswith("toggle_"):
                        user_key = '_'.join(self.call.data.split("_")[1:])  # Извлекаем имя пользователя
                        if list(self.state_stack.keys())[-1] == 'Закрыть доступ':
                            if user_key in self.selected_users:
                                self.selected_users.remove(user_key)  # Убираем из списка
                            else:
                                self.selected_users.add(user_key)  # Добавляем в список
                            self.close()  # Перерисовываем кнопки с обновленными значениями
                        elif list(self.state_stack.keys())[-1] in ('Удалить видео', 'Удалить статистику'):
                            if user_key in self.selected_video_stat:
                                self.selected_video_stat.remove(user_key)  # Убираем из списка
                            else:
                                self.selected_video_stat.add(user_key)  # Добавляем в список
                            self.dell_video_statis()

    def show_start_menu(self, message):
        self.markup = InlineKeyboardMarkup()
        self.markup.add(InlineKeyboardButton("Начать", callback_data="Начать"))
        response_text = f"""Вы находитесь в разделе: <u>Главное меню</u>\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:""",
        if self.admin:
            self.markup.add(InlineKeyboardButton("Управление", callback_data="Управление"))
        try:
            bot.edit_message_text(
                chat_id=self.call.message.chat.id,
                message_id=self.call.message.message_id,
                text=response_text,
                reply_markup=self.markup,
                parse_mode="HTML"  # Включаем поддержку HTML
            )
        except ApiException as e:
            if "Message is not modified" in str(e):
                return  # Просто игнорируем ошибку, так как сообщение уже актуально
            if self.load_data()["commands"]['RedHeads']['users']:
                if any(user in self.load_data()["commands"]['RedHeads']['users'].values() for user in
                       [message.chat.id, str(message.chat.username).replace('@', '')]):
                    with open(path_to_img_fish, 'rb') as photo:
                        bot.send_photo(message.chat.id, photo)
                else:
                    with open(path_to_img_volley, 'rb') as photo:
                        bot.send_photo(message.chat.id, photo)
            else:
                with open(path_to_img_volley, 'rb') as photo:
                    bot.send_photo(message.chat.id, photo)

            bot.send_message(chat_id=message.chat.id, text=response_text, reply_markup=self.markup)

    # Запуск бота
    def navigate(self):
        data = self.load_data()["commands"]

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
                full_path = f"Главное меню - Команды - {section_path}"  # Добавляем "Главное меню" в начало
            else:
                full_path = "Главное меню - <u>Команды</u>"  # Если ключей нет, просто "Главное меню"

            bot.edit_message_text(
                chat_id=self.call.message.chat.id,
                message_id=self.call.message.message_id,
                text=f"""Вы находитесь в разделе: {full_path}\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:""",
                reply_markup=self.markup,
                parse_mode="HTML"  # Включаем поддержку HTML
            )

    def control_buttons(self):
        buttons = [InlineKeyboardButton(key, callback_data=key) for key in
                   ["Доступ к боту", "Редактирование команд"]]
        self.markup = InlineKeyboardMarkup([buttons])
        new_text = """Вы находитесь в разделе: Главное меню - <u>Управление</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"""
        bot.edit_message_text(
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id,
            text=new_text,
            reply_markup=self.markup,
            parse_mode="HTML"  # Включаем поддержку HTML
        )

    def add_dell_users(self):
        self.markup = InlineKeyboardMarkup()
        self.markup.add(InlineKeyboardButton("Открыть доступ", callback_data="Открыть доступ"))
        self.markup.add(InlineKeyboardButton("Закрыть доступ", callback_data="Закрыть доступ"))
        new_text = """Вы находитесь в разделе: Главное меню - Управление -  <u>Доступ к боту</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"""
        bot.edit_message_text(
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id,
            text=new_text,
            reply_markup=self.markup,
            parse_mode="HTML"  # Включаем поддержку HTML
        )

    def del_buttons_commands(self):
        print(self.call.data)
        print(list(self.state_stack.keys()))
        buttons = [InlineKeyboardButton(key, callback_data=key) for key in self.load_data()["commands"].keys()]
        self.markup = InlineKeyboardMarkup([buttons])

        text_responce = ''
        if self.call.data in ('Открыть доступ', 'Закрыть доступ'):
            text_responce = f"Доступ к боту - <u>{self.call.data}</u>"
            self.markup.add(InlineKeyboardButton("Админы", callback_data="admins"))
        elif self.call.data in ["Доступ к боту", 'Редактирование команд']:
            text_responce = f"<u>{self.call.data}</u>"
        elif self.call.data in ['💾 Закрыть доступ!', 'cancel_dell', 'admins'] + list(
                self.load_data()["commands"].keys()) and list(self.state_stack.keys())[-1] == 'Закрыть доступ':
            text_responce = f"Доступ к боту - <u>Закрыть доступ</u>"
            self.markup.add(InlineKeyboardButton("Админы", callback_data="admins"))
        elif self.call.data in list(self.load_data()["commands"].keys()) and list(self.state_stack.keys())[
            -1] in ('Редактирование команд'):
            text_responce = f"Доступ к боту - <u>Редактирование команд</u>"
        elif list(self.state_stack.keys())[-1] in ('Редактирование команд'):
            text_responce = f"Доступ к боту - <u>Редактирование команд</u>"
        new_text = f"Вы находитесь в разделе: Главное меню - Управление - {text_responce}.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"
        bot.edit_message_text(
            new_text,
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id,
            reply_markup=self.markup
        )

    def close(self):
        self.markup = InlineKeyboardMarkup()
        buttons = []
        users = (
            self.load_data()["commands"][self.select_command]["users"].items() if self.select_command != 'admins' else
            self.load_data()[self.select_command].items())
        for keys, value in users:
            is_selected = f"{keys}_{value}_{self.select_command}" in self.selected_users  # Проверяем, выбран ли пользователь
            icon = "✅" if is_selected else "❌"  # Меняем иконку
            button_text = f"{icon} {keys}({value})"
            item = types.InlineKeyboardButton(button_text,
                                              callback_data=f"toggle_{keys}_{value}_{self.select_command}")
            buttons.append(item)

        self.markup.add(*buttons)
        select_command = 'Админы' if self.select_command == 'admins' else self.select_command
        save = InlineKeyboardButton("💾 Закрыть доступ!", callback_data='💾 Закрыть доступ!')
        cancel = InlineKeyboardButton("Отмена!", callback_data='cancel_dell')
        self.markup.add(cancel, save)
        new_text = f"Вы находитесь в разделе: Главное меню - Управление -  Доступ к боту - Закрыть доступ -  <u>{select_command}</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"

        bot.edit_message_text(
            new_text,
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id,
            reply_markup=self.markup
        )

    def dell_users_or_admins(self):

        # Загружаем данные из файла
        data = self.load_data()
        if self.select_command == 'admins' and len(self.load_data()['admins'].keys()) == 1 and self.selected_users:
            response_text = 'Должен быть минимум 1 админ, пользователь НЕ УДАЛЕН'
            bot.answer_callback_query(self.call.id, response_text,
                                      show_alert=True)
            self.selected_users = set()
            self.state_stack = dict(list(self.state_stack.items())[:-2])

            self.del_buttons_commands()
            return

        elif self.select_command and self.selected_users:
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
            response_text = 'Пользователи удалены' if len(self.selected_users) > 1 else 'Пользователь удален'
            bot.answer_callback_query(self.call.id, response_text,
                                      show_alert=True)
            self.selected_users = set()
            self.state_stack = dict(list(self.state_stack.items())[:-1])
            self.del_buttons_commands()

        elif self.selected_video_stat:
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
            self.state_stack = dict(list(self.state_stack.items())[:-2])
            self.edit_command()
        elif str(list(self.state_stack.keys())[-2]) not in ('Удалить статистику', 'Удалить видео'):
            self.selected_users = set()
            self.selected_video_stat = set()
            self.state_stack = dict(list(self.state_stack.items())[:-2])
            self.del_buttons_commands()
        elif str(list(self.state_stack.keys())[-2]) in ('Удалить статистику', 'Удалить видео'):
            self.selected_users = set()
            self.selected_video_stat = set()
            self.state_stack = dict(list(self.state_stack.items())[:-2])
            if str(list(self.state_stack.keys())[-1]) == 'Удалить статистику':
                self.edit_statistic()
            else:
                self.edit_video()

    def open(self):
        text = self.select_command if self.select_command != 'admins' else 'Админы'
        # Редактируем текущее сообщение, чтобы запросить имя сотрудника
        bot.edit_message_text(
            f"Вы находитесь в разделе: Главное меню - Управление -  Доступ к боту - Открыть доступ - <u>{text}</u>.\n\nИспользуй "
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
            if ":" in str(message.text):
                employee_name = str(message.text).replace(' ', '').replace('\n', ',').replace(',,', '').replace('@',
                                                                                                                '').split(
                    ',')  # Получаем введенное имя сотрудника

                data = self.load_data()

                for new_name in employee_name:
                    name, value = new_name.split(":")
                    if len(name) >= 4 and len(value) >= 4:
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
                    else:
                        try:
                            bot.delete_message(chat_id=message.chat.id,
                                               message_id=message.message_id)
                        except:
                            pass
                        response_test = 'Ник или id должно быть минимум 4 символа'
                        bot.answer_callback_query(self.call.id, response_test,
                                                  show_alert=True)
                        self.selected_users = set()
                        self.selected_video_stat = set()
                        self.call.data = 'Открыть доступ'
                        self.del_buttons_commands()
                        return
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
                self.selected_users = set()
                self.selected_video_stat = set()
                self.call.data = 'Открыть доступ'
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
            try:
                bot.delete_message(chat_id=message.chat.id,
                                   message_id=message.message_id)
            except:
                pass
            self.selected_users = set()
            self.selected_video_stat = set()
            self.call.data = 'Открыть доступ'
            self.del_buttons_commands()

    def edit_command(self):
        self.markup = InlineKeyboardMarkup()
        self.markup.add(InlineKeyboardButton("Редактировать видео", callback_data="Редактировать видео"))
        self.markup.add(InlineKeyboardButton("Редактировать ститистику", callback_data="Редактировать статистику"))
        new_text = f"""Вы находитесь в разделе: Главное меню - Управление -  Редактирование команд - <u>{self.select_command}</u>\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"""
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
        new_text = f"""Вы находитесь в разделе: Главное меню - Управление -  Редактирование команд - {self.select_command} - <u>Редактировать видео</u>\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"""
        bot.edit_message_text(
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id,
            text=new_text,
            reply_markup=self.markup,
            parse_mode="HTML"  # Включаем поддержку HTML
        )

    def edit_statistic(self):
        self.markup = InlineKeyboardMarkup()
        self.markup.add(InlineKeyboardButton("Добавить статистику", callback_data="Добавить статистику"))
        self.markup.add(InlineKeyboardButton("Удалить статистику", callback_data="Удалить статистику"))
        new_text = f"""Вы находитесь в разделе: Главное меню - Управление -  Редактирование команд - {self.select_command} - <u>Редактировать ститистику</u>\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"""
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
            f"Вы находитесь в разделе: Главное меню - Управление -  Редактирование команд - {self.select_command} - Редактировать {self.call.data.split(' ')[-1]} - <u>{self.call.data}</u> .\n\nИспользуй "
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
            if ":" in str(message.text):
                new_video_stats = str(message.text).replace(' ', '').replace('\n', ',').replace(',,', '').replace('@',
                                                                                                                  '').split(
                    ',')  # Получаем введенное имя сотрудника

                data = self.load_data()
                for new_name in new_video_stats:
                    name, value = new_name.split(":", 1)
                    if len(name) >= 4 and len(value) >= 4 and value[:4] == 'http':
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
                    else:
                        try:
                            bot.delete_message(chat_id=message.chat.id,
                                               message_id=message.message_id)
                        except:
                            pass
                        response_test = 'Неправильны указаны значения. Ожидается длина ключа и значения минимум 4 знака и ссылка должна начинаться с http'
                        bot.answer_callback_query(self.call.id, response_test,
                                                  show_alert=True)
                        self.state_stack = dict(list(self.state_stack.items())[:-1])
                        if get_video_stats == 'Видео':
                            self.edit_video()
                        else:
                            self.edit_statistic()
                        return
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
                self.state_stack = dict(list(self.state_stack.items())[:-1])
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
                response_test = ''
                bot.answer_callback_query(self.call.id, response_test,
                                          show_alert=True)
                self.state_stack = dict(list(self.state_stack.items())[:-1])
                if get_video_stats == 'Видео':
                    self.edit_video()
                else:
                    self.edit_statistic()
        else:
            if message.message_id:
                try:
                    bot.delete_message(chat_id=message.chat.id,
                                       message_id=message.message_id)
                except:
                    pass
            self.state_stack = dict(list(self.state_stack.items())[:-1])
            if get_video_stats == 'Видео':
                self.edit_video()
            else:
                self.edit_statistic()

    def dell_video_statis(self):
        self.markup = InlineKeyboardMarkup()
        buttons = []
        text = ['Статистика', 'статистику']

        if list(self.state_stack.keys())[-2] == 'Редактировать видео':
            text = ['Видео', 'видео']
        for keys, value in self.load_data()["commands"][self.select_command][text[0]].items():
            is_selected = f"{keys}_{text[0][:5]}_{self.select_command}" in self.selected_video_stat  # Проверяем, выбран ли пользователь
            icon = "✅" if is_selected else "❌"  # Меняем иконку
            button_text = f"{icon} {keys}"
            item = types.InlineKeyboardButton(button_text,
                                              callback_data=f"toggle_{keys}_{text[0][:5]}_{self.select_command}")
            buttons.append(item)

        self.markup.add(*buttons)

        save = InlineKeyboardButton("💾 Сохранить!", callback_data='save_dell_video_stats')
        cancel = InlineKeyboardButton("Отмена!", callback_data='cancel_dell_video_stats')
        self.markup.add(cancel, save)
        new_text = f"Вы находитесь в разделе: Главное меню - Управление -  Редактирование команд - {self.select_command} - Редактировать {text[-1]} - <u>Удалить {text[-1]}</u> .\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"

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
