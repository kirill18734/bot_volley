import json
from telebot.async_telebot import AsyncTeleBot
from telebot import types
from config.auto_search_dir import data_config, path_to_config_json, path_to_img_volley, path_to_img_fish
from telebot.types import BotCommand, InlineKeyboardMarkup, InlineKeyboardButton
import calendar
import uuid
from datetime import datetime, timedelta
import asyncio

bot = AsyncTeleBot(data_config['my_telegram_bot']['bot_token'], parse_mode='HTML')
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
        self.selected_list = set()
        self.selected_edit_users = set()
        self.user_states = {}
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

    async def async_init(self):
        await self.start_main()

    # отправка, закрытие, получение результатов опроса
    async def survey(self):
        data = await self.load_data()

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
                        await self.write_data(data)

                    except Exception as e:
                        print(f"Ошибка при отправке опроса пользователю {user}: {e}")
            # опрос автоматически закрывается, когда наступает время закрытие, то изменяем также значения
            elif target_date2 <= current_date and 'Да' in (value['Опрос открыт'], value['Опрос отправлен']):
                value["Опрос открыт"] = "Нет"
                await self.write_data(data)

    async def entry(self, message):
        # Изменить условия фильтрования доступа :
        data = await self.load_data()

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
                    await self.write_data(data)
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
                        await self.write_data(data)
                        break  # Выходим из цикла, если нашли и изменили значение
            self.admin = False
        else:
            self.admin = None
            try:
                await bot.send_message(message.chat.id, "У вас нет доступа к данному боту")
                await bot.delete_message(message.chat.id, message.message_id)
            except:
                pass

    async def load_data(self):
        return await asyncio.to_thread(self._load_data_sync)

    def _load_data_sync(self):
        with open(path_to_config_json, 'r', encoding='utf-8') as file:
            return json.load(file)

    async def write_data(self, data):
        return await asyncio.to_thread(self._write_data_sync, data)

    def _write_data_sync(self, data):
        with open(path_to_config_json, 'w', encoding='utf-8') as file:
            json.dump(data, file, ensure_ascii=False, indent=4)

    async def start_main(self):
        await bot.set_my_commands([BotCommand("start", "В начало"), BotCommand("back", "Назад")])

        @bot.poll_answer_handler(func=lambda answer: True)
        async def handle_poll_answer(answer):
            user_id = answer.user.id
            poll_id = answer.poll_id
            option_ids = 0 if not answer.option_ids else '+1' if answer.option_ids[0] == 1 else 'Буду'

            data = await self.load_data()
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

                        await self.write_data(data)

        @bot.message_handler(commands=['start'])
        async def handle_start(message):
            if message.message_id:
                try:
                    await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
                except:
                    pass
            await self.entry(message)

            if self.admin is not None:
                # очищаем начальные значения
                self.keys.clear()
                self.state_stack.clear()
                self.selected_list.clear()
                self.user_data.clear()

                await self.show_start_menu(message)

        @bot.message_handler(commands=['back'])
        async def handle_back(message):
            await self.entry(message)
            if message.message_id:
                try:
                    await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
                except:
                    pass
            if self.admin is None:
                return
            elif 'Начать' in self.state_stack.keys() and self.keys:
                self.keys.pop()
                await self.navigate()
                return
            while self.state_stack:
                # Получаем последний ключ
                last_key = next(reversed(self.state_stack))
                last_function = self.state_stack[last_key]
                try:
                    # Попытка вызвать функцию
                    await last_function()
                    break  # Выход из цикла, если вызов завершился успешно
                except:
                    # Если произошла ошибка, удаляем элемент и продолжаем цикл
                    del self.state_stack[last_key]
            else:
                self.keys.clear()
                self.state_stack.clear()
                self.selected_list.clear()
                await self.show_start_menu(message)

        @bot.message_handler(
            func=lambda message: self.user_states.get(message.chat.id) in (
                    "add_user", "add_video", "add_statistics", "add_address"))
        async def get_description_reminder(message):
            if self.user_states.get(message.chat.id) == 'add_user':
                await self.add_list(message)
            elif self.user_states.get(message.chat.id) == 'add_video':
                await self.add_list(message)
            elif self.user_states.get(message.chat.id) == 'add_statistics':
                await self.add_list(message)
            elif self.user_states.get(message.chat.id) == 'add_address':
                await self.get_adress_text(message)
            self.user_states.clear()

        @bot.callback_query_handler(func=lambda call: True)
        async def handle_query(call):
            self.call = call
            data = await self.load_data()
            await self.entry(call.message)
            actions = {
                "Управление": self.control_buttons,
                "Доступ к боту": self.main_control,
                "Открыть доступ": self.open_control,
                "Закрыть доступ": self.close_control,
                "💾 Закрыть доступ!": self.dell_list,
                "cancel_dell": self.dell_list,
                "Редактирование команд": self.edit_commands,
                "Редактировать видео": self.edit_video,
                "Добавить видео": self.add_video,
                "Удалить видео": self.dell_video,
                "save_dell_video": self.dell_list,
                "cancel_dell_video": self.dell_list,
                "Редактировать статистику": self.edit_statistic,
                "Добавить статистику": self.add_static,
                "Удалить статистику": self.dell_stitistic,
                "save_dell_stat": self.dell_list,
                "cancel_dell_stat": self.dell_list,
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
                await self.show_start_menu(call.message)

            elif 'Начать' in [self.call.data] + list(self.state_stack.keys()):
                if not self.state_stack:
                    self.state_stack[self.call.data] = self.show_start_menu
                else:
                    self.keys.append(self.call.data)
                await self.navigate()
            else:
                if self.call.data in (actions.keys()):

                    self.state_stack[self.call.data] = actions[self.call.data]
                    await actions[self.call.data]()
                elif self.call.data.startswith("cal_"):
                    date_str = self.call.data[4:]  # Убираем "cal_"
                    await bot.send_message(self.call.message.chat.id, f"Вы выбрали {date_str}",
                                           reply_markup=types.ReplyKeyboardRemove())

                elif self.call.data in list(data["commands"].keys()) + ['admins']:
                    if list(self.state_stack.keys())[-1] == 'Закрыть доступ':
                        self.select_command = self.call.data
                        await self.close()
                    elif list(self.state_stack.keys())[-1] == 'Открыть доступ':
                        self.select_command = self.call.data
                        await self.open()
                    elif list(self.state_stack.keys())[-1] == 'Редактирование команд':
                        self.select_command = self.call.data
                        self.state_stack["command"] = self.edit_command
                        await self.edit_command()
                elif self.call.data.startswith("toggle_"):
                    user_key = '_'.join(self.call.data.split("_")[1:])  # Извлекаем имя пользователя
                    if list(self.state_stack.keys())[-1] == 'Закрыть доступ':
                        if user_key in self.selected_list:
                            self.selected_list.remove(user_key)  # Убираем из списка
                        else:
                            self.selected_list.add(user_key)  # Добавляем в список
                        await self.close()  # Перерисовываем кнопки с обновленными значениями
                    elif list(self.state_stack.keys())[-1] == 'Удалить видео':
                        if user_key in self.selected_list:
                            self.selected_list.remove(user_key)  # Убираем из списка
                        else:
                            self.selected_list.add(user_key)  # Добавляем в список
                        await self.dell_video()
                    elif list(self.state_stack.keys())[-1] == 'Удалить статистику':
                        if user_key in self.selected_list:
                            self.selected_list.remove(user_key)  # Убираем из списка
                        else:
                            self.selected_list.add(user_key)  # Добавляем в список
                        await self.dell_stitistic()
                    elif list(self.state_stack.keys())[-1] == 'Новый опрос':
                        if user_key in self.selected_list:
                            self.selected_list.remove(user_key)  # Убираем из списка
                        else:
                            self.selected_list.add(user_key)  # Добавляем в список
                        await self.select_send_survey()
                elif call.data in ("Товарищеская игра", "Тренировка", "Игра"):
                    self.unique_id = str(uuid.uuid4())  # Генерирует случайный UUID версии 4
                    if self.unique_id not in self.user_data:
                        self.user_data[self.unique_id] = {}  # Создаем запись для уникального ID
                    self.user_data[self.unique_id]['Тип'] = f"{call.data}"
                    if not self.state_stack:
                        self.state_stack[self.call.data] = self.type_play
                    await self.new_survey()
                elif call.data.startswith("prev_") or call.data.startswith("next_"):
                    _, year, month = call.data.split("_")
                    await  self.generate_calendar(int(year), int(month))

                elif call.data.startswith("prevsend_") or call.data.startswith("nextsend_"):
                    _, year, month = call.data.split("_")
                    await self.generate_calendar(int(year), int(month))

                elif call.data.startswith("time_"):

                    _, time = call.data.split("_")

                    if 'Время тренировки/игры' not in (self.user_data[self.unique_id].keys()):
                        # Теперь можно безопасно записать дату
                        self.user_data[self.unique_id]['Время тренировки/игры'] = f"{time}"
                        await self.get_address()
                    # Передаем дату в функцию (убрал .value(), так как строка не имеет такого метода)

                    elif 'Время отправки опроса' not in (self.user_data[self.unique_id].keys()):
                        # Теперь можно безопасно записать дату
                        self.user_data[self.unique_id]['Время отправки опроса'] = f"{time}"
                        await self.save_survey()

                elif call.data.startswith("day_"):

                    _, year, month, day = call.data.split("_")
                    if 'Дата тренировки/игры' not in (self.user_data[self.unique_id].keys()):
                        # Теперь можно безопасно записать дату
                        self.user_data[self.unique_id][
                            'Дата тренировки/игры'] = f"{int(day):02d}-{int(month):02d}-{year}"
                        await self.generate_time_selection()
                    elif 'Дата отправки опроса' not in (self.user_data[self.unique_id].keys()):
                        self.user_data[self.unique_id][
                            'Дата отправки опроса'] = f"{int(day):02d}-{int(month):02d}-{year}"
                        await self.select_time_send_survey()
                    # Передаем дату в функцию (убрал .value(), так как строка не имеет такого метода)


                elif call.data == 'select_send_command':
                    # Теперь можно безопасно записать дату
                    self.user_data[self.unique_id]['Получатели опроса'] = f"{','.join(self.selected_list)}"
                    # Передаем дату в функцию (убрал .value(), так как строка не имеет такого метода)
                    await self.select_date_send_survey()
                elif call.data == "back_hours":
                    # Переход назад (цикл через 2 -> 2.5 -> 3)
                    if self.hour == 2:
                        self.hour = 3
                    elif self.hour == 3:
                        self.hour = 2.5
                    elif self.hour == 2.5:
                        self.hour = 2
                    await self.generate_time_selection()
                elif call.data == "up_hour":
                    # Переход назад (цикл через 2 -> 2.5 -> 3)
                    if self.hour == 2:
                        self.hour = 2.5
                    elif self.hour == 2.5:
                        self.hour = 3
                    elif self.hour == 3:
                        self.hour = 2
                    await self.generate_time_selection()
                elif call.data == "back_edit_hours":
                    # Переход назад (цикл через 2 -> 2.5 -> 3)
                    if self.hour == 2:
                        self.hour = 3
                    elif self.hour == 3:
                        self.hour = 2.5
                    elif self.hour == 2.5:
                        self.hour = 2
                    await self.timeedit_survey()
                elif call.data == "up_edit_hour":
                    # Переход назад (цикл через 2 -> 2.5 -> 3)
                    if self.hour == 2:
                        self.hour = 2.5
                    elif self.hour == 2.5:
                        self.hour = 3
                    elif self.hour == 3:
                        self.hour = 2
                    await self.timeedit_survey()

                elif call.data.startswith("price_"):
                    _, price = call.data.split("_")
                    self.user_data[self.unique_id]['Цена'] = f"{price}"
                    await self.select_send_survey()
                elif self.call.data == "nextdell" and self.current_index < len(self.surveys) - 1:
                    self.current_index += 1
                    await self.del_survey()
                elif self.call.data == "prevdell" and self.current_index > 0:
                    self.current_index -= 1
                    await self.del_survey()
                elif self.call.data == "mainnextedit" and self.current_index < len(self.surveys) - 1:
                    self.current_index += 1
                    await self.edit_survey()
                elif self.call.data == "mainprevedit" and self.current_index > 0:
                    self.current_index -= 1
                    await self.edit_survey()
                elif self.call.data == "mainnextres" and self.current_index < len(self.surveys) - 1:
                    self.current_index += 1
                    await self.result_surveys()
                elif self.call.data == "mainprevres" and self.current_index > 0:
                    self.current_index -= 1
                    await self.result_surveys()
                elif self.call.data.startswith("editsurvey_"):
                    await self.save_edit()
                elif call.data.startswith("prevedit_") or call.data.startswith("nextedit_"):
                    _, year, month = call.data.split("_")
                    await bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                                        reply_markup=await self.generate_edit_survey_calendar(int(year),
                                                                                                              int(month)))
                elif call.data.startswith("prevreminder_") or call.data.startswith("nextreminder_"):
                    _, year, month = call.data.split("_")
                    await bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                                        reply_markup=await self.generate_reminder_calendar(int(year),
                                                                                                           int(month)))
                elif call.data.startswith("preveditsend_") or call.data.startswith("nexteditsend_"):
                    _, year, month = call.data.split("_")
                    await bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                                        reply_markup=await self.generate_editsend_survey_calendar(
                                                            int(year),
                                                            int(month)))
                elif call.data.startswith("editcommand_"):
                    user_key = '_'.join(self.call.data.split("_")[1:])  # Извлекаем имя пользователя
                    if user_key in self.selected_edit_users:
                        self.selected_edit_users.remove(user_key)  # Убираем из списка
                    else:
                        self.selected_edit_users.add(user_key)  # Добавляем в список
                    await self.recieptsedit_survey()
                elif call.data == "recieptsedit_survey":
                    key_del = self.surveys[self.current_index][0]
                    users = data["surveys"][key_del]["Получатели опроса"]
                    users_list = [user for user in users.split(",") if user]  # Убираем пустые строки
                    self.selected_edit_users.update(users_list)  # Добавляем в set
                    await self.recieptsedit_survey()

    async def create_buttons(self, buttons):
        return [InlineKeyboardButton(key, callback_data=value) for key, value in buttons.items()]

    async def edit_message(self, text, buttons=None, add=None, add_row=1, add2=None, add2_row=1, row_date=None,
                           row_time=None, row_price=None, add_end=None):

        self.markup = InlineKeyboardMarkup()  # Создаем новый объект InlineKeyboardMarkup
        if buttons:
            self.markup = InlineKeyboardMarkup([await self.create_buttons(buttons)])

        if add:
            row = []  # Список для хранения кнопок в текущей строке
            for key, value in add.items():
                if 'http' not in value:
                    row.append(InlineKeyboardButton(key, callback_data=value))
                else:
                    row.append(InlineKeyboardButton(key, url=value))

                # Если достигли максимального количества кнопок в строке, добавляем строку в разметку
                if len(row) == add_row:
                    self.markup.add(*row)  # Добавляем текущую строку в разметку
                    row = []  # Очищаем список для следующей строки

            # Если остались кнопки в последней строке, добавляем их
            if row:
                self.markup.add(*row)
        if add2:
            row = []  # Список для хранения кнопок в текущей строке
            for key, value in add2.items():
                if 'http' not in value:
                    row.append(InlineKeyboardButton(key, callback_data=value))
                else:
                    row.append(InlineKeyboardButton(key, url=value))

                # Если достигли максимального количества кнопок в строке, добавляем строку в разметку
                if len(row) == add2_row:
                    self.markup.add(*row)  # Добавляем текущую строку в разметку
                    row = []  # Очищаем список для следующей строки

            # Если остались кнопки в последней строке, добавляем их
            if row:
                self.markup.add(*row)
        if row_date:
            self.markup.row(*[InlineKeyboardButton(month, callback_data="ignore") for month in row_date[:1]])
            self.markup.row(*[InlineKeyboardButton(dayweek, callback_data="ignore") for dayweek in row_date[1:8]])

            for row_ in row_date[8:-2]:
                row_list = []
                for row_line in row_:
                    row_list.append(row_line)
                    if len(row_list) == 7:
                        self.markup.row(*row_list)

            row_next = []
            for row_ in row_date[-2:]:
                row_next.append(row_)
                if len(row_next) == 2:
                    self.markup.row(*row_next)

        if row_time:

            for row_ in row_time[:-2]:
                row_list = []
                for row_line in row_:
                    row_list.append(row_line)
                    if len(row_list) == 3:
                        self.markup.row(*row_list)
            row_next = []
            for row_ in row_time[-2:]:
                row_next.append(row_)
                if len(row_next) == 2:
                    self.markup.row(*row_next)
        if row_price:
            for row_ in row_price:
                row_list = []
                for row_line in row_:
                    row_list.append(row_line)
                    if len(row_list) == 4:
                        self.markup.row(*row_list)
                        row_list = []  # Сбрасываем row_list после добавления в row
                # Добавляем оставшиеся элементы, если они есть
                if row_list:
                    self.markup.row(*row_list)
        if add_end:
            row = []  # Список для хранения кнопок в текущей строке
            for key, value in add_end.items():
                if 'http' not in value:
                    row.append(InlineKeyboardButton(key, callback_data=value))
                else:
                    row.append(InlineKeyboardButton(key, url=value))

                # Если достигли максимального количества кнопок в строке, добавляем строку в разметку
                if len(row) == add_end:
                    self.markup.add(*row)  # Добавляем текущую строку в разметку
                    row = []  # Очищаем список для следующей строки

            # Если остались кнопки в последней строке, добавляем их
            if row:
                self.markup.add(*row)
        await bot.edit_message_text(
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id,
            text=text,
            reply_markup=self.markup,
            parse_mode="HTML"
        )

    async def show_start_menu(self, message):
        buttons_name = ["Начать"]
        data = await self.load_data()
        response_text = f"""Вы находитесь в разделе: <u>Главное меню</u>\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"""
        if self.admin:
            buttons_name.append('Управление')
        try:
            buttons = {name: name for name in buttons_name}
            await self.edit_message(response_text, buttons)
        except:
            users = [str(name.replace('@', '')).split('_')[0] for name in
                     data["commands"]['RedHeads']["users"].values()]
            if data["commands"]['RedHeads']['users']:
                if any(user in users for user in [message.chat.id, str(message.chat.username).replace('@', '')]):
                    with open(path_to_img_fish, 'rb') as photo:
                        await bot.send_photo(message.chat.id, photo)
                else:
                    with open(path_to_img_volley, 'rb') as photo:
                        await bot.send_photo(message.chat.id, photo)
            else:
                with open(path_to_img_volley, 'rb') as photo:
                    await bot.send_photo(message.chat.id, photo)

            await bot.send_message(chat_id=message.chat.id, text=response_text, reply_markup=self.markup,
                                   parse_mode="HTML")

    # Запуск бота
    async def navigate(self):
        get_data = await self.load_data()
        data = get_data["commands"]
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
            await self.edit_message(response_text, add=add)
            # Формируем путь с подчёркиванием последнего ключа

    async def control_buttons(self):
        buttons_name = ["Доступ к боту", "Опрос", "Напоминание", "Редактирование команд"]
        buttons = {name: name for name in buttons_name}
        response_text = """Вы находитесь в разделе: Главное меню - <u>Управление</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"""
        await self.edit_message(response_text, buttons)

    async def main_control(self):
        buttons_name = ["Открыть доступ", "Закрыть доступ"]
        buttons = {name: name for name in buttons_name}
        response_text = """Вы находитесь в разделе: Главное меню - Управление -  <u>Доступ к боту</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"""
        await self.edit_message(response_text, buttons)

    async def open_control(self):
        data = await self.load_data()
        buttons_name = [key for key in data["commands"].keys()]
        buttons = {name: name for name in buttons_name}
        buttons['Админы'] = 'admins'
        response_text = f"Вы находитесь в разделе: Главное меню - Управление - Доступ к боту - <u>Открыть доступ</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"
        await self.edit_message(response_text, buttons)

    async def add_list(self, message):

        if message.text not in ['/back',
                                '/start']:
            if ":" in str(message.text):
                new_video_stats = str(message.text).replace(' ', '').replace('\n', ',').replace(',,', ',').replace('@',
                                                                                                                   '').split(
                    ',')  # Получаем введенное имя сотрудника

                data = await self.load_data()
                for new_name in new_video_stats:
                    name, value = new_name.split(":", 1)
                    if ":" in str(new_name) and len(name) >= 3 <= len(value):

                        if self.user_states[self.call.message.chat.id] in ("add_statistics", "add_video"):
                            response_test = 'Неправильны указаны значения. Ожидается длина названия и ссылки минимум 3 знака, и ссылка должна начинаться с http'
                            text_header = 'Статистика' if self.user_states[
                                                              self.call.message.chat.id] == "add_statistics" else "Видео"
                            if value not in data["commands"][self.select_command][text_header].values():
                                response_test = 'Ссылка добавлена'
                                data["commands"][self.select_command][text_header][name] = value
                            else:

                                response_test = f'Ссылка {value} уже существует'
                                await bot.answer_callback_query(self.call.id, response_test,
                                                                show_alert=True)
                                try:
                                    await bot.delete_message(chat_id=message.chat.id,
                                                             message_id=message.message_id)
                                except:
                                    pass
                                self.state_stack = dict(list(self.state_stack.items())[:-1])
                                if text_header == 'Статистика':
                                    await self.edit_statistic()
                                else:
                                    await self.edit_video()
                                return
                        else:
                            if self.select_command != 'admins' and value not in data["commands"][self.select_command][
                                "users"].values():
                                data["commands"][self.select_command]["users"][name] = value
                            elif self.select_command == 'admins' and value not in data["admins"].values():
                                data["admins"][name] = value
                            else:
                                response_test = f'Пользователь с id: {value} уже существует'
                                await bot.answer_callback_query(self.call.id, response_test,
                                                                show_alert=True)
                                try:
                                    await bot.delete_message(chat_id=message.chat.id,
                                                             message_id=message.message_id)
                                except:
                                    pass
                    else:
                        try:
                            await bot.delete_message(chat_id=message.chat.id,
                                                     message_id=message.message_id)
                        except:
                            pass
                        response_test = 'Неправильны указаны значения. Ожидается длина названия и ссылки минимум 3 знака, и ссылка должна начинаться с http'
                        await bot.answer_callback_query(self.call.id, response_test,
                                                        show_alert=True)
                        self.state_stack = dict(list(self.state_stack.items())[:-1])
                        await self.state_stack[list(self.state_stack.keys())[-1]]()
                        return

                await self.write_data(data)
                response_test = 'Ссылки добавлены' if len(new_video_stats) > 1 and self.user_states[
                    self.call.message.chat.id] in ("add_statistics", "add_video") else 'Ссылка добавлена' if len(
                    new_video_stats) == 1 and self.user_states[self.call.message.chat.id] in ("add_statistics",
                                                                                              "add_video") else 'Пользователь добавлен' if len(
                    new_video_stats) == 1 else 'Пользователи добавлены'
                await bot.answer_callback_query(self.call.id, response_test,
                                                show_alert=True)
                try:
                    await bot.delete_message(chat_id=message.chat.id,
                                             message_id=message.message_id)
                except:
                    pass
                self.state_stack = dict(list(self.state_stack.items())[:-1])
                await self.state_stack[list(self.state_stack.keys())[-1]]()
            else:
                try:
                    await bot.delete_message(chat_id=message.chat.id,
                                             message_id=message.message_id)
                except:
                    pass
                response_test = 'Некорректное добавление, ознакомьтесь с примерами и попробуйте еще раз'
                await bot.answer_callback_query(self.call.id, response_test,
                                                show_alert=True)
                self.state_stack = dict(list(self.state_stack.items())[:-1])

                await self.state_stack[list(self.state_stack.keys())[-1]]()
        else:
            if message.message_id:
                try:
                    await bot.delete_message(chat_id=message.chat.id,
                                             message_id=message.message_id)
                except:
                    pass
            self.state_stack = dict(list(self.state_stack.items())[:-1])
            await self.state_stack[list(self.state_stack.keys())[-1]]()

    async def close_control(self):
        data = await self.load_data()
        buttons_name = [key for key in data["commands"].keys()]
        buttons = {name: name for name in buttons_name}
        buttons['Админы'] = 'admins'
        response_text = f"Вы находитесь в разделе: Главное меню - Управление - Доступ к боту - <u>Закрыть доступ</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"
        await self.edit_message(response_text, buttons)

    async def edit_commands(self):
        data = await self.load_data()
        buttons_name = [key for key in data["commands"].keys()]
        buttons = {name: name for name in buttons_name}
        response_text = f"Вы находитесь в разделе: Главное меню - Управление - Доступ к боту - <u>Редактирование команд</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"
        await self.edit_message(response_text, buttons)

    async def close(self):
        data = await self.load_data()
        users = (
            data["commands"][self.select_command]["users"].items() if self.select_command != 'admins' else
            data['admins'].items())
        add = {}
        for keys, value in users:
            value = str(value).split("_")[0]
            is_selected = f"{keys}_{value}_{self.select_command}" in self.selected_list  # Проверяем, выбран ли пользователь
            icon = "✅" if is_selected else "❌"  # Меняем иконку
            button_text = f"{icon} {keys}({value})"
            add[button_text] = f"toggle_{keys}_{value}_{self.select_command}"
        add2 = {"Отмена!": 'cancel_dell', '💾 Закрыть доступ!': '💾 Закрыть доступ!'}

        text = self.select_command if self.select_command != 'admins' else 'Админы'
        response_text = f"Вы находитесь в разделе: Главное меню - Управление -  Доступ к боту - Закрыть доступ -  <u>{text}</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"
        await self.edit_message(response_text, add=add, add_row=3, add2=add2, add2_row=2)

    async def dell_list(self):
        # Загружаем данные из файла
        data = await self.load_data()
        if self.call.data == '💾 Закрыть доступ!':
            if self.select_command == 'admins' and (
                    len(data['admins'].keys()) == 1 or len(data['admins'].keys()) == len(
                self.selected_list)) and self.selected_list:
                text = 'пользователи НЕ УДАЛЕНЫ' if len(self.selected_list) > 1 else 'пользователь НЕ УДАЛЕН'
                response_text = f'Должен быть минимум 1 админ, {text}'
                await bot.answer_callback_query(self.call.id, response_text,
                                                show_alert=True)
                self.state_stack = dict(list(self.state_stack.items())[:-1])
                await self.close_control()

            elif self.select_command and self.selected_list:
                # Удаляем пользователей
                for user in self.selected_list:
                    data_user = user.split("_")
                    if data_user[-1] != 'admins':
                        # Удаляем пользователя из данных
                        if data_user[0] in data["commands"][data_user[-1]]["users"]:
                            del data["commands"][data_user[-1]]["users"][data_user[0]]
                    else:
                        if data_user[0] in data["admins"]:
                            del data["admins"][data_user[0]]
                # Сохраняем обновленные данные обратно в файл
                await self.write_data(data)  # Передаем измененные данные в функцию сохранения

                response_text = 'Пользователи удалены' if len(self.selected_list) > 1 else 'Пользователь удален'
                await bot.answer_callback_query(self.call.id, response_text,
                                                show_alert=True)
        elif self.call.data == 'cancel_dell':
            self.state_stack = dict(list(self.state_stack.items())[:-1])
            await self.close_control()
        elif self.call.data == 'cancel_dell_video':
            self.state_stack = dict(list(self.state_stack.items())[:-2])
            await self.edit_video()
        elif self.call.data == 'cancel_dell_stat':
            self.state_stack = dict(list(self.state_stack.items())[:-2])
            await self.edit_statistic()
        elif self.call.data in ('save_dell_video', 'save_dell_stat'):
            text = 'Видео' if self.call.data == 'save_dell_video' else 'Статистика'
            # Удаляем пользователей
            if self.selected_list:
                for user in self.selected_list:
                    data_user = user.split("_")
                    if data_user[0] in data["commands"][data_user[-1]][text]:
                        del data["commands"][data_user[-1]][text][data_user[0]]
                # Сохраняем обновленные данные обратно в файл
                await self.write_data(data)  # Передаем измененные данные в функцию сохранения
                response_text = 'Ссылки удалены' if len(self.selected_list) > 1 else 'Ссылка удалена'
                await bot.answer_callback_query(self.call.id, response_text,
                                                show_alert=True)
            self.state_stack = dict(list(self.state_stack.items())[:-2])
            next_method = self.edit_video if text == 'Видео' else self.edit_statistic
            await next_method()

        self.selected_list.clear()

    async def open(self):
        text = self.select_command if self.select_command != 'admins' else 'Админы'
        response_text = f"Вы находитесь в разделе: Главное меню - Управление -  Доступ к боту - Открыть доступ - <u>{text}</u>.\n\nИспользуй " \
                        f"кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start " \
                        f"\n\nНапишите Ник и id пользователя для добавления через двоеточие, пример:\n Вася:2938214371 или " \
                        f"Петя:@petya (можно без @). \nТакже можно добавлять списком нескольких пользователей через запятую, " \
                        f"пример:\nВася:2938214371, Петя:@petya, Lena:lenusik"

        self.user_states[self.call.message.chat.id] = "add_user"
        await self.edit_message(response_text)

    async def edit_command(self):
        buttons_name = ["Редактировать видео", "Редактировать статистику"]
        buttons = {name: name for name in buttons_name}
        response_text = f"""Вы находитесь в разделе: Главное меню - Управление -  Редактирование команд - <u>{self.select_command}</u>\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"""
        await self.edit_message(response_text, buttons)

    async def edit_video(self):
        buttons_name = ["Добавить видео", "Удалить видео"]
        buttons = {name: name for name in buttons_name}
        response_text = f"""Вы находитесь в разделе: Главное меню - Управление -  Редактирование команд - {self.select_command} - <u>Редактировать видео</u>\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"""
        await self.edit_message(response_text, buttons)

    async def add_video(self):
        response_text = f"Вы находитесь в разделе: Главное меню - Управление -  Редактирование команд - {self.select_command} - Редактировать видео - <u>Добавить видео</u> .\n\nИспользуй " \
                        f"кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start " \
                        f"\n\nНапишите название  и ссылку на видео для добавления через двоеточие, пример:\nСезон 2024-2025:https://disk.yandex.ru/d/bWFMzczzg" \
                        f"\nТакже можно добавлять списком несколько ссылок через запятую, " \
                        f"пример:\nСезон 2024-2025:https://disk.yandex.ru/d/bWFMzczzg, Сезон 2025-2026:https://disk.yandex.ru/d/bW343Mzczzg"
        # Редактируем текущее сообщение, чтобы запросить имя сотрудника

        self.user_states[self.call.message.chat.id] = "add_video"
        await self.edit_message(response_text)

    async def dell_video(self):
        data = await self.load_data()
        add = {}
        for keys, value in data["commands"][self.select_command]["Видео"].items():
            is_selected = f"{keys}_Видео_{self.select_command}" in self.selected_list  # Проверяем, выбран ли пользователь
            icon = "✅" if is_selected else "❌"  # Меняем иконку
            button_text = f"{icon} {keys}"
            add[button_text] = f"toggle_{keys}_Видео_{self.select_command}"

        add2 = {'Отмена!': 'cancel_dell_video', "💾 Сохранить!": 'save_dell_video'}

        response_text = f"Вы находитесь в разделе: Главное меню - Управление -  Редактирование команд - {self.select_command} - Редактировать видео - <u>Удалить видео</u> .\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"
        await self.edit_message(response_text, add=add, add_row=3, add2=add2, add2_row=2)

    async def edit_statistic(self):
        buttons_name = ["Добавить статистику", "Удалить статистику"]
        buttons = {name: name for name in buttons_name}
        response_text = f"""Вы находитесь в разделе: Главное меню - Управление -  Редактирование команд - {self.select_command} - <u>Редактировать ститистику</u>\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"""
        await self.edit_message(response_text, buttons)

    async def add_static(self):
        response_text = f"Вы находитесь в разделе: Главное меню - Управление -  Редактирование команд - {self.select_command} - Редактировать статистику - <u>Добавить статистику</u> .\n\nИспользуй " \
                        f"кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start " \
                        f"\n\nНапишите название  и ссылку на видео для добавления через двоеточие, пример:\nСезон 2024-2025:https://disk.yandex.ru/d/bWFMzczzg" \
                        f"\nТакже можно добавлять списком несколько ссылок через запятую, " \
                        f"пример:\nСезон 2024-2025:https://disk.yandex.ru/d/bWFMzczzg, Сезон 2025-2026:https://disk.yandex.ru/d/bW343Mzczzg"
        # Редактируем текущее сообщение, чтобы запросить имя сотрудника
        self.user_states[self.call.message.chat.id] = "add_statistics"
        await self.edit_message(response_text)
        # Устанавливаем состояние ожидания ответа от пользователя

    async def dell_stitistic(self):
        data = await self.load_data()
        add = {}
        for keys, value in data["commands"][self.select_command]["Статистика"].items():
            is_selected = f"{keys}_Стат_{self.select_command}" in self.selected_list  # Проверяем, выбран ли пользователь
            icon = "✅" if is_selected else "❌"  # Меняем иконку
            button_text = f"{icon} {keys}"
            add[button_text] = f"toggle_{keys}_Стат_{self.select_command}"

        add2 = {'Отмена!': 'cancel_dell_stat', '💾 Сохранить!': 'save_dell_stat'}

        response_text = f"Вы находитесь в разделе: Главное меню - Управление -  Редактирование команд - {self.select_command} - Редактировать статистику - <u>Удалить статистику</u> .\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"

        await self.edit_message(response_text, add=add, add_row=3, add2=add2, add2_row=2)

    async def the_survey(self):
        buttons_name = ["Новый опрос", "Удалить опрос", "Редактировать опрос", "Результаты опросов"]
        buttons = {name: name for name in buttons_name}
        response_text = f"Вы находитесь в разделе: Главное меню - Управление - <u>Опрос</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"
        await self.edit_message(response_text, buttons)

    async def type_play(self):
        buttons_name = ["Игра", "Тренировка", "Товарищеская игра"]
        buttons = {name: name for name in buttons_name}
        response_text = f"Вы находитесь в разделе: Главное меню - Управление - Опрос - <u>Новый опрос</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"
        await self.edit_message(response_text, buttons)

    async def generate_calendar(self, year, month, response_text=None):
        if not response_text:
            text_responce = "\n".join(
                f"{k}: {v}" for game_data in self.user_data.values() for k, v in game_data.items())
            response_text = f"Вы находитесь в разделе: Главное меню - Управление - Новый опрос - {self.user_data[self.unique_id]['Тип']} - <u>Дата</u>.\n\n{text_responce}.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите дату игры/тренировки:"
        cal = calendar.monthcalendar(year, month)
        buttons = [f"{tmonth_names[month]} {year}", "Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

        # Дни месяца
        for week in cal:
            row = []
            for day in week:
                if day == 0:
                    row.append(InlineKeyboardButton(" ", callback_data="ignore"))
                else:
                    row.append(InlineKeyboardButton(
                        str(day),
                        callback_data=f"day_{year}_{month:02d}_{day:02d}"
                    ))
            buttons.append(row)

        prev_month, prev_year = (month - 1, year) if month > 1 else (12, year - 1)
        next_month, next_year = (month + 1, year) if month < 12 else (1, year + 1)

        buttons.append(InlineKeyboardButton("<", callback_data=f"prev_{prev_year}_{prev_month}"))
        buttons.append(InlineKeyboardButton(">", callback_data=f"next_{next_year}_{next_month}"))

        await self.edit_message(response_text, row_date=buttons)
        # return markup

    async def new_survey(self):
        text_responce = "\n".join(f"{k}: {v}" for game_data in self.user_data.values() for k, v in game_data.items())
        response_text = f"Вы находитесь в разделе: Главное меню - Управление - Новый опрос - {self.user_data[self.unique_id]['Тип']} - <u>Дата</u>.\n\n{text_responce}.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите дату игры/тренировки:"
        now = datetime.now()
        await self.generate_calendar(now.year, now.month, response_text)

    async def generate_time_selection(self):

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
        response_text = f"Вы находитесь в разделе: Главное меню - Управление - Новый опрос - {self.user_data[self.unique_id]['Тип']} - Дата -  <u>Время</u>\n\n{text_responce}.\n\nИспользуйте кнопки для навигации. Чтобы вернуться на шаг назад, используйте команду /back. В начало /start \n\nВыберите время (интервал - {text}) игры/тренировки:"

        buttons = []
        for i in range(0, len(times), 4):
            buttons.append(
                [InlineKeyboardButton(time,
                                      callback_data=f"time_{time}")
                 for
                 time in
                 times[i:i + 4]])

        buttons.append(InlineKeyboardButton("<", callback_data=f"back_hours"))
        buttons.append(InlineKeyboardButton(">", callback_data=f"up_hour"))

        await self.edit_message(response_text, row_time=buttons)

    async def get_address(self):
        text_responce = "\n".join(f"{k}: {v}" for game_data in self.user_data.values() for k, v in game_data.items())
        response_text = f"Вы находитесь в разделе: Главное меню - Управление - Новый опрос - {self.user_data[self.unique_id]['Тип']} - Дата - Время - <u>Адрес</u>\n\n{text_responce}.\n\nИспользуйте кнопки для навигации. Чтобы вернуться на шаг назад, используйте команду /back. В начало /start \n\nНапишите адрес:"

        self.user_states[self.call.message.chat.id] = "add_address"
        await self.edit_message(response_text)

    async def get_adress_text(self, message):
        self.user_data[self.unique_id]['Адрес'] = message.text
        try:
            await bot.delete_message(chat_id=message.chat.id,
                                     message_id=message.message_id)
        except:
            pass
        await self.get_price()

    async def get_price(self):
        text_responce = "\n".join(f"{k}: {v}" for game_data in self.user_data.values() for k, v in game_data.items())
        prices = [x for x in range(300, 1501, 50)]
        response_text = (
            f"Вы находитесь в разделе: Главное меню - Управление - Новый опрос - {self.user_data[self.unique_id]['Тип']} - Дата - Время - Адрес - <u>Цена</u>\n\n{text_responce}.\n\nИспользуйте кнопки для навигации. Чтобы вернуться на шаг назад, используйте команду /back. В начало /start\n\nВыберите цену игры/тренировки:")

        buttons = [
            [InlineKeyboardButton(str(price), callback_data=f"price_{price}") for price in prices]
        ]

        await self.edit_message(response_text, row_price=buttons)

    async def select_send_survey(self):
        text_responce = "\n".join(f"{k}: {v}" for game_data in self.user_data.values() for k, v in game_data.items())
        data = await self.load_data()
        users = {name: name for name in data["commands"].keys()}
        users['Админы'] = 'admins'

        # Создание кнопок
        buttons = [
            [
                InlineKeyboardButton(
                    f"{'✅' if value in self.selected_list else '❌'} {key}",
                    callback_data=f"toggle_{value}"
                )
                for key, value in users.items()
            ]
        ]

        response_text = (
            f"Вы находитесь в разделе: Главное меню - Управление - Новый опрос - {self.user_data[self.unique_id]['Тип']} - Дата - Время - Адрес - Цена - <u>Выбор команды для опроса</u>\n\n{text_responce}.\n\nИспользуйте кнопки для навигации. Чтобы вернуться на шаг назад, используйте команду /back. В начало /start\n\nВыберите команду для опроса:")

        add = {"Дальше": "select_send_command"}
        await self.edit_message(response_text, row_price=buttons, add_end=add)

    async def select_date_send_survey(self):
        text_responce = "\n".join(f"{k}: {v}" for game_data in self.user_data.values() for k, v in game_data.items())
        response_text = (
            f"Вы находитесь в разделе: Главное меню - Управление - Новый опрос - {self.user_data[self.unique_id]['Тип']} - Дата - Время - Адрес - Цена - Выбор команды для опроса - <u>Дата отправки опроса</u>\n\n{text_responce}.\n\nИспользуйте кнопки для навигации. Чтобы вернуться на шаг назад, используйте команду /back. В начало /start\n\nВыберите дату отправки опроса:")
        now = datetime.now()
        await self.generate_calendar(now.year, now.month, response_text)

    async def select_time_send_survey(self):
        time = [f"{hour:02}:{minute:02}" for hour in range(9, 24) for minute in [0, 30]]
        text_responce = "\n".join(f"{k}: {v}" for game_data in self.user_data.values() for k, v in game_data.items())
        buttons = [[InlineKeyboardButton(key, callback_data=f"time_{key}") for key in time]]
        # Разбиваем список кнопок на подсписки по 5 элементов
        response_text = (
            f"Вы находитесь в разделе: Главное меню - Управление - Новый опрос - {self.user_data[self.unique_id]['Тип']} - Дата - Время - Адрес - Цена - Выбор команды для опроса - Дата отправки опроса - <u>Время отправки опроса</u>\n\n{text_responce}.\n\nИспользуйте кнопки для навигации. Чтобы вернуться на шаг назад, используйте команду /back. В начало /start\n\nВыберите время отправки опроса:")
        await self.edit_message(response_text, row_price=buttons)

    async def save_survey(self):
        text_responce = "\n".join(f"{k}: {v}" for game_data in self.user_data.values() for k, v in game_data.items())
        buttons = {"Отмена": "cancel_send_survey", "Запланировать опрос": "save_send_survey"}

        response_text = (
            f"Вы находитесь в разделе: Главное меню - Управление - Новый опрос - {self.user_data[self.unique_id]['Тип']} - Дата - Время - Адрес - Цена - Выбор команды для опроса - Дата отправки опроса - Время отправки опроса - <u>Сохранение опроса</u>\n\n{text_responce}.\n\nИспользуйте кнопки для навигации. Чтобы вернуться на шаг назад, используйте команду /back. В начало /start\n\nПроверьте подготовленный опрос и выберете раздел")
        await self.edit_message(response_text, buttons=buttons)

    async def save(self):
        data = await self.load_data()
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
        await self.write_data(data)

        response_text = 'Задание запланировано'
        await bot.answer_callback_query(self.call.id, response_text, show_alert=True)

        # Очищаем временные данные
        self.user_data.clear()
        self.selected_list.clear()
        await self.the_survey()

    async def del_survey(self):
        self.data = await self.load_data()
        """Отображает текущий опрос с кнопками навигации"""
        self.surveys = list(self.data["surveys"].items())
        if not self.surveys:
            response_text = 'Нет доступных опросов.'
            await bot.answer_callback_query(self.call.id, response_text,
                                            show_alert=True)
            return

        survey_id, survey_data = self.surveys[self.current_index]
        response_text = (
            f"Вы находитесь в разделе: Главное меню - Управление - <u>Удалить опрос</u>.\n\n")

        response_text += f"<b>Опрос {self.current_index + 1} из {len(self.surveys)}</b>\n\n"
        response_text += "\n".join(f"{k}: {v}" for k, v in survey_data.items())
        response_text += '\n\nИспользуйте кнопки для навигации. Чтобы вернуться на шаг назад, используйте команду /back. В начало /start\n\nВыбирете опрос для удаления:'
        add = {
            "<": "prevdell" if self.current_index > 0 else None,
            ">": "nextdell" if self.current_index < len(self.surveys) - 1 else None
        }

        # Убираем ключи с значением None
        add = {key: value for key, value in add.items() if value is not None}

        add2 = {"Отмена": "cansel_survey", "Удалить опрос": "dell_survey"}

        await self.edit_message(response_text, add=add, add_row=2, add2=add2, add2_row=2)

    async def save_dell_survey(self):
        data = await self.load_data()
        key_del = self.surveys[self.current_index][0]
        del data["surveys"][key_del]
        # Сохраняем обновленные данные обратно в файл
        await self.write_data(data)  # Передаем измененные данные в функцию сохранения
        response_text = 'Опрос удален'
        await bot.answer_callback_query(self.call.id, response_text,
                                        show_alert=True)
        self.current_index = 0
        await self.the_survey()

    async def edit_survey(self):
        self.data = await self.load_data()
        """Отображает текущий опрос с кнопками навигации"""
        self.surveys = list(self.data["surveys"].items())
        if not self.surveys:
            response_text = 'Нет доступных опросов.'
            await bot.answer_callback_query(self.call.id, response_text, show_alert=True)
            return

        survey_id, survey_data = self.surveys[self.current_index]
        response_text = (
            f"Вы находитесь в разделе: Главное меню - Управление - <u>Редактировать опрос</u>.\n\n"
        )

        response_text += f"<b>Опрос {self.current_index + 1} из {len(self.surveys)}</b>\n\n"
        response_text += "\n".join(f"{k}: {v}" for k, v in survey_data.items() if k not in (
            'Отметились', 'Количество отметившихся', 'id опроса', 'Опрос отправлен', 'Опрос открыт'))
        response_text += ('\n\nИспользуйте кнопки для навигации. Чтобы вернуться на шаг назад, '
                          'используйте команду /back. В начало /start\n\nВыберите опрос для удаления:')
        add = {
            "<": "mainprevedit" if self.current_index > 0 else None,
            ">": "mainnextedit" if self.current_index < len(self.surveys) - 1 else None
        }

        # Убираем ключи с значением None
        add = {key: value for key, value in add.items() if value is not None}

        edit_buttons = [[
            InlineKeyboardButton("Изменить тип", callback_data="typeedit_survey"),
            InlineKeyboardButton("Изменить дату тренировки/игры", callback_data="dateedit_survey"),
            InlineKeyboardButton("Изменить время тренировки/игры", callback_data="timeedit_survey"),
            InlineKeyboardButton("Изменить адрес", callback_data="addressedit_survey"),
            InlineKeyboardButton("Изменить цену", callback_data="priceedit_survey"),
            InlineKeyboardButton("Изменить получателей", callback_data="recieptsedit_survey"),
            InlineKeyboardButton("Изменить дату отправки опроса", callback_data="datesend_survey"),
            InlineKeyboardButton("Изменить время отправки опроса", callback_data="timesend_survey")

        ]]
        await self.edit_message(response_text, add=add, add_row=2, row_price=edit_buttons)

    async def typeedit_survey(self):

        buttons = [InlineKeyboardButton(key, callback_data=f"editsurvey_Тип_{key}") for key in
                   ["Игра", "Тренировка", "Товарищеская игра"]]
        self.markup = InlineKeyboardMarkup([buttons])
        new_text = f"Вы находитесь в разделе: Главное меню - Управление - Редактировать опрос - <u>Изменить тип</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"
        await bot.edit_message_text(
            new_text,
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id,
            reply_markup=self.markup
        )


    async def dateedit_survey(self):
        now = datetime.now()
        new_text = f"Вы находитесь в разделе: Главное меню - Управление - Редактировать опрос - <u>Изменить дату тренировки/игры</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите дату:"
        await bot.edit_message_text(
            new_text,
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id,
            reply_markup=self.markup
        )

    async def timeedit_survey(self):

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
        await bot.edit_message_text(
            new_text,
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id,
            reply_markup=self.markup
        )

    async def addressedit_survey(self):
        new_text = (
            f"Вы находитесь в разделе: Главное меню - Управление - Редактировать опрос - <u>Изменить адрес</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nНапишите адрес:"
        )
        await bot.edit_message_text(
            new_text,
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id
        )
        bot.register_next_step_handler(self.call.message, self.get_adress_edit_text)

    async def get_adress_edit_text(self, message):
        self.call.data = f"editsurvey_Адрес_{message.text}"
        try:
            await bot.delete_message(chat_id=message.chat.id,
                                     message_id=message.message_id)
        except:
            pass
        await self.save_edit()

    async def priceedit_survey(self):
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

        await bot.edit_message_text(
            new_text,
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id,
            reply_markup=self.markup
        )

    async def recieptsedit_survey(self):
        self.markup = InlineKeyboardMarkup()
        data = await self.load_data()
        buttons = []
        users = list(data["commands"].keys()) + ['Админы']
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
        await bot.edit_message_text(
            new_text,
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id,
            reply_markup=self.markup
        )

    async def generate_editsend_survey_calendar(self, year, month):
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

    async def datesend_survey(self):
        now = datetime.now()
        self.markup = self.generate_editsend_survey_calendar(now.year, now.month)
        new_text = f"Вы находитесь в разделе: Главное меню - Управление - Редактировать опрос - <u>Изменить дату отправки опроса</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите дату:"
        await bot.edit_message_text(
            new_text,
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id,
            reply_markup=self.markup
        )

    async def timesend_survey(self):
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

        await bot.edit_message_text(
            new_text,
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id,
            reply_markup=self.markup
        )

    async def save_edit(self):
        data = await self.load_data()
        key_del = self.surveys[self.current_index][0]
        new_value = self.call.data.split("_")

        if new_value[1] != 'Получатели опроса':
            data["surveys"][key_del][new_value[1]] = new_value[-1]
        else:
            data["surveys"][key_del][new_value[1]] = ','.join(self.selected_edit_users)
        await self.write_data(data)  # Передаем измененные данные в функцию сохранения
        response_text = (
            f'{new_value[1]} изменен' if new_value[1] in ("Тип", "Адрес") else
            f'{new_value[1]} изменена' if new_value[1] in ("Дата тренировки/игры", "Цена") else
            f'{new_value[1]} изменены' if new_value[1] == "Получатели опроса" else
            f'{new_value[1]} изменено'
        )

        await bot.answer_callback_query(self.call.id, response_text,
                                        show_alert=True)
        await self.edit_survey()

    async def format_dict(self, d, indent=0, base_indent=4):
        result = ""
        for key, value in d.items():
            current_indent = indent + base_indent  # Смещаем все уровни на base_indent
            if isinstance(value, dict):
                result += " " * current_indent + f"{key}:\n" + await self.format_dict(value, current_indent,
                                                                                      base_indent)
            else:
                result += " " * current_indent + f"{key}: {value}\n"
        return result

    async def result_surveys(self):
        self.data = await self.load_data()
        """Отображает текущий опрос с кнопками навигации"""
        self.surveys = list(self.data["surveys"].items())
        if not self.surveys:
            response_text = 'Нет доступных опросов.'
            await bot.answer_callback_query(self.call.id, response_text, show_alert=True)
            return

        survey_id, survey_data = self.surveys[self.current_index]
        text_responce = (
            f"Вы находитесь в разделе: Главное меню - Управление - <u>Результаты опросов</u>.\n\n"
        )

        text_responce += f"<b>Опрос {self.current_index + 1} из {len(self.surveys)}</b>\n\n"
        text_responce += "\n".join(f"{k}: {v}" for k, v in survey_data.items() if k not in ('id опроса', 'Отметились'))
        # Генерация текста
        text_responce += "\nОтметились:\n" + await self.format_dict(survey_data["Отметились"], base_indent=4)
        text_responce += ('\n\nИспользуйте кнопки для навигации. Чтобы вернуться на шаг назад, '
                          'используйте команду /back. В начало /start\n\nВыберите опрос для удаления:')

        navigation_buttons = [
            InlineKeyboardButton("<", callback_data="mainprevres") if self.current_index > 0 else None,
            InlineKeyboardButton(">", callback_data="mainnextres") if self.current_index < len(
                self.surveys) - 1 else None
        ]
        navigation_buttons = [btn for btn in navigation_buttons if btn]  # Убираем None

        self.markup = InlineKeyboardMarkup([navigation_buttons])

        await bot.edit_message_text(
            text_responce,
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id,
            reply_markup=self.markup,
            parse_mode="HTML"
        )

    async def reminder(self):
        buttons = [InlineKeyboardButton(key, callback_data=key) for key in
                   ["Создать напоминание", "Редактировать напоминание", "Результаты напоминаний"]]
        self.markup = InlineKeyboardMarkup([buttons])
        self.markup.add(InlineKeyboardButton("Удалить напоминание", callback_data="Удалить напоминание"))
        new_text = f"Вы находитесь в разделе: Главное меню - Управление - <u>Напоминание</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"
        await bot.edit_message_text(
            new_text,
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id,
            reply_markup=self.markup
        )



    async def datesend_reminder(self):
        now = datetime.now()
        self.markup = self.generate_reminder_calendar(now.year, now.month)

        new_text = f"Вы находитесь в разделе: Главное меню - Управление - Напоминание - Создать напоминание - <u>Дата</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите дату:"
        await bot.edit_message_text(
            new_text,
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id,
            reply_markup=self.markup
        )

    async def timesend_reminder(self):
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
        await bot.edit_message_text(
            new_text,
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id,
            reply_markup=self.markup
        )

    async def description_reminder(self):
        new_text = (
            f"Вы находитесь в разделе: Главное меню - Управление - Напоминание - Создать напоминание - Дата - Время - <u>Текст напоминания</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nНапишите текст напоминания:"
        )
        await bot.edit_message_text(
            new_text,
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id
        )
        await bot.register_next_step_handler(self.call.message, self.get_description_reminder)

    async def get_description_reminder(self, message):
        self.call.data = f"remindersdscr_Описание_{message.text}"
        try:
            await bot.delete_message(chat_id=message.chat.id,
                                     message_id=message.message_id)
        except:
            pass

    async def select_user_send_reminder(self):
        buttons = [InlineKeyboardButton(key, callback_data=key) for key in
                   ["Отправка командам", "Отправка пользователям"]]
        self.markup = InlineKeyboardMarkup([buttons])
        self.markup.add(InlineKeyboardButton("Удалить напоминание", callback_data="Удалить напоминание"))
        new_text = f"Вы находитесь в разделе: Главное меню - Управление - Напоминание - Создать напоминание - Дата - Время - Текст напоминания - <u>Выбор получателей</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберете раздел:"
        await bot.edit_message_text(
            new_text,
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id,
            reply_markup=self.markup
        )


async def main():
    bot_instance = Main()
    await bot_instance.async_init()
    await bot.infinity_polling()


if __name__ == "__main__":
    asyncio.run(main())
