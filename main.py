import json
import schedule as schedule
import telebot
from telebot import types
from config.auto_search_dir import data_config, path_to_config_json, path_to_img_volley, path_to_img_fish
from telebot.types import BotCommand, InlineKeyboardMarkup, InlineKeyboardButton
import calendar
import uuid
from datetime import datetime, timedelta

bot = telebot.TeleBot(data_config['my_telegram_bot']['bot_token'], parse_mode='HTML')
tmonth_names = {
    1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель", 5: "Май", 6: "Июнь",
    7: "Июль", 8: "Август", 9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
}
# Список дней недели на русском
days_week = [
    "Понедельник",  # 0
    "Вторник",  # 1
    "Среда",  # 2
    "Четверг",  # 3
    "Пятница",  # 4
    "Суббота",  # 5
    "Воскресенье"  # 6
]
# Словарь для хранения пользователей, проголосовавших за каждый вариант
poll_results = {}


class Main:
    def __init__(self):
        self.state_stack = {}  # Стек для хранения состояний
        self.selected_users = set()
        self.selected_send_users = set()
        self.selected_video = set()
        self.selected_stat = set()
        self.selected_edit_users = set()
        self.current_index = 0
        self.data = None
        self.surveys = None
        self.user_data = {}
        self.unique_id = None
        self.keys = []
        self.hour = 2
        self.select_command = None
        self.markup = None
        self.call = None
        self.admin = None
        self.survey()
        self.start_main()

    # отправка, закрытие, получение результатов опроса
    def survey(self):
        data = self.load_data()
        if data['surveys']:  # Проверяем, есть ли ключ 'surveys'
            for key, value in data['surveys'].items():

                users = [str(user).replace("@", '') for command in str(value['Получатели опроса']).replace("Админы",
                                                                                                           "admins").split(
                    ',') for user in
                         (data['admins'].values() if command == "admins" else data['commands'][command][
                             "users"].values())]
                # Заданная дата
                target_date = datetime.strptime(f"{value['Дата отправки опроса']} {value['Время отправки опроса']}",
                                                "%d-%m-%Y %H:%M")

                target_date2 = datetime.strptime(
                    f"{value['Дата тренировки/игры']} {str(value['Время тренировки/игры']).split(' - ')[0]}",
                    "%d-%m-%Y %H:%M"
                ) - timedelta(minutes=30)
                day_index = days_week[target_date2.weekday()]

                current_date = datetime.now().replace(second=0, microsecond=0)
                # отправка опроса
                if target_date == current_date and target_date2 >= current_date and value[
                    'Опрос отправлен'] == 'Нет' and value['Получатели опроса']:
                    # question = f"{value['Тип']} {day_index} c {str(value['Время тренировки/игры']).replace(' - ', ' до ')} стоймость {value['Цена']}р"
                    question = f"{value['Тип']} {value['Дата тренировки/игры']} ({day_index}) c {str(value['Время тренировки/игры']).replace(' - ', ' до ')} стоймость {value['Цена']}р .\nАдрес: {value['Адрес']}"
                    # Получение дня недели

                    options = ["Буду", "+1"]
                    for user in users:

                        try:
                            user_chat = user.split("_")[-1]
                            poll_message = bot.send_poll(
                                chat_id=user_chat,
                                question=question,
                                options=options,
                                close_date=target_date2,
                                is_anonymous=False,  # Ответы будут видны боту
                                allows_multiple_answers=False,
                                explanation_parse_mode='HTML'
                            )

                            value['Опрос отправлен'] = "Да"
                            value["Опрос открыт"] = "Да"
                            value['id опроса'] = poll_message.poll.id
                            self.write_data(data)

                        except Exception as e:
                            print(f"Ошибка при отправке опроса пользователю {user}: {e}")
                # опрос автоматически закрывается, когда наступает время закрытие, то изменяем также значения
                elif target_date2 <= current_date and 'Да' in (value['Опрос открыт'], value['Опрос отправлен']):
                    value["Опрос открыт"] = "Нет"
                    self.write_data(data)

    def entry(self, message):
        # Изменить условия фильтрования доступа :
        data = self.load_data()
        admins = list(str(value.replace('@', '')).split("_")[0] for value in data["admins"].values())

        users = [str(name.replace('@', '')).split("_")[0] for command in data["commands"].keys() for name
                 in data["commands"][command]["users"].values()]
        username = str(message.chat.username).replace('@', '')
        if any(user in admins for user in [message.chat.id, username]):
            # Значение, которое мы хотим изменить
            # Ищем ключ по значению и изменяем его

            for key, value in data["admins"].items():
                if value.replace("@", '') in (username, message.chat.id) and len(
                        str(value.replace("@", '')).split('_')) == 1:
                    new_value = value + str(f"_{message.chat.id}")
                    data["admins"][key] = new_value
                    self.write_data(data)
                    break  # Выходим из цикла, если нашли и изменили значение

            self.admin = True
        elif any(user in users for user in [message.chat.id, username]):
            # Значение, которое мы хотим изменить
            # Ищем ключ по значению и изменяем его
            for command in data["commands"].keys():
                for key, value in data["commands"][command]["users"].items():
                    if value.replace("@", '') in (username, message.chat.id) and len(
                            str(value.replace("@", '')).split('_')) == 1:
                        new_value = value + str(f"_{message.chat.id}")
                        data["commands"][command]["users"][key] = new_value
                        self.write_data(data)
                        break  # Выходим из цикла, если нашли и изменили значение
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

        @bot.poll_answer_handler(func=lambda answer: True)
        def handle_poll_answer(answer):
            user_id = answer.user.id
            poll_id = answer.poll_id
            option_ids = 0 if not answer.option_ids else '+1' if answer.option_ids[0] == 1 else 'Буду'

            data = self.load_data()
            if data['surveys']:  # Проверяем, есть ли ключ 'surveys'
                for key, value in data['surveys'].items():
                    if value["id опроса"] == str(poll_id):
                        for command in str(value['Получатели опроса']).split(','):

                            for user, id_ in (
                                    data['commands'][command]['users'].items() if command != 'Админы' else data[
                                        'admins'].items()):
                                # Ваш код здесь

                                if str(user_id) == id_.split('_')[-1]:
                                    if command not in value["Отметились"]:
                                        value["Отметились"][command] = {}

                                    value["Отметились"][command][f'{user}({user_id})'] = option_ids
                                    value['Количество отметившихся'] = len(
                                        set(user for command in value["Отметились"].keys()
                                            for user, val in value["Отметились"][command].items()
                                            if val != 0))

                        self.write_data(data)

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
                self.selected_users.clear()
                self.selected_video.clear()
                self.selected_stat.clear()
                self.user_data.clear()
                self.selected_send_users.clear()
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
                return
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
            else:
                self.keys.clear()
                self.state_stack.clear()
                self.selected_users.clear()
                self.selected_video.clear()
                self.selected_stat.clear()
                self.show_start_menu(message)

        @bot.callback_query_handler(func=lambda call: True)
        def handle_query(call):
            self.call = call
            self.entry(call.message)
            actions = {
                "Управление": self.control_buttons,
                "Доступ к боту": self.main_control,
                "Открыть доступ": self.open_control,
                "Закрыть доступ": self.close_control,
                "💾 Закрыть доступ!": self.dell_users,
                "cancel_dell": self.dell_users,
                "Редактирование команд": self.edit_commands,
                "Редактировать видео": self.edit_video,
                "Добавить видео": self.add_video,
                "Удалить видео": self.dell_video,
                "save_dell_video": self.save_del_video,
                "cancel_dell_video": self.edit_video,
                "Редактировать статистику": self.edit_statistic,
                "Добавить статистику": self.add_static,
                "Удалить статистику": self.dell_stitistic,
                "save_dell_stat": self.save_del_statistic,
                "cancel_dell_stat": self.edit_statistic,
                "Опрос": self.the_survey,
                "Новый опрос": self.type_play,
                "cancel_send_survey": self.the_survey,
                "save_send_survey": self.save,
                "Удалить опрос": self.del_survey,
                "cansel_survey": self.the_survey,
                "dell_survey": self.save_dell_survey,
                "Редактировать опрос": self.edit_survey,
                "typeedit_survey": self.typeedit_survey,
                "dateedit_survey": self.dateedit_survey,
                "timeedit_survey": self.timeedit_survey,
                "addressedit_survey": self.addressedit_survey,
                "priceedit_survey": self.priceedit_survey,
                "datesend_survey": self.datesend_survey,
                "timesend_survey": self.timesend_survey,
                "Результаты опросов": self.result_surveys,
                "Напоминание": self.reminder,
                "Создать напоминание": self.datesend_reminder

            }

            if self.admin is None:
                return

            elif self.call.data not in ('Управление', 'Начать') and not self.state_stack:
                self.show_start_menu(call.message)

            elif 'Начать' in [self.call.data] + list(self.state_stack.keys()):
                if not self.state_stack:
                    self.state_stack[self.call.data] = self.show_start_menu
                else:
                    self.keys.append(self.call.data)
                self.navigate()
            else:

                if self.call.data in (actions.keys()):
                    self.state_stack[self.call.data] = actions[self.call.data]
                    actions[self.call.data]()
                elif self.call.data.startswith("cal_"):
                    date_str = self.call.data[4:]  # Убираем "cal_"
                    bot.send_message(self.call.message.chat.id, f"Вы выбрали {date_str}",
                                     reply_markup=types.ReplyKeyboardRemove())

                elif self.call.data in list(self.load_data()["commands"].keys()) + ['Админы']:
                    if list(self.state_stack.keys())[-1] == 'Закрыть доступ':
                        self.select_command = self.call.data
                        self.close()
                    elif list(self.state_stack.keys())[-1] == 'Открыть доступ':
                        self.select_command = self.call.data
                        self.open()
                    elif list(self.state_stack.keys())[-1] == 'Редактирование команд':
                        self.select_command = self.call.data
                        self.state_stack["command"] = self.edit_command
                        self.edit_command()
                elif self.call.data.startswith("toggle_"):
                    user_key = '_'.join(self.call.data.split("_")[1:])  # Извлекаем имя пользователя
                    if list(self.state_stack.keys())[-1] == 'Закрыть доступ':
                        if user_key in self.selected_users:
                            self.selected_users.remove(user_key)  # Убираем из списка
                        else:
                            self.selected_users.add(user_key)  # Добавляем в список
                        self.close()  # Перерисовываем кнопки с обновленными значениями
                    elif list(self.state_stack.keys())[-1] == 'Удалить видео':
                        if user_key in self.selected_video:
                            self.selected_video.remove(user_key)  # Убираем из списка
                        else:
                            self.selected_video.add(user_key)  # Добавляем в список
                        self.dell_video()
                    elif list(self.state_stack.keys())[-1] == 'Удалить статистику':
                        if user_key in self.selected_stat:
                            self.selected_stat.remove(user_key)  # Убираем из списка
                        else:
                            self.selected_stat.add(user_key)  # Добавляем в список
                        self.dell_stitistic()
                elif call.data in ("Товарищеская игра", "Тренировка", "Игра"):
                    self.unique_id = str(uuid.uuid4())  # Генерирует случайный UUID версии 4
                    if self.unique_id not in self.user_data:
                        self.user_data[self.unique_id] = {}  # Создаем запись для уникального ID
                    self.user_data[self.unique_id]['Тип'] = f"{call.data}"
                    if not self.state_stack:
                        self.state_stack[self.call.data] = self.type_play
                    self.new_survey()
                elif call.data.startswith("prev_") or call.data.startswith("next_"):
                    _, year, month = call.data.split("_")
                    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                                  reply_markup=self.generate_calendar(int(year), int(month)))

                elif call.data.startswith("prevsend_") or call.data.startswith("nextsend_"):
                    _, year, month = call.data.split("_")
                    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                                  reply_markup=self.generate_send_calendar(int(year), int(month)))
                elif call.data.startswith("daysend_"):

                    _, year, month, day = call.data.split("_")
                    # Теперь можно безопасно записать дату
                    self.user_data[self.unique_id]['Дата отправки опроса'] = f"{int(day):02d}-{int(month):02d}-{year}"

                    # Передаем дату в функцию (убрал .value(), так как строка не имеет такого метода)
                    self.select_time_send_survey()
                elif call.data.startswith("timesend_"):

                    _, time = call.data.split("_")

                    # Теперь можно безопасно записать дату
                    self.user_data[self.unique_id]['Время отправки опроса'] = f"{time}"

                    # Передаем дату в функцию (убрал .value(), так как строка не имеет такого метода)
                    self.save_survey()
                elif call.data.startswith("day_"):

                    _, year, month, day = call.data.split("_")

                    # Теперь можно безопасно записать дату
                    self.user_data[self.unique_id]['Дата тренировки/игры'] = f"{int(day):02d}-{int(month):02d}-{year}"

                    # Передаем дату в функцию (убрал .value(), так как строка не имеет такого метода)
                    self.generate_time_selection()
                elif call.data == 'select_send_command':
                    # Теперь можно безопасно записать дату
                    self.user_data[self.unique_id]['Получатели опроса'] = f"{','.join(self.selected_send_users)}"
                    # Передаем дату в функцию (убрал .value(), так как строка не имеет такого метода)
                    self.select_date_send_survey()
                elif call.data == "back_hours":
                    # Переход назад (цикл через 2 -> 2.5 -> 3)
                    if self.hour == 2:
                        self.hour = 3
                    elif self.hour == 3:
                        self.hour = 2.5
                    elif self.hour == 2.5:
                        self.hour = 2
                    self.generate_time_selection()
                elif call.data == "up_hour":
                    # Переход назад (цикл через 2 -> 2.5 -> 3)
                    if self.hour == 2:
                        self.hour = 2.5
                    elif self.hour == 2.5:
                        self.hour = 3
                    elif self.hour == 3:
                        self.hour = 2
                    self.generate_time_selection()
                elif call.data == "back_edit_hours":
                    # Переход назад (цикл через 2 -> 2.5 -> 3)
                    if self.hour == 2:
                        self.hour = 3
                    elif self.hour == 3:
                        self.hour = 2.5
                    elif self.hour == 2.5:
                        self.hour = 2
                    self.timeedit_survey()
                elif call.data == "up_edit_hour":
                    # Переход назад (цикл через 2 -> 2.5 -> 3)
                    if self.hour == 2:
                        self.hour = 2.5
                    elif self.hour == 2.5:
                        self.hour = 3
                    elif self.hour == 3:
                        self.hour = 2
                    self.timeedit_survey()
                elif call.data.startswith("time_"):
                    _, data, time = call.data.split("_")
                    self.user_data[self.unique_id]['Время тренировки/игры'] = f"{time}"
                    self.get_address()
                elif call.data.startswith("price_"):
                    _, price = call.data.split("_")
                    self.user_data[self.unique_id]['Цена'] = f"{price}"
                    self.select_send_survey()
                elif self.call.data.startswith("send_"):
                    user_key = '_'.join(self.call.data.split("_")[1:])  # Извлекаем имя пользователя
                    if user_key in self.selected_send_users:
                        self.selected_send_users.remove(user_key)  # Убираем из списка
                    else:
                        self.selected_send_users.add(user_key)  # Добавляем в список
                    self.select_send_survey()
                elif self.call.data == "nextdell" and self.current_index < len(self.surveys) - 1:
                    self.current_index += 1
                    self.del_survey()
                elif self.call.data == "prevdell" and self.current_index > 0:
                    self.current_index -= 1
                    self.del_survey()
                elif self.call.data == "mainnextedit" and self.current_index < len(self.surveys) - 1:
                    self.current_index += 1
                    self.edit_survey()
                elif self.call.data == "mainprevedit" and self.current_index > 0:
                    self.current_index -= 1
                    self.edit_survey()
                elif self.call.data == "mainnextres" and self.current_index < len(self.surveys) - 1:
                    self.current_index += 1
                    self.result_surveys()
                elif self.call.data == "mainprevres" and self.current_index > 0:
                    self.current_index -= 1
                    self.result_surveys()
                elif self.call.data.startswith("editsurvey_"):
                    self.save_edit()
                elif call.data.startswith("prevedit_") or call.data.startswith("nextedit_"):
                    _, year, month = call.data.split("_")
                    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                                  reply_markup=self.generate_edit_survey_calendar(int(year),
                                                                                                  int(month)))
                elif call.data.startswith("prevreminder_") or call.data.startswith("nextreminder_"):
                    _, year, month = call.data.split("_")
                    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                                  reply_markup=self.generate_reminder_calendar(int(year),
                                                                                               int(month)))
                elif call.data.startswith("preveditsend_") or call.data.startswith("nexteditsend_"):
                    _, year, month = call.data.split("_")
                    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                                  reply_markup=self.generate_editsend_survey_calendar(int(year),
                                                                                                      int(month)))
                elif call.data.startswith("editcommand_"):
                    user_key = '_'.join(self.call.data.split("_")[1:])  # Извлекаем имя пользователя
                    if user_key in self.selected_edit_users:
                        self.selected_edit_users.remove(user_key)  # Убираем из списка
                    else:
                        self.selected_edit_users.add(user_key)  # Добавляем в список
                    self.recieptsedit_survey()
                elif call.data == "recieptsedit_survey":
                    key_del = self.surveys[self.current_index][0]
                    users = self.load_data()["surveys"][key_del]["Получатели опроса"]
                    users_list = [user for user in users.split(",") if user]  # Убираем пустые строки
                    self.selected_edit_users.update(users_list)  # Добавляем в set
                    self.recieptsedit_survey()

    def create_buttons(self, buttons):
        return [InlineKeyboardButton(key, callback_data=value) for key, value in buttons.items()]

    def edit_message(self, text, buttons=None, add=None):
        self.markup = InlineKeyboardMarkup()  # Добавляем это
        if buttons:
            self.markup = InlineKeyboardMarkup([self.create_buttons(buttons)])
        if add:

            for key, value in add.items():
                if 'http' not in value:

                    self.markup.add(InlineKeyboardButton(key, callback_data=value))
                else:
                    self.markup.add(InlineKeyboardButton(key, url=value))
        bot.edit_message_text(
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id,
            text=text,
            reply_markup=self.markup,
            parse_mode="HTML"
        )

    def show_start_menu(self, message):
        buttons_name = ["Начать"]
        response_text = f"""Вы находитесь в разделе: <u>Главное меню</u>\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:""",
        if self.admin:
            buttons_name.append('Управление')
        try:
            buttons = {name: name for name in buttons_name}
            self.edit_message(response_text, buttons)
        except:
            users = [str(name.replace('@', '')).split('_')[0] for name in
                     self.load_data()["commands"]['RedHeads']["users"].values()]
            if self.load_data()["commands"]['RedHeads']['users']:
                if any(user in users for user in [message.chat.id, str(message.chat.username).replace('@', '')]):
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
        self.markup = InlineKeyboardMarkup()
        data = self.load_data()["commands"]
        for key in self.keys:
            data = data.get(key, {})
            # убираем список игроков
            data.pop('users', None)

        if isinstance(data, dict) and data:

            if self.keys:
                last_key = f"<u>{self.keys[-1]}</u>"
                section_path = " - ".join(self.keys[:-1] + [last_key])  # Все, кроме последнего, остаются обычными
                full_path = f"Команды - {section_path}"  # Добавляем "Главное меню" в начало
            else:
                full_path = "<u>Команды</u>"  # Если ключей нет, просто "Главное меню"
            # Сортируем ключи в алфавитном порядке
            sorted_keys = sorted(data.keys())

            response_text = f"""Вы находитесь в разделе: Главное меню - {full_path}\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"""
            add = {}
            for k in sorted_keys:  # Используем отсортированные ключи
                v = data[k]
                if isinstance(v, str) and v.startswith("http"):
                    add[k] = v
                else:
                    add[k] = k
            self.edit_message(response_text, add=add)
            # Формируем путь с подчёркиванием последнего ключа

    def control_buttons(self):
        buttons_name = ["Доступ к боту", "Опрос", "Напоминание", "Редактирование команд"]
        buttons = {name: name for name in buttons_name}
        response_text = """Вы находитесь в разделе: Главное меню - <u>Управление</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"""
        self.edit_message(response_text, buttons)

    def main_control(self):
        buttons_name = ["Открыть доступ", "Закрыть доступ"]
        buttons = {name: name for name in buttons_name}
        response_text = """Вы находитесь в разделе: Главное меню - Управление -  <u>Доступ к боту</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"""
        self.edit_message(response_text, buttons)

    def open_control(self):
        buttons_name = [key for key in self.load_data()["commands"].keys()] + ['Админы']
        buttons = {name: name for name in buttons_name}
        response_text = f"Вы находитесь в разделе: Главное меню - Управление - Доступ к боту - <u>Открыть доступ</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"
        self.edit_message(response_text, buttons)

    def close_control(self):
        buttons_name = [key for key in self.load_data()["commands"].keys()] + ['Админы']
        buttons = {name: name for name in buttons_name}
        response_text = f"Вы находитесь в разделе: Главное меню - Управление - Доступ к боту - <u>Закрыть доступ</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"
        self.edit_message(response_text, buttons)

    def edit_commands(self):
        buttons_name = [key for key in self.load_data()["commands"].keys()]
        buttons = {name: name for name in buttons_name}
        response_text = f"Вы находитесь в разделе: Главное меню - Управление - Доступ к боту - <u>Редактирование команд</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"
        self.edit_message(response_text, buttons)

    def close(self):
        users = (
            self.load_data()["commands"][self.select_command]["users"].items() if self.select_command != 'Админы' else
            self.load_data()['admins'].items())
        add = {}
        for keys, value in users:
            value = str(value).split("_")[0]
            is_selected = f"{keys}_{value}_{self.select_command}" in self.selected_users  # Проверяем, выбран ли пользователь
            icon = "✅" if is_selected else "❌"  # Меняем иконку
            button_text = f"{icon} {keys}({value})"
            add[button_text] = f"toggle_{keys}_{value}_{self.select_command}"
        add['💾 Закрыть доступ!'] = '💾 Закрыть доступ!'
        add["Отмена!"] = 'cancel_dell'
        response_text = f"Вы находитесь в разделе: Главное меню - Управление -  Доступ к боту - Закрыть доступ -  <u>{self.select_command}</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"
        self.edit_message(response_text, add=add)

    def dell_users(self):
        # Загружаем данные из файла
        data = self.load_data()
        if self.select_command == 'admins' and (
                len(self.load_data()['admins'].keys()) == 1 or len(self.load_data()['admins'].keys()) == len(
            self.selected_users)) and self.selected_users:
            text = 'пользователи НЕ УДАЛЕНЫ' if len(self.selected_users) > 1 else 'пользователь НЕ УДАЛЕН'
            response_text = f'Должен быть минимум 1 админ, {text}'
            bot.answer_callback_query(self.call.id, response_text,
                                      show_alert=True)
            self.selected_users.clear()
            self.selected_video.clear()
            self.selected_stat.clear()
            if str(list(self.state_stack.keys())[-1]) in ('💾 Закрыть доступ!', 'cancel_dell'):
                self.state_stack = dict(list(self.state_stack.items())[:-1])

            self.close_control()
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
            self.selected_users.clear()
            self.selected_video.clear()
            self.selected_stat.clear()
            if str(list(self.state_stack.keys())[-1]) in ('💾 Закрыть доступ!', 'cancel_dell'):
                self.state_stack = dict(list(self.state_stack.items())[:-1])
            self.close_control()
        else:
            if str(list(self.state_stack.keys())[-1]) in ('💾 Закрыть доступ!', 'cancel_dell'):
                self.state_stack = dict(list(self.state_stack.items())[:-1])
            self.close_control()

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
                        response_test = 'Длина имени или id должна быть минимум 4 символа'
                        bot.answer_callback_query(self.call.id, response_test,
                                                  show_alert=True)
                        self.selected_users = set()
                        self.selected_video_stat = set()
                        self.open_control()
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
                self.selected_users.clear()
                self.selected_video.clear()
                self.selected_stat.clear()
                self.open_control()
            else:
                try:
                    bot.delete_message(chat_id=message.chat.id,
                                       message_id=message.message_id)
                except:
                    pass

                response_test = 'Некорректное добавление, ознакомьтесь с примерами и попробуйте еще раз'
                bot.answer_callback_query(self.call.id, response_test,
                                          show_alert=True)
                self.selected_users.clear()
                self.selected_video.clear()
                self.selected_stat.clear()
                self.open_control()
        else:
            try:
                bot.delete_message(chat_id=message.chat.id,
                                   message_id=message.message_id)
            except:
                pass
            self.selected_users.clear()
            self.selected_video.clear()
            self.selected_stat.clear()
            self.open_control()

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

    def add_video(self):
        # Редактируем текущее сообщение, чтобы запросить имя сотрудника
        bot.edit_message_text(
            f"Вы находитесь в разделе: Главное меню - Управление -  Редактирование команд - {self.select_command} - Редактировать видео - <u>Добавить видео</u> .\n\nИспользуй "
            f"кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start "
            f"\n\nНапишите название  и ссылку на видео для добавления через двоеточие, пример:\nСезон 2024-2025:https://disk.yandex.ru/d/bWFMzczzg"
            f"\nТакже можно добавлять списком несколько ссылок через запятую, "
            f"пример:\nСезон 2024-2025:https://disk.yandex.ru/d/bWFMzczzg, Сезон 2025-2026:https://disk.yandex.ru/d/bW343Mzczzg",
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id
        )

        # Устанавливаем состояние ожидания ответа от пользователя
        bot.register_next_step_handler(self.call.message,
                                       self.add_video_list)

    def add_video_list(self, message):
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
                        if value not in data["commands"][self.select_command]['Видео'].values():
                            data["commands"][self.select_command]['Видео'][name] = value
                        else:
                            text = f'Ссылка {value} уже существует'
                            bot.answer_callback_query(self.call.id, text,
                                                      show_alert=True)
                            try:
                                bot.delete_message(chat_id=message.chat.id,
                                                   message_id=message.message_id)
                            except:
                                pass
                            self.state_stack = dict(list(self.state_stack.items())[:-1])
                            self.edit_video()
                            return
                    else:
                        try:
                            bot.delete_message(chat_id=message.chat.id,
                                               message_id=message.message_id)
                        except:
                            pass
                        response_test = 'Неправильны указаны значения. Ожидается длина названия и ссылки минимум 4 знака, и ссылка должна начинаться с http'
                        bot.answer_callback_query(self.call.id, response_test,
                                                  show_alert=True)
                        self.state_stack = dict(list(self.state_stack.items())[:-1])
                        self.edit_video()
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
                self.edit_video()
            else:
                try:
                    bot.delete_message(chat_id=message.chat.id,
                                       message_id=message.message_id)
                except:
                    pass
                response_test = 'Некорректное добавление, ознакомьтесь с примерами и попробуйте еще раз'
                bot.answer_callback_query(self.call.id, response_test,
                                          show_alert=True)
                self.state_stack = dict(list(self.state_stack.items())[:-1])
                self.edit_video()
        else:
            if message.message_id:
                try:
                    bot.delete_message(chat_id=message.chat.id,
                                       message_id=message.message_id)
                except:
                    pass
            self.state_stack = dict(list(self.state_stack.items())[:-1])
            self.edit_video()

    def dell_video(self):
        self.markup = InlineKeyboardMarkup()
        buttons = []
        for keys, value in self.load_data()["commands"][self.select_command]["Видео"].items():
            is_selected = f"{keys}_Видео_{self.select_command}" in self.selected_video  # Проверяем, выбран ли пользователь
            icon = "✅" if is_selected else "❌"  # Меняем иконку
            button_text = f"{icon} {keys}"
            item = types.InlineKeyboardButton(button_text,
                                              callback_data=f"toggle_{keys}_Видео_{self.select_command}")
            buttons.append(item)

        self.markup.add(*buttons)

        save = InlineKeyboardButton("💾 Сохранить!", callback_data='save_dell_video')
        cancel = InlineKeyboardButton("Отмена!", callback_data='cancel_dell_video')
        self.markup.add(cancel, save)
        new_text = f"Вы находитесь в разделе: Главное меню - Управление -  Редактирование команд - {self.select_command} - Редактировать видео - <u>Удалить видео</u> .\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"

        bot.edit_message_text(
            new_text,
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id,
            reply_markup=self.markup
        )

    def save_del_video(self):

        data = self.load_data()
        if self.selected_video:
            # Удаляем пользователей
            for user in self.selected_video:
                data_user = user.split("_")
                if data_user[0] in data["commands"][data_user[-1]]["Видео"]:
                    del data["commands"][data_user[-1]]["Видео"][data_user[0]]
            # Сохраняем обновленные данные обратно в файл
            self.write_data(data)  # Передаем измененные данные в функцию сохранения
            response_text = 'Ссылки удалены' if len(self.selected_video) > 1 else 'Ссылка удалена'
            bot.answer_callback_query(self.call.id, response_text,
                                      show_alert=True)
            self.selected_users.clear()
            self.selected_video.clear()
            self.selected_stat.clear()
            self.state_stack = dict(list(self.state_stack.items())[:-2])
            self.edit_video()
        else:
            self.selected_users.clear()
            self.selected_video.clear()
            self.selected_stat.clear()
            self.state_stack = dict(list(self.state_stack.items())[:-2])
            self.edit_video()

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

    def add_static(self):
        # Редактируем текущее сообщение, чтобы запросить имя сотрудника
        bot.edit_message_text(
            f"Вы находитесь в разделе: Главное меню - Управление -  Редактирование команд - {self.select_command} - Редактировать статистику - <u>Добавить статистику</u> .\n\nИспользуй "
            f"кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start "
            f"\n\nНапишите название  и ссылку на видео для добавления через двоеточие, пример:\nСезон 2024-2025:https://disk.yandex.ru/d/bWFMzczzg"
            f"\nТакже можно добавлять списком несколько ссылок через запятую, "
            f"пример:\nСезон 2024-2025:https://disk.yandex.ru/d/bWFMzczzg, Сезон 2025-2026:https://disk.yandex.ru/d/bW343Mzczzg",
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id
        )
        # Устанавливаем состояние ожидания ответа от пользователя
        bot.register_next_step_handler(self.call.message,
                                       self.add_static_list)

    def add_static_list(self, message):
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
                        if value not in data["commands"][self.select_command]['Статистика'].values():
                            data["commands"][self.select_command]['Статистика'][name] = value
                        else:
                            text = f'Ссылка {value} уже существует'
                            bot.answer_callback_query(self.call.id, text,
                                                      show_alert=True)
                            try:
                                bot.delete_message(chat_id=message.chat.id,
                                                   message_id=message.message_id)
                            except:
                                pass
                            self.state_stack = dict(list(self.state_stack.items())[:-1])
                            self.edit_statistic()
                            return
                    else:
                        try:
                            bot.delete_message(chat_id=message.chat.id,
                                               message_id=message.message_id)
                        except:
                            pass
                        response_test = 'Неправильны указаны значения. Ожидается длина названия и ссылки минимум 4 знака, и ссылка должна начинаться с http'
                        bot.answer_callback_query(self.call.id, response_test,
                                                  show_alert=True)
                        self.state_stack = dict(list(self.state_stack.items())[:-1])
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
                self.state_stack = dict(list(self.state_stack.items())[:-1])
                self.edit_statistic()
        else:
            if message.message_id:
                try:
                    bot.delete_message(chat_id=message.chat.id,
                                       message_id=message.message_id)
                except:
                    pass
            self.state_stack = dict(list(self.state_stack.items())[:-1])
            self.edit_statistic()

    def dell_stitistic(self):
        self.markup = InlineKeyboardMarkup()
        buttons = []
        for keys, value in self.load_data()["commands"][self.select_command]["Статистика"].items():
            is_selected = f"{keys}_Статистика_{self.select_command}" in self.selected_stat  # Проверяем, выбран ли пользователь
            icon = "✅" if is_selected else "❌"  # Меняем иконку
            button_text = f"{icon} {keys}"
            item = types.InlineKeyboardButton(button_text,
                                              callback_data=f"toggle_{keys}_Статистика_{self.select_command}")
            buttons.append(item)

        self.markup.add(*buttons)

        save = InlineKeyboardButton("💾 Сохранить!", callback_data='save_dell_stat')
        cancel = InlineKeyboardButton("Отмена!", callback_data='cancel_dell_stat')
        self.markup.add(cancel, save)
        new_text = f"Вы находитесь в разделе: Главное меню - Управление -  Редактирование команд - {self.select_command} - Редактировать статистику - <u>Удалить статистику</u> .\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"

        bot.edit_message_text(
            new_text,
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id,
            reply_markup=self.markup
        )

    def save_del_statistic(self):
        data = self.load_data()
        if self.selected_stat:
            # Удаляем пользователей
            for user in self.selected_stat:
                data_user = user.split("_")
                if data_user[0] in data["commands"][data_user[-1]]["Статистика"]:
                    del data["commands"][data_user[-1]]["Статистика"][data_user[0]]
            # Сохраняем обновленные данные обратно в файл
            self.write_data(data)  # Передаем измененные данные в функцию сохранения
            response_text = 'Ссылки удалены' if len(self.selected_stat) > 1 else 'Ссылка удалена'
            bot.answer_callback_query(self.call.id, response_text,
                                      show_alert=True)
            self.selected_users.clear()
            self.selected_video.clear()
            self.selected_stat.clear()
            self.state_stack = dict(list(self.state_stack.items())[:-2])
            self.edit_statistic()
        else:
            self.selected_users.clear()
            self.selected_video.clear()
            self.selected_stat.clear()
            self.state_stack = dict(list(self.state_stack.items())[:-2])
            self.edit_statistic()

    def the_survey(self):
        buttons = [InlineKeyboardButton(key, callback_data=key) for key in
                   ["Новый опрос", "Удалить опрос", "Редактировать опрос", "Результаты опросов"]]
        self.markup = InlineKeyboardMarkup([buttons])
        new_text = f"Вы находитесь в разделе: Главное меню - Управление - <u>Опрос</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"
        bot.edit_message_text(
            new_text,
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id,
            reply_markup=self.markup
        )

    def type_play(self):
        buttons = [InlineKeyboardButton(key, callback_data=key) for key in
                   ["Игра", "Тренировка", "Товарищеская игра"]]
        self.markup = InlineKeyboardMarkup([buttons])
        new_text = f"Вы находитесь в разделе: Главное меню - Управление - Опрос - <u>Новый опрос</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"
        bot.edit_message_text(
            new_text,
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id,
            reply_markup=self.markup
        )

    def generate_calendar(self, year, month):
        markup = InlineKeyboardMarkup()
        cal = calendar.monthcalendar(year, month)
        markup.row(InlineKeyboardButton(f"{tmonth_names[month]} {year}", callback_data="ignore"))

        week_days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        markup.row(*[InlineKeyboardButton(day, callback_data="ignore") for day in week_days])

        for week in cal:
            row = []
            for day in week:
                row.append(InlineKeyboardButton(" " if day == 0 else str(day),
                                                callback_data=f"day_{year}_{month}_{day}" if day != 0 else "ignore"))
            markup.row(*row)

        prev_month, prev_year = (month - 1, year) if month > 1 else (12, year - 1)
        next_month, next_year = (month + 1, year) if month < 12 else (1, year + 1)

        markup.row(
            InlineKeyboardButton("<", callback_data=f"prev_{prev_year}_{prev_month}"),
            InlineKeyboardButton(">", callback_data=f"next_{next_year}_{next_month}")
        )
        return markup

    def new_survey(self):
        now = datetime.now()
        text_responce = "\n".join(f"{k}: {v}" for game_data in self.user_data.values() for k, v in game_data.items())
        self.markup = self.generate_calendar(now.year, now.month)
        new_text = f"Вы находитесь в разделе: Главное меню - Управление - Новый опрос - {self.user_data[self.unique_id]['Тип']} - <u>Дата</u>.\n\n{text_responce}.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите дату игры/тренировки:"
        bot.edit_message_text(
            new_text,
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id,
            reply_markup=self.markup
        )

    def generate_time_selection(self):
        self.markup = InlineKeyboardMarkup()
        text_responce = "\n".join(f"{k}: {v}" for game_data in self.user_data.values() for k, v in game_data.items())
        times = [f"{hour:02d}:{minute:02d} - {hour + 2:02d}:{minute:02d}"
                 for hour in range(9, 21)
                 for minute in [0, 30]]

        if self.hour == 2.5:
            times = [f"{hour:02d}:{minute:02d} - {(hour + 2 + (minute + 30) // 60) % 24:02d}:{(minute + 30) % 60:02d}"
                     for hour in range(9, 22) for minute in [0, 30]]
        elif self.hour == 3:
            times = [f"{hour:02d}:{minute:02d} - {hour + 3:02d}:{minute:02d}"
                     for hour in range(9, 21)
                     for minute in [0, 30]]
        text = f"{self.hour}ч" if self.hour != 2.5 else '2ч30м'
        new_text = f"Вы находитесь в разделе: Главное меню - Управление - Новый опрос - {self.user_data[self.unique_id]['Тип']} - Дата -  <u>Время</u>\n\n{text_responce}.\n\nИспользуйте кнопки для навигации. Чтобы вернуться на шаг назад, используйте команду /back. В начало /start \n\nВыберите время (интервал - {text}) игры/тренировки:"
        for i in range(0, len(times), 4):
            self.markup.row(
                *[InlineKeyboardButton(time,
                                       callback_data=f"time_{self.user_data[self.unique_id]['Дата тренировки/игры']}_{time}")
                  for
                  time in
                  times[i:i + 4]])
        self.markup.row(
            InlineKeyboardButton("<", callback_data=f"back_hours"),
            InlineKeyboardButton(">", callback_data=f"up_hour")
        )
        bot.edit_message_text(
            new_text,
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id,
            reply_markup=self.markup
        )

    def get_address(self):
        text_responce = "\n".join(f"{k}: {v}" for game_data in self.user_data.values() for k, v in game_data.items())
        new_text = f"Вы находитесь в разделе: Главное меню - Управление - Новый опрос - {self.user_data[self.unique_id]['Тип']} - Дата - Время - <u>Адрес</u>\n\n{text_responce}.\n\nИспользуйте кнопки для навигации. Чтобы вернуться на шаг назад, используйте команду /back. В начало /start \n\nНапишите адрес:"
        bot.edit_message_text(
            new_text,
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id
        )
        bot.register_next_step_handler(self.call.message, self.get_adress_text)

    def get_adress_text(self, message):
        self.user_data[self.unique_id]['Адрес'] = message.text
        try:
            bot.delete_message(chat_id=message.chat.id,
                               message_id=message.message_id)
        except:
            pass
        self.get_price()

    def get_price(self):
        text_responce = "\n".join(f"{k}: {v}" for game_data in self.user_data.values() for k, v in game_data.items())
        self.markup = InlineKeyboardMarkup([])
        prices = [x for x in range(300, 1501, 50)]
        new_text = (
            f"Вы находитесь в разделе: Главное меню - Управление - Новый опрос - {self.user_data[self.unique_id]['Тип']} - Дата - Время - Адрес - <u>Цена</u>\n\n{text_responce}.\n\nИспользуйте кнопки для навигации. Чтобы вернуться на шаг назад, используйте команду /back. В начало /start\n\nВыберите цену игры/тренировки:")
        keyboard = []
        for i in range(0, len(prices), 4):
            keyboard.append([
                InlineKeyboardButton(str(price), callback_data=f"price_{price}") for price in prices[i:i + 4]
            ])

        self.markup = InlineKeyboardMarkup(keyboard)

        bot.edit_message_text(
            new_text,
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id,
            reply_markup=self.markup
        )

    def select_send_survey(self):
        text_responce = "\n".join(f"{k}: {v}" for game_data in self.user_data.values() for k, v in game_data.items())
        self.markup = InlineKeyboardMarkup()
        buttons = []
        users = list(self.load_data()["commands"].keys()) + ['Админы']
        for value in users:
            is_selected = f"{value}" in self.selected_send_users  # Проверяем, выбран ли пользователь
            icon = "✅" if is_selected else "❌"  # Меняем иконку

            button_text = f"{icon} {value}"
            item = types.InlineKeyboardButton(button_text,
                                              callback_data=f"send_{value}")
            buttons.append(item)
        new_text = (
            f"Вы находитесь в разделе: Главное меню - Управление - Новый опрос - {self.user_data[self.unique_id]['Тип']} - Дата - Время - Адрес - Цена - <u>Выбор команды для опроса</u>\n\n{text_responce}.\n\nИспользуйте кнопки для навигации. Чтобы вернуться на шаг назад, используйте команду /back. В начало /start\n\nВыберите команду для опроса:")
        self.markup.add(*buttons)
        self.markup.add(InlineKeyboardButton("Дальше", callback_data="select_send_command"))
        bot.edit_message_text(
            new_text,
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id,
            reply_markup=self.markup
        )

    def generate_send_calendar(self, year, month):
        markup = InlineKeyboardMarkup()
        cal = calendar.monthcalendar(year, month)
        markup.row(InlineKeyboardButton(f"{tmonth_names[month]} {year}", callback_data="ignore"))

        week_days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        markup.row(*[InlineKeyboardButton(day, callback_data="ignore") for day in week_days])

        for week in cal:
            row = []
            for day in week:
                row.append(InlineKeyboardButton(" " if day == 0 else str(day),
                                                callback_data=f"daysend_{year}_{month}_{day}" if day != 0 else "ignore"))
            markup.row(*row)

        prev_month, prev_year = (month - 1, year) if month > 1 else (12, year - 1)
        next_month, next_year = (month + 1, year) if month < 12 else (1, year + 1)

        markup.row(
            InlineKeyboardButton("<", callback_data=f"prevsend_{prev_year}_{prev_month}"),
            InlineKeyboardButton(">", callback_data=f"nextsend_{next_year}_{next_month}")
        )
        return markup

    def select_date_send_survey(self):
        now = datetime.now()
        text_responce = "\n".join(f"{k}: {v}" for game_data in self.user_data.values() for k, v in game_data.items())
        self.markup = self.generate_send_calendar(now.year, now.month)
        new_text = (
            f"Вы находитесь в разделе: Главное меню - Управление - Новый опрос - {self.user_data[self.unique_id]['Тип']} - Дата - Время - Адрес - Цена - Выбор команды для опроса - <u>Дата отправки опроса</u>\n\n{text_responce}.\n\nИспользуйте кнопки для навигации. Чтобы вернуться на шаг назад, используйте команду /back. В начало /start\n\nВыберите дату отправки опроса:")

        bot.edit_message_text(
            new_text,
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id,
            reply_markup=self.markup
        )

    def select_time_send_survey(self):
        text_responce = "\n".join(f"{k}: {v}" for game_data in self.user_data.values() for k, v in game_data.items())
        time = [f"{hour:02}:{minute:02}" for hour in range(9, 24) for minute in [0, 30]]
        buttons = [InlineKeyboardButton(key, callback_data=f"timesend_{key}") for key in time]
        # Разбиваем список кнопок на подсписки по 5 элементов
        buttons_layout = [buttons[i:i + 5] for i in range(0, len(buttons), 5)]
        self.markup = InlineKeyboardMarkup(buttons_layout)
        new_text = (
            f"Вы находитесь в разделе: Главное меню - Управление - Новый опрос - {self.user_data[self.unique_id]['Тип']} - Дата - Время - Адрес - Цена - Выбор команды для опроса - Дата отправки опроса - <u>Время отправки опроса</u>\n\n{text_responce}.\n\nИспользуйте кнопки для навигации. Чтобы вернуться на шаг назад, используйте команду /back. В начало /start\n\nВыберите время отправки опроса:")
        bot.edit_message_text(
            new_text,
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id,
            reply_markup=self.markup
        )

    def save_survey(self):
        text_responce = "\n".join(f"{k}: {v}" for game_data in self.user_data.values() for k, v in game_data.items())
        self.markup = InlineKeyboardMarkup()
        self.markup.add(InlineKeyboardButton("Отмена", callback_data="cancel_send_survey"))
        self.markup.add(InlineKeyboardButton("Запланировать опрос", callback_data="save_send_survey"))
        new_text = (
            f"Вы находитесь в разделе: Главное меню - Управление - Новый опрос - {self.user_data[self.unique_id]['Тип']} - Дата - Время - Адрес - Цена - Выбор команды для опроса - Дата отправки опроса - Время отправки опроса - <u>Сохранение опроса</u>\n\n{text_responce}.\n\nИспользуйте кнопки для навигации. Чтобы вернуться на шаг назад, используйте команду /back. В начало /start\n\nПроверьте подготовленный опрос и выберете раздел")

        bot.edit_message_text(
            new_text,
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id,
            reply_markup=self.markup
        )

    def save(self):
        data = self.load_data()
        self.user_data[self.unique_id]['Опрос открыт'] = "Нет"
        self.user_data[self.unique_id]['Опрос отправлен'] = "Нет"
        self.user_data[self.unique_id]['Отметились'] = {}
        self.user_data[self.unique_id]['Количество отметившихся'] = 0
        self.user_data[self.unique_id]['id опроса'] = 0

        # Проверяем, есть ли "surveys" в config, если нет - создаем пустой словарь
        if "surveys" not in data:
            data["surveys"] = {}

        # Добавляем данные правильно (без .values())
        data["surveys"][self.unique_id] = self.user_data[self.unique_id]  # <-- Убрал .values()

        # Сохраняем обновленные данные обратно в файл
        self.write_data(data)

        response_text = 'Задание запланировано'
        bot.answer_callback_query(self.call.id, response_text, show_alert=True)

        # Очищаем временные данные
        self.user_data.clear()
        self.selected_send_users.clear()
        self.the_survey()

    def del_survey(self):
        self.data = self.load_data()
        """Отображает текущий опрос с кнопками навигации"""
        self.surveys = list(self.data["surveys"].items())
        if not self.surveys:
            response_text = 'Нет доступных опросов.'
            bot.answer_callback_query(self.call.id, response_text,
                                      show_alert=True)
            return

        survey_id, survey_data = self.surveys[self.current_index]
        text_responce = (
            f"Вы находитесь в разделе: Главное меню - Управление - <u>Удалить опрос</u>.\n\n")

        text_responce += f"<b>Опрос {self.current_index + 1} из {len(self.surveys)}</b>\n\n"
        text_responce += "\n".join(f"{k}: {v}" for k, v in survey_data.items())
        text_responce += '\n\nИспользуйте кнопки для навигации. Чтобы вернуться на шаг назад, используйте команду /back. В начало /start\n\nВыбирете опрос для удаления:'
        buttons = [
            InlineKeyboardButton("<", callback_data="prevdell") if self.current_index > 0 else None,
            InlineKeyboardButton(">", callback_data="nextdell") if self.current_index < len(self.surveys) - 1 else None
        ]

        buttons = [btn for btn in buttons if btn]  # Убираем None

        markup = InlineKeyboardMarkup([buttons, [InlineKeyboardButton("Отмена", callback_data="cansel_survey"),
                                                 InlineKeyboardButton("Удалить опрос", callback_data="dell_survey")]])

        bot.edit_message_text(
            text_responce,
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id,
            reply_markup=markup,
            parse_mode="HTML"
        )

    def save_dell_survey(self):
        data = self.load_data()
        key_del = self.surveys[self.current_index][0]
        del data["surveys"][key_del]
        # Сохраняем обновленные данные обратно в файл
        self.write_data(data)  # Передаем измененные данные в функцию сохранения
        response_text = 'Опрос удален'
        bot.answer_callback_query(self.call.id, response_text,
                                  show_alert=True)
        self.selected_users.clear()
        self.selected_video.clear()
        self.selected_stat.clear()
        self.current_index = 0
        self.the_survey()

    def edit_survey(self):
        self.data = self.load_data()
        """Отображает текущий опрос с кнопками навигации"""
        self.surveys = list(self.data["surveys"].items())
        if not self.surveys:
            response_text = 'Нет доступных опросов.'
            bot.answer_callback_query(self.call.id, response_text, show_alert=True)
            return

        survey_id, survey_data = self.surveys[self.current_index]
        text_responce = (
            f"Вы находитесь в разделе: Главное меню - Управление - <u>Редактировать опрос</u>.\n\n"
        )

        text_responce += f"<b>Опрос {self.current_index + 1} из {len(self.surveys)}</b>\n\n"
        text_responce += "\n".join(f"{k}: {v}" for k, v in survey_data.items() if k not in (
            'Отметились', 'Количество отметившихся', 'id опроса', 'Опрос отправлен', 'Опрос открыт'))
        text_responce += ('\n\nИспользуйте кнопки для навигации. Чтобы вернуться на шаг назад, '
                          'используйте команду /back. В начало /start\n\nВыберите опрос для удаления:')

        navigation_buttons = [
            InlineKeyboardButton("<", callback_data="mainprevedit") if self.current_index > 0 else None,
            InlineKeyboardButton(">", callback_data="mainnextedit") if self.current_index < len(
                self.surveys) - 1 else None
        ]
        navigation_buttons = [btn for btn in navigation_buttons if btn]  # Убираем None

        edit_buttons = [
            InlineKeyboardButton("Изменить тип", callback_data="typeedit_survey"),
            InlineKeyboardButton("Изменить дату тренировки/игры", callback_data="dateedit_survey"),
            InlineKeyboardButton("Изменить время тренировки/игры", callback_data="timeedit_survey"),
            InlineKeyboardButton("Изменить адрес", callback_data="addressedit_survey"),
            InlineKeyboardButton("Изменить цену", callback_data="priceedit_survey"),
            InlineKeyboardButton("Изменить получателей", callback_data="recieptsedit_survey"),
            InlineKeyboardButton("Изменить дату отправки опроса", callback_data="datesend_survey"),
            InlineKeyboardButton("Изменить время отправки опроса", callback_data="timesend_survey")
        ]

        # Разбиваем edit_buttons на строки по 3 кнопки
        edit_buttons_layout = [edit_buttons[i:i + 3] for i in range(0, len(edit_buttons), 3)]

        self.markup = InlineKeyboardMarkup([navigation_buttons] + edit_buttons_layout)

        bot.edit_message_text(
            text_responce,
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id,
            reply_markup=self.markup,
            parse_mode="HTML"
        )

    def typeedit_survey(self):

        buttons = [InlineKeyboardButton(key, callback_data=f"editsurvey_Тип_{key}") for key in
                   ["Игра", "Тренировка", "Товарищеская игра"]]
        self.markup = InlineKeyboardMarkup([buttons])
        new_text = f"Вы находитесь в разделе: Главное меню - Управление - Редактировать опрос - <u>Изменить тип</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"
        bot.edit_message_text(
            new_text,
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id,
            reply_markup=self.markup
        )

    def generate_edit_survey_calendar(self, year, month):
        markup = InlineKeyboardMarkup()
        cal = calendar.monthcalendar(year, month)
        markup.row(InlineKeyboardButton(f"{tmonth_names[month]} {year}", callback_data="ignore"))

        week_days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        markup.row(*[InlineKeyboardButton(day, callback_data="ignore") for day in week_days])

        for week in cal:
            row = []
            for day in week:
                row.append(InlineKeyboardButton(" " if day == 0 else str(day),
                                                callback_data=f"editsurvey_Дата тренировки/игры_{int(day):02d}-{int(month):02d}-{year}" if day != 0 else "ignore"))
            markup.row(*row)
        prev_month, prev_year = (month - 1, year) if month > 1 else (12, year - 1)
        next_month, next_year = (month + 1, year) if month < 12 else (1, year + 1)

        markup.row(
            InlineKeyboardButton("<", callback_data=f"prevedit_{prev_year}_{prev_month}"),
            InlineKeyboardButton(">", callback_data=f"nextedit_{next_year}_{next_month}")
        )
        return markup

    def dateedit_survey(self):
        now = datetime.now()
        self.markup = self.generate_edit_survey_calendar(now.year, now.month)
        new_text = f"Вы находитесь в разделе: Главное меню - Управление - Редактировать опрос - <u>Изменить дату тренировки/игры</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите дату:"
        bot.edit_message_text(
            new_text,
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id,
            reply_markup=self.markup
        )

    def timeedit_survey(self):

        self.markup = InlineKeyboardMarkup()
        times = [f"{hour:02d}:{minute:02d} - {hour + 2:02d}:{minute:02d}"
                 for hour in range(9, 21)
                 for minute in [0, 30]]

        if self.hour == 2.5:
            times = [f"{hour:02d}:{minute:02d} - {(hour + 2 + (minute + 30) // 60) % 24:02d}:{(minute + 30) % 60:02d}"
                     for hour in range(9, 22) for minute in [0, 30]]
        elif self.hour == 3:
            times = [f"{hour:02d}:{minute:02d} - {hour + 3:02d}:{minute:02d}"
                     for hour in range(9, 21)
                     for minute in [0, 30]]
        text = f"{self.hour}ч" if self.hour != 2.5 else '2ч30м'
        new_text = (
            f"Вы находитесь в разделе: Главное меню - Управление - Редактировать опрос - <u>Изменить время тренировки/игры</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите время (интервал - {text}) игры/тренировки:"
        )
        for i in range(0, len(times), 4):
            self.markup.row(
                *[InlineKeyboardButton(time,
                                       callback_data=f"editsurvey_Время тренировки/игры_{time}")
                  for
                  time in
                  times[i:i + 4]])
        self.markup.row(
            InlineKeyboardButton("<", callback_data=f"back_edit_hours"),
            InlineKeyboardButton(">", callback_data=f"up_edit_hour")
        )
        bot.edit_message_text(
            new_text,
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id,
            reply_markup=self.markup
        )

    def addressedit_survey(self):
        new_text = (
            f"Вы находитесь в разделе: Главное меню - Управление - Редактировать опрос - <u>Изменить адрес</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nНапишите адрес:"
        )
        bot.edit_message_text(
            new_text,
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id
        )
        bot.register_next_step_handler(self.call.message, self.get_adress_edit_text)

    def get_adress_edit_text(self, message):
        self.call.data = f"editsurvey_Адрес_{message.text}"
        try:
            bot.delete_message(chat_id=message.chat.id,
                               message_id=message.message_id)
        except:
            pass
        self.save_edit()

    def priceedit_survey(self):
        self.markup = InlineKeyboardMarkup([])
        prices = [x for x in range(300, 1501, 50)]
        new_text = (
            f"Вы находитесь в разделе: Главное меню - Управление - Редактировать опрос - <u>Изменить цену</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберете цену тренировки/игры:"
        )
        keyboard = []
        for i in range(0, len(prices), 4):
            keyboard.append([
                InlineKeyboardButton(str(price), callback_data=f"editsurvey_Цена_{price}") for price in prices[i:i + 4]
            ])

        self.markup = InlineKeyboardMarkup(keyboard)

        bot.edit_message_text(
            new_text,
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id,
            reply_markup=self.markup
        )

    def recieptsedit_survey(self):
        self.markup = InlineKeyboardMarkup()
        buttons = []
        users = list(self.load_data()["commands"].keys()) + ['Админы']
        for value in users:
            is_selected = f"{value}" in self.selected_edit_users  # Проверяем, выбран ли пользователь
            icon = "✅" if is_selected else "❌"  # Меняем иконку
            button_text = f"{icon} {value}"
            item = types.InlineKeyboardButton(button_text,
                                              callback_data=f"editcommand_{value}")
            buttons.append(item)
        new_text = (
            f"Вы находитесь в разделе: Главное меню - Управление - Редактировать опрос - <u>Изменить получателей</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберете команды:"
        )
        self.markup.add(*buttons)

        self.markup.add(InlineKeyboardButton("Сохранить",
                                             callback_data=f"editsurvey_Получатели опроса"))
        bot.edit_message_text(
            new_text,
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id,
            reply_markup=self.markup
        )

    def generate_editsend_survey_calendar(self, year, month):
        markup = InlineKeyboardMarkup()
        cal = calendar.monthcalendar(year, month)
        markup.row(InlineKeyboardButton(f"{tmonth_names[month]} {year}", callback_data="ignore"))

        week_days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        markup.row(*[InlineKeyboardButton(day, callback_data="ignore") for day in week_days])

        for week in cal:
            row = []
            for day in week:
                row.append(InlineKeyboardButton(" " if day == 0 else str(day),
                                                callback_data=f"editsurvey_Дата отправки опроса_{int(day):02d}-{int(month):02d}-{year}" if day != 0 else "ignore"))
            markup.row(*row)
        prev_month, prev_year = (month - 1, year) if month > 1 else (12, year - 1)
        next_month, next_year = (month + 1, year) if month < 12 else (1, year + 1)

        markup.row(
            InlineKeyboardButton("<", callback_data=f"preveditsend_{prev_year}_{prev_month}"),
            InlineKeyboardButton(">", callback_data=f"nexteditsend_{next_year}_{next_month}")
        )
        return markup

    def datesend_survey(self):
        now = datetime.now()
        self.markup = self.generate_editsend_survey_calendar(now.year, now.month)
        new_text = f"Вы находитесь в разделе: Главное меню - Управление - Редактировать опрос - <u>Изменить дату отправки опроса</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите дату:"
        bot.edit_message_text(
            new_text,
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id,
            reply_markup=self.markup
        )

    def timesend_survey(self):
        time = [f"{hour:02}:{minute:02}" for hour in range(9, 24) for minute in [0, 30]]
        buttons = [InlineKeyboardButton(key, callback_data=f"editsurvey_Время отправки опроса_{key}") for key in time]

        # Разбиваем список кнопок на подсписки по 5 элементов
        buttons_layout = [buttons[i:i + 5] for i in range(0, len(buttons), 5)]

        self.markup = InlineKeyboardMarkup(buttons_layout)

        new_text = (
            "Вы находитесь в разделе: Главное меню - Управление - Редактировать опрос - <u>Изменить время</u>.\n\n"
            "Используй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\n"
            "Выберите время:"
        )

        bot.edit_message_text(
            new_text,
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id,
            reply_markup=self.markup
        )

    def save_edit(self):
        data = self.load_data()
        key_del = self.surveys[self.current_index][0]
        new_value = self.call.data.split("_")

        if new_value[1] != 'Получатели опроса':
            data["surveys"][key_del][new_value[1]] = new_value[-1]
        else:
            data["surveys"][key_del][new_value[1]] = ','.join(self.selected_edit_users)
        self.write_data(data)  # Передаем измененные данные в функцию сохранения
        response_text = (
            f'{new_value[1]} изменен' if new_value[1] in ("Тип", "Адрес") else
            f'{new_value[1]} изменена' if new_value[1] in ("Дата тренировки/игры", "Цена") else
            f'{new_value[1]} изменены' if new_value[1] == "Получатели опроса" else
            f'{new_value[1]} изменено'
        )

        bot.answer_callback_query(self.call.id, response_text,
                                  show_alert=True)
        self.edit_survey()

    def format_dict(self, d, indent=0, base_indent=4):
        result = ""
        for key, value in d.items():
            current_indent = indent + base_indent  # Смещаем все уровни на base_indent
            if isinstance(value, dict):
                result += " " * current_indent + f"{key}:\n" + self.format_dict(value, current_indent, base_indent)
            else:
                result += " " * current_indent + f"{key}: {value}\n"
        return result

    def result_surveys(self):
        self.data = self.load_data()
        """Отображает текущий опрос с кнопками навигации"""
        self.surveys = list(self.data["surveys"].items())
        if not self.surveys:
            response_text = 'Нет доступных опросов.'
            bot.answer_callback_query(self.call.id, response_text, show_alert=True)
            return

        survey_id, survey_data = self.surveys[self.current_index]
        text_responce = (
            f"Вы находитесь в разделе: Главное меню - Управление - <u>Результаты опросов</u>.\n\n"
        )

        text_responce += f"<b>Опрос {self.current_index + 1} из {len(self.surveys)}</b>\n\n"
        text_responce += "\n".join(f"{k}: {v}" for k, v in survey_data.items() if k not in ('id опроса', 'Отметились'))
        # Генерация текста
        text_responce += "\nОтметились:\n" + self.format_dict(survey_data["Отметились"], base_indent=4)
        text_responce += ('\n\nИспользуйте кнопки для навигации. Чтобы вернуться на шаг назад, '
                          'используйте команду /back. В начало /start\n\nВыберите опрос для удаления:')

        navigation_buttons = [
            InlineKeyboardButton("<", callback_data="mainprevres") if self.current_index > 0 else None,
            InlineKeyboardButton(">", callback_data="mainnextres") if self.current_index < len(
                self.surveys) - 1 else None
        ]
        navigation_buttons = [btn for btn in navigation_buttons if btn]  # Убираем None

        self.markup = InlineKeyboardMarkup([navigation_buttons])

        bot.edit_message_text(
            text_responce,
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id,
            reply_markup=self.markup,
            parse_mode="HTML"
        )

    def reminder(self):
        buttons = [InlineKeyboardButton(key, callback_data=key) for key in
                   ["Создать напоминание", "Редактировать напоминание", "Результаты напоминаний"]]
        self.markup = InlineKeyboardMarkup([buttons])
        self.markup.add(InlineKeyboardButton("Удалить напоминание", callback_data="Удалить напоминание"))
        new_text = f"Вы находитесь в разделе: Главное меню - Управление - <u>Напоминание</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"
        bot.edit_message_text(
            new_text,
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id,
            reply_markup=self.markup
        )

    def generate_reminder_calendar(self, year, month):

        markup = InlineKeyboardMarkup()
        cal = calendar.monthcalendar(year, month)

        markup.row(InlineKeyboardButton(f"{tmonth_names[month]} {year}", callback_data="ignore"))

        week_days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        markup.row(*[InlineKeyboardButton(day, callback_data="ignore") for day in week_days])

        for week in cal:
            row = []
            for day in week:
                row.append(InlineKeyboardButton(" " if day == 0 else str(day),
                                                callback_data=f"reminder_Дата отправки напоминания_{int(day):02d}-{int(month):02d}-{year}" if day != 0 else "ignore"))
            markup.row(*row)
        prev_month, prev_year = (month - 1, year) if month > 1 else (12, year - 1)
        next_month, next_year = (month + 1, year) if month < 12 else (1, year + 1)

        markup.row(
            InlineKeyboardButton("<", callback_data=f"prevreminder_{prev_year}_{prev_month}"),
            InlineKeyboardButton(">", callback_data=f"nextreminder_{next_year}_{next_month}")
        )
        return markup

    def datesend_reminder(self):
        now = datetime.now()
        self.markup = self.generate_reminder_calendar(now.year, now.month)

        new_text = f"Вы находитесь в разделе: Главное меню - Управление - Напоминание - Создать напоминание - <u>Дата</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите дату:"
        bot.edit_message_text(
            new_text,
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id,
            reply_markup=self.markup
        )

    def timesend_reminder(self):
        time = [f"{hour:02}:{minute:02}" for hour in range(9, 24) for minute in [0, 30]]
        buttons = [InlineKeyboardButton(key, callback_data=f"reminder_Время отправки напоминания_{key}") for key in
                   time]
        # Разбиваем список кнопок на подсписки по 5 элементов
        buttons_layout = [buttons[i:i + 5] for i in range(0, len(buttons), 5)]
        self.markup = InlineKeyboardMarkup(buttons_layout)
        new_text = (
            "Вы находитесь в разделе: Главное меню - Управление - Напоминание - Создать напоминание - Дата - <u>Время</u>.\n\n"
            "Используй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\n"
            "Выберите время:"
        )
        bot.edit_message_text(
            new_text,
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id,
            reply_markup=self.markup
        )

    def description_reminder(self):
        new_text = (
            f"Вы находитесь в разделе: Главное меню - Управление - Напоминание - Создать напоминание - Дата - Время - <u>Текст напоминания</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nНапишите текст напоминания:"
        )
        bot.edit_message_text(
            new_text,
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id
        )
        bot.register_next_step_handler(self.call.message, self.get_description_reminder)

    def get_description_reminder(self, message):
        self.call.data = f"remindersdscr_Описание_{message.text}"
        try:
            bot.delete_message(chat_id=message.chat.id,
                               message_id=message.message_id)
        except:
            pass

    def select_user_send_reminder(self):
        buttons = [InlineKeyboardButton(key, callback_data=key) for key in
                   ["Отправка командам", "Отправка пользователям"]]
        self.markup = InlineKeyboardMarkup([buttons])
        self.markup.add(InlineKeyboardButton("Удалить напоминание", callback_data="Удалить напоминание"))
        new_text = f"Вы находитесь в разделе: Главное меню - Управление - Напоминание - Создать напоминание - Дата - Время - Текст напоминания - <u>Выбор получателей</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберете раздел:"
        bot.edit_message_text(
            new_text,
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id,
            reply_markup=self.markup
        )


while True:
    try:
        schedule.run_pending()
        Main()
        bot.infinity_polling(timeout=90, long_polling_timeout=5)
    except:
        continue
