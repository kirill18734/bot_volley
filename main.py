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
        self.user_states = {}
        self.current_index = 0
        self.data = None
        self.send_serveys = None
        self.surveys = None
        self.user_data = {}
        self.unique_id = None
        self.keys = []
        self.hour = 2
        self.select_command = None
        self.markup = None
        self.call = None
        self.admin = None

    async def async_survey(self):
        await self.survey()

    async def async_init(self):
        await self.start_main()

    # отправка, закрытие, получение результатов опроса
    async def survey(self):
        while True:
            try:
                data = await self.load_data()
                for survey_id, survey_data in data['surveys'].items():
                    if survey_data.get('Получатели опроса'):
                        commands = str(survey_data.get('Получатели опроса')).replace("Админы", "admins").split(',')
                        users = [
                            str(user).replace("@", '').split('_')[-1]
                            for cmd in commands
                            for user in (data['admins'].values() if cmd == 'admins' else data['commands'][cmd][
                                "users"].values())
                        ]
                        if users:
                            target_date = datetime.strptime(
                                f"{survey_data.get('Дата отправки опроса')} {survey_data.get('Время отправки опроса')}",
                                "%d-%m-%Y %H:%M")

                            target_date2 = datetime.strptime(
                                f"{survey_data.get('Дата тренировки/игры')} {survey_data.get('Время тренировки/игры').split(' - ')[0]}",
                                "%d-%m-%Y %H:%M"
                            ) - timedelta(minutes=30)

                            day_index = days_week[target_date2.weekday()]
                            #
                            current_date = datetime.now().replace(second=0, microsecond=0)
                            #
                            #         # отправка опроса
                            if target_date == current_date and target_date2 >= current_date and survey_data.get(
                                    'Опрос отправлен') == 'Нет' and survey_data.get('Получатели опроса'):

                                question = f"{survey_data.get('Тип')} {survey_data.get('Дата тренировки/игры')} ({day_index}) c {survey_data.get('Время тренировки/игры').replace(' - ', ' до ')} стоймость {survey_data.get('Цена')}р .\nАдрес: {survey_data.get('Адрес')}"

                                # #     # Получение дня недели
                                options = ["Буду", "+1"]
                                for user in users:
                                    try:
                                        user_chat = user.split("_")[-1]
                                        poll_message = await bot.send_poll(
                                            chat_id=user_chat,
                                            question=question,
                                            options=options,
                                            close_date=target_date2,
                                            is_anonymous=False,  # Ответы будут видны боту
                                            allows_multiple_answers=False,
                                            explanation_parse_mode='HTML'
                                        )

                                        survey_data['Опрос отправлен'] = "Да"
                                        survey_data["Опрос открыт"] = "Да"
                                        survey_data['id опроса'] = poll_message.poll.id
                                        await self.write_data(data)

                                    except Exception as e:
                                        print(f"Ошибка при отправке опроса пользователю {user}: {e}")
                            #     # опрос автоматически закрывается, когда наступает время закрытие, то изменяем также значения
                            elif target_date2 <= current_date and 'Да' in (
                                    survey_data.get('Опрос открыт'), survey_data.get('Опрос отправлен')):
                                survey_data["Опрос открыт"] = "Нет"
                                await self.write_data(data)

            except:
                pass

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
                response_text = 'У вас нет доступа к данному боту'
                await bot.send_message(message.chat.id, response_text)
                try:
                    await bot.delete_message(message.chat.id, message.message_id)
                except:
                    pass
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

                                    if option_ids != 0:
                                        value["Отметились"][command][f'{user}({user_id})'] = option_ids
                                    else:
                                        # Если голос не был поставлен, удаляем пользователя из "Отметились"
                                        if f'{user}({user_id})' in value["Отметились"][command]:
                                            del value["Отметились"][command][f'{user}({user_id})']
                                    value['Количество отметившихся'] = len(
                                        set(user for command in value["Отметились"].keys()
                                            for user, val in value["Отметились"][command].items()
                                            if val != 0))
                                # Если в команде нет отметившихся пользователей, удаляем команду
                            if command in value["Отметились"] and not value["Отметились"][command]:
                                del value["Отметились"][command]

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
                "Новый опрос": self.typeplay,
                "save_send_survey": self.save,
                "Удалить опрос": self.del_survey,
                "cansel_survey": self.the_survey,
                "dell_survey": self.save_dell_survey,
                "Результаты опросов": self.result_surveys,
                "Редактировать опрос": self.edit_survey,
                "Напоминание": self.reminder
            }

            if self.admin is None:
                return
            elif self.call.data in ('Команды'):
                await self.selectsendsurvey()
            elif self.call.data not in ('Управление', 'Начать') and not self.state_stack:
                await self.show_start_menu(call.message)

            elif 'Начать' in [self.call.data] + list(self.state_stack.keys()):
                if not self.state_stack:
                    self.state_stack[self.call.data] = self.show_start_menu
                else:
                    self.keys.append(self.call.data)
                await self.navigate()
            else:

                if self.admin:
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
                    elif self.call.data == 'Пользователи':
                        await self.user_receipts_reminder()
                    elif self.call.data == 'cancel_send_survey':
                        if 'Новый опрос' not in list(self.state_stack.keys()) and 'Редактировать опрос' not in list(
                                self.state_stack.keys()):
                            await self.reminder()
                        else:
                            await self.the_survey()
                    elif self.call.data.startswith("edit_"):
                        _, function = str(self.call.data).split('_')
                        self.send_serveys = None
                        if function == 'newsurveysend':
                            self.send_serveys = function
                            function = 'newsurvey'
                        await getattr(self, function, None)()
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
                        elif list(self.state_stack.keys())[-1] in ('Новый опрос', 'Редактировать опрос'):
                            if user_key in self.selected_list:
                                self.selected_list.remove(user_key)  # Убираем из списка
                            else:
                                self.selected_list.add(user_key)  # Добавляем в список
                            await self.selectsendsurvey()
                        elif 'Новый опрос' not in list(self.state_stack.keys()) and 'Редактировать опрос' not in list(
                                self.state_stack.keys()) and 'Напоминание' not in list(
                                self.state_stack.keys()) :
                            if user_key in self.selected_list:
                                self.selected_list.remove(user_key)  # Убираем из списка
                            else:
                                self.selected_list.add(user_key)  # Добавляем в список
                            await self.selectsendsurvey()
                        elif list(self.state_stack.keys())[-1] == 'Напоминание':
                            if user_key in self.selected_list:
                                self.selected_list.remove(user_key)  # Убираем из списка
                            else:
                                self.selected_list.add(user_key)  # Добавляем в список
                            await self.user_receipts_reminder()
                    elif call.data in ("Товарищеская игра", "Тренировка", "Игра"):
                        if list(self.state_stack.keys())[-1] == 'Новый опрос':
                            self.unique_id = str(uuid.uuid4())  # Генерирует случайный UUID версии 4
                            if self.unique_id not in self.user_data:
                                self.user_data[self.unique_id] = {}  # Создаем запись для уникального ID
                            self.user_data[self.unique_id]['Тип'] = f"{call.data}"
                            if not self.state_stack:
                                self.state_stack[self.call.data] = self.typeplay
                            await self.newsurvey()
                        else:
                            self.call.data = 'Тип_' + self.call.data
                            await self.save_edit()
                    elif self.call.data == 'Создать напоминание':
                        self.unique_id = str(uuid.uuid4())  # Генерирует случайный UUID версии 4
                        self.user_data.clear()
                        if self.unique_id not in self.user_data:
                            self.user_data[self.unique_id] = {}  # Создаем запись для уникального ID
                        now = datetime.now()
                        await self.generate_calendar(now.year, now.month)
                    elif call.data.startswith("prev_") or call.data.startswith("next_"):
                        _, year, month = call.data.split("_")
                        if list(self.state_stack.keys())[-1] == 'Новый опрос':
                            await self.generate_calendar(int(year), int(month))
                        elif 'Новый опрос' not in list(self.state_stack.keys()) and 'Редактировать опрос' not in list(
                                self.state_stack.keys()):
                            await self.generate_calendar(int(year), int(month))
                        else:
                            if not self.send_serveys:
                                response_text = f"Вы находитесь в разделе: Главное меню - Управление - Редактировать опрос - <u>Изменить дату тренировки/игры</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите дату:"
                            else:
                                self.send_serveys = None
                                self.state_stack = dict(list(self.state_stack.items())[:3])
                                response_text = f"Вы находитесь в разделе: Главное меню - Управление - Редактировать опрос - <u>Изменить дату отправки опроса</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите дату:"
                            await self.generate_calendar(int(year), int(month), response_text=response_text)

                    elif call.data.startswith("prevsend_") or call.data.startswith("nextsend_"):
                        _, year, month = call.data.split("_")
                        await self.generate_calendar(int(year), int(month))

                    elif call.data.startswith("time_"):
                        _, time = call.data.split("_")
                        if list(self.state_stack.keys())[-1] == 'Новый опрос':
                            if 'Время тренировки/игры' not in (self.user_data[self.unique_id].keys()):
                                # Теперь можно безопасно записать дату
                                self.user_data[self.unique_id]['Время тренировки/игры'] = f"{time}"
                                await self.getaddress()
                            # Передаем дату в функцию (убрал .value(), так как строка не имеет такого метода)

                            elif 'Время отправки опроса' not in (self.user_data[self.unique_id].keys()):
                                # Теперь можно безопасно записать дату
                                self.user_data[self.unique_id]['Время отправки опроса'] = f"{time}"
                                await self.save_survey()
                        elif 'Новый опрос' not in list(self.state_stack.keys()) and 'Редактировать опрос' not in list(
                                self.state_stack.keys()):
                            self.user_data[self.unique_id]['Время отправки напоминания'] = f"{time}"
                            await self.getaddress()
                        else:
                            if not self.send_serveys:
                                self.call.data = f"Время тренировки/игры_{time}"
                            else:
                                self.call.data = f"Время отправки опроса_{time}"
                            await self.save_edit()
                    elif call.data.startswith("day_"):
                        _, year, month, day = call.data.split("_")
                        if list(self.state_stack.keys())[-1] == 'Новый опрос':
                            if 'Дата тренировки/игры' not in (self.user_data[self.unique_id].keys()):
                                # Теперь можно безопасно записать дату
                                self.user_data[self.unique_id][
                                    'Дата тренировки/игры'] = f"{int(day):02d}-{int(month):02d}-{year}"
                                await self.generatetime()
                            elif 'Дата отправки опроса' not in (self.user_data[self.unique_id].keys()):
                                self.user_data[self.unique_id][
                                    'Дата отправки опроса'] = f"{int(day):02d}-{int(month):02d}-{year}"
                                await self.timesendsurvey()
                        elif 'Новый опрос' not in list(self.state_stack.keys()) and 'Редактировать опрос' not in list(
                                self.state_stack.keys()):
                            self.user_data[self.unique_id][
                                'Дата отправки напоминания'] = f"{int(day):02d}-{int(month):02d}-{year}"
                            await self.timesendsurvey()
                        else:
                            if not self.send_serveys:
                                self.call.data = f"Дата тренировки/игры_{int(day):02d}-{int(month):02d}-{year}"
                            else:
                                self.call.data = f"Дата отправки опроса_{int(day):02d}-{int(month):02d}-{year}"
                            await self.save_edit()
                        # Передаем дату в функцию (убрал .value(), так как строка не имеет такого метода)

                    elif call.data == 'select_send_command':
                        if list(self.state_stack.keys())[-1] == 'Новый опрос':
                            # Теперь можно безопасно записать дату
                            self.user_data[self.unique_id]['Получатели опроса'] = ','.join(self.selected_list)
                            # Передаем дату в функцию (убрал .value(), так как строка не имеет такого метода)
                            await self.select_date_send_survey()
                        elif 'Новый опрос' not in list(self.state_stack.keys()) and 'Редактировать опрос' not in list(
                                self.state_stack.keys()):
                            self.user_data[self.unique_id]['Получатели напоминания'] = ','.join(self.selected_list)
                            await self.save_survey()
                        else:
                            self.call.data = f'Получатели опроса_{self.selected_list}'
                            await self.save_edit()

                    elif call.data == "back_hours":
                        # Переход назад (цикл через 2 -> 2.5 -> 3)
                        if self.hour == 2:
                            self.hour = 3
                        elif self.hour == 3:
                            self.hour = 2.5
                        elif self.hour == 2.5:
                            self.hour = 2
                        await self.generatetime()
                    elif call.data == "up_hour":
                        # Переход назад (цикл через 2 -> 2.5 -> 3)
                        if self.hour == 2:
                            self.hour = 2.5
                        elif self.hour == 2.5:
                            self.hour = 3
                        elif self.hour == 3:
                            self.hour = 2
                        await self.generatetime()

                    elif call.data.startswith("price_"):
                        _, price = call.data.split("_")
                        if list(self.state_stack.keys())[-1] == 'Новый опрос':
                            self.user_data[self.unique_id]['Цена'] = f"{price}"
                            await self.selectsendsurvey()
                        else:
                            self.call.data = f"Цена_{price}"
                            await self.save_edit()
                    elif self.call.data == "nextdell" and self.current_index < len(self.surveys) - 1:
                        self.current_index += 1
                        await self.del_survey()
                    elif self.call.data == "prevdell" and self.current_index > 0:
                        self.current_index -= 1
                        await self.del_survey()
                    elif self.call.data == "mainnextedit" and self.current_index < len(self.surveys) - 1:
                        self.current_index += 1

                        if list(self.state_stack.keys())[-1] not in ('Результаты опросов', 'Напоминание'):
                            await self.edit_survey()
                        elif list(self.state_stack.keys())[-1] == 'Напоминание':
                            await self.user_receipts_reminder()
                        else:
                            await self.result_surveys()
                    elif self.call.data == "mainprevedit" and self.current_index > 0:
                        self.current_index -= 1

                        if list(self.state_stack.keys())[-1] not in ('Результаты опросов', 'Напоминание'):
                            await self.edit_survey()
                        elif list(self.state_stack.keys())[-1] == 'Напоминание':
                            await self.user_receipts_reminder()
                        else:
                            await self.result_surveys()
                else:
                    await self.show_start_menu(call.message)

    async def edit_message(self, response_text, buttons=None, buttons_row=4):
        self.markup = InlineKeyboardMarkup()

        if not response_text:
            print('Неверно указан текст')
            return
        if buttons:
            await self.process_buttons(buttons, buttons_row)

        await bot.edit_message_text(
            chat_id=self.call.message.chat.id,
            message_id=self.call.message.message_id,
            text=response_text,
            reply_markup=self.markup,
            parse_mode="HTML"
        )

    async def process_buttons(self, buttons, buttons_row):
        """ Обработка как словарей (вложенных), так и списков списков кнопок """

        # ✅ Если это список списков (как row_date в календаре)
        if isinstance(buttons, list):
            for item in buttons:
                if isinstance(item, list):  # список кнопок в строке
                    self.markup.row(*item)
                elif isinstance(item, InlineKeyboardButton):  # одиночная кнопка в отдельной строке
                    self.markup.row(item)
            return

        # ✅ Если это словарь — обрабатываем вложенность
        row = []

        for key, value in buttons.items():
            if isinstance(value, dict):
                if row:
                    self.markup.add(*row)
                    row = []
                await self.process_buttons(value, buttons_row)
                continue

            if 'http' not in value:
                row.append(InlineKeyboardButton(key, callback_data=value))
            else:
                row.append(InlineKeyboardButton(key, url=value))

            if len(row) == buttons_row:
                self.markup.add(*row)
                row = []

        if row:
            self.markup.add(*row)

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

            if users:
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
            await self.edit_message(response_text, buttons=add, buttons_row=1)
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
        if not users:
            response_text = f'Пользователи отсутствуют'
            await bot.answer_callback_query(self.call.id, response_text,
                                            show_alert=True)
            try:
                await self.close_control()
            except:
                pass
            return
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
        await self.edit_message(response_text, buttons=add)

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
                self.state_stack = dict(list(self.state_stack.items())[:-1])
                # Сохраняем обновленные данные обратно в файл
                await self.write_data(data)  # Передаем измененные данные в функцию сохранения

                response_text = 'Пользователи удалены' if len(self.selected_list) > 1 else 'Пользователь удален'
                await bot.answer_callback_query(self.call.id, response_text,
                                                show_alert=True)
                await self.close_control()
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

        add['Закрыть'] = {'Отмена!': 'cancel_dell_video', "💾 Сохранить!": 'save_dell_video'}

        response_text = f"Вы находитесь в разделе: Главное меню - Управление -  Редактирование команд - {self.select_command} - Редактировать видео - <u>Удалить видео</u> .\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"
        await self.edit_message(response_text, buttons=add)

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

        add['Закрыть'] = {'Отмена!': 'cancel_dell_stat', '💾 Сохранить!': 'save_dell_stat'}

        response_text = f"Вы находитесь в разделе: Главное меню - Управление -  Редактирование команд - {self.select_command} - Редактировать статистику - <u>Удалить статистику</u> .\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"

        await self.edit_message(response_text, buttons=add)

    async def the_survey(self):
        buttons_name = ["Новый опрос", "Удалить опрос", "Редактировать опрос", "Результаты опросов"]
        buttons = {name: name for name in buttons_name}
        response_text = f"Вы находитесь в разделе: Главное меню - Управление - <u>Опрос</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"
        await self.edit_message(response_text, buttons)

    async def typeplay(self):
        buttons_name = ["Игра", "Тренировка", "Товарищеская игра"]
        buttons = {name: name for name in buttons_name}
        if list(self.state_stack.keys())[-1] == 'Новый опрос':
            response_text = f"Вы находитесь в разделе: Главное меню - Управление - Опрос - <u>Новый опрос</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"
        else:
            self.state_stack = dict(list(self.state_stack.items())[:3])
            response_text = f"Вы находитесь в разделе: Главное меню - Управление - Редактировать опрос - <u>Изменить тип</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"
        await self.edit_message(response_text, buttons)

    async def generate_calendar(self, year, month, response_text=None):
        if not response_text and list(self.state_stack.keys())[-1] == 'Новый опрос':
            text_responce = "\n".join(
                f"{k}: {v}" for game_data in self.user_data.values() for k, v in game_data.items())
            response_text = f"Вы находитесь в разделе: Главное меню - Управление - Новый опрос - {self.user_data[self.unique_id]['Тип']} - <u>Дата</u>.\n\n{text_responce}.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите дату игры/тренировки:"
        elif 'Новый опрос' not in self.state_stack and 'Редактировать опрос' not in self.state_stack:
            response_text = (
                "Вы находитесь в разделе: Главное меню - Управление - Напоминание - Создать напоминание - "
                "<u>Дата</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. "
                "В начало /start \n\nВыберите дату:"
            )

        cal = calendar.monthcalendar(year, month)

        buttons = []

        # Заголовок: Апрель 2025
        buttons.append([InlineKeyboardButton(f"{tmonth_names[month]} {year}", callback_data="ignore")])

        # Дни недели
        buttons.append(
            [InlineKeyboardButton(day, callback_data="ignore") for day in ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]])

        # Дни месяца
        for week in cal:
            week_buttons = []
            for day in week:
                if day == 0:
                    week_buttons.append(InlineKeyboardButton(" ", callback_data="ignore"))
                else:
                    week_buttons.append(
                        InlineKeyboardButton(str(day), callback_data=f"day_{year}_{month:02d}_{day:02d}")
                    )
            buttons.append(week_buttons)

        # Переключатели месяцев
        prev_month, prev_year = (month - 1, year) if month > 1 else (12, year - 1)
        next_month, next_year = (month + 1, year) if month < 12 else (1, year + 1)
        buttons.append([
            InlineKeyboardButton("<", callback_data=f"prev_{prev_year}_{prev_month}"),
            InlineKeyboardButton(">", callback_data=f"next_{next_year}_{next_month}")
        ])

        # Рендерим через edit_message, который теперь умеет обрабатывать список списков
        await self.edit_message(response_text, buttons=buttons)

    async def newsurvey(self):
        if list(self.state_stack.keys())[-1] == 'Новый опрос':
            text_responce = "\n".join(
                f"{k}: {v}" for game_data in self.user_data.values() for k, v in game_data.items())
            response_text = f"Вы находитесь в разделе: Главное меню - Управление - Новый опрос - {self.user_data[self.unique_id]['Тип']} - <u>Дата</u>.\n\n{text_responce}.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите дату игры/тренировки:"
        elif self.call.data != 'edit_newsurveysend':
            self.state_stack = dict(list(self.state_stack.items())[:3])
            response_text = f"Вы находитесь в разделе: Главное меню - Управление - Редактировать опрос - <u>Изменить дату тренировки/игры</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите дату:"
        else:
            self.state_stack = dict(list(self.state_stack.items())[:3])
            response_text = f"Вы находитесь в разделе: Главное меню - Управление - Редактировать опрос - <u>Изменить дату отправки опроса</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите дату:"

        now = datetime.now()
        await self.generate_calendar(now.year, now.month, response_text)

    async def generatetime(self):
        self.send_serveys = None
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
        if list(self.state_stack.keys())[-1] == 'Новый опрос':
            text_responce = "\n".join(
                f"{k}: {v}" for game_data in self.user_data.values() for k, v in game_data.items())
            response_text = f"Вы находитесь в разделе: Главное меню - Управление - Новый опрос - {self.user_data[self.unique_id]['Тип']} - Дата -  <u>Время</u>\n\n{text_responce}.\n\nИспользуйте кнопки для навигации. Чтобы вернуться на шаг назад, используйте команду /back. В начало /start \n\nВыберите время (интервал - {text}) игры/тренировки:"
        else:
            self.state_stack = dict(list(self.state_stack.items())[:3])
            response_text = f"Вы находитесь в разделе: Главное меню - Управление - Редактировать опрос - <u>Изменить время тренировки/игры</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите время (интервал - {text}) игры/тренировки:"

        buttons = []
        for i in range(0, len(times), 4):
            buttons.append(
                [InlineKeyboardButton(time,
                                      callback_data=f"time_{time}")
                 for
                 time in
                 times[i:i + 4]])
        buttons.append([
            InlineKeyboardButton("<", callback_data=f"back_hours"),
            InlineKeyboardButton(">", callback_data=f"up_hour")
        ])

        await self.edit_message(response_text, buttons=buttons)

    async def getaddress(self):
        text_responce = "\n".join(
            f"{k}: {v}" for game_data in self.user_data.values() for k, v in game_data.items())
        if list(self.state_stack.keys())[-1] == 'Новый опрос':
            response_text = f"Вы находитесь в разделе: Главное меню - Управление - Новый опрос - {self.user_data[self.unique_id]['Тип']} - Дата - Время - <u>Адрес</u>\n\n{text_responce}.\n\nИспользуйте кнопки для навигации. Чтобы вернуться на шаг назад, используйте команду /back. В начало /start \n\nНапишите адрес:"
        elif 'Новый опрос' not in list(self.state_stack.keys()) and 'Редактировать опрос' not in list(
                self.state_stack.keys()):
            response_text = f"Вы находитесь в разделе: Главное меню - Управление - Напоминание - Создать напоминание - Дата - Время - <u>Текст напоминания</u>\n\n{text_responce}.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nНапишите текст напоминания:"
        else:
            self.state_stack = dict(list(self.state_stack.items())[:3])
            response_text = f"Вы находитесь в разделе: Главное меню - Управление - Редактировать опрос - <u>Изменить адрес</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nНапишите адрес:"
        self.user_states[self.call.message.chat.id] = "add_address"
        await self.edit_message(response_text)

    async def get_adress_text(self, message):
        if message.text not in ['/back',
                                '/start']:
            try:
                await bot.delete_message(chat_id=message.chat.id,
                                         message_id=message.message_id)
            except:
                pass

            if list(self.state_stack.keys())[-1] == 'Новый опрос':
                self.user_data[self.unique_id]['Адрес'] = message.text
                await self.getprice()

            elif 'Новый опрос' not in list(self.state_stack.keys()) and 'Редактировать опрос' not in list(
                    self.state_stack.keys()):
                self.user_data[self.unique_id]['Текст напоминания'] = message.text
                await self.receipts_reminder()
            else:
                self.call.data = f"Адрес_{message.text}"
                await self.save_edit()
        else:
            if message.message_id:
                try:
                    await bot.delete_message(chat_id=message.chat.id,
                                             message_id=message.message_id)
                except:
                    pass
            self.state_stack = dict(list(self.state_stack.items())[:-1])
            await self.state_stack[list(self.state_stack.keys())[-1]]()

    async def getprice(self):
        prices = [x for x in range(300, 1501, 50)]
        if list(self.state_stack.keys())[-1] == 'Новый опрос':
            text_responce = "\n".join(
                f"{k}: {v}" for game_data in self.user_data.values() for k, v in game_data.items())
            response_text = f"Вы находитесь в разделе: Главное меню - Управление - Новый опрос - {self.user_data[self.unique_id]['Тип']} - Дата - Время - Адрес - <u>Цена</u>\n\n{text_responce}.\n\nИспользуйте кнопки для навигации. Чтобы вернуться на шаг назад, используйте команду /back. В начало /start\n\nВыберите цену игры/тренировки:"
        else:
            self.state_stack = dict(list(self.state_stack.items())[:3])
            response_text = f"Вы находитесь в разделе: Главное меню - Управление - Редактировать опрос - <u>Изменить цену</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберете цену тренировки/игры:"

        buttons = [
            [InlineKeyboardButton(str(price), callback_data=f"price_{price}") for price in prices]
        ]

        await self.edit_message(response_text, buttons=buttons)

    async def selectsendsurvey(self):

        text_responce = "\n".join(f"{k}: {v}" for game_data in self.user_data.values() for k, v in game_data.items())
        data = await self.load_data()
        users = {name: name for name in data["commands"].keys()}
        users['Админы'] = 'Админы'

        # Создание кнопок
        buttons = {f"{'✅' if value in self.selected_list else '❌'} {key}": f"toggle_{value}" for key, value in
                   users.items()}
        if list(self.state_stack.keys())[-1] == 'Новый опрос':

            response_text = f"Вы находитесь в разделе: Главное меню - Управление - Новый опрос - {self.user_data[self.unique_id]['Тип']} - Дата - Время - Адрес - Цена - <u>Получатели опроса</u>\n\n{text_responce}.\n\nИспользуйте кнопки для навигации. Чтобы вернуться на шаг назад, используйте команду /back. В начало /start\n\nВыберите команду для опроса:"
            buttons['end'] = {"Дальше": f"select_send_command"}

        elif 'Новый опрос' not in list(self.state_stack.keys()) and 'Редактировать опрос' not in list(
                self.state_stack.keys()):
            response_text = f"Вы находитесь в разделе: Главное меню - Управление - Напоминание - Создать напоминание - Дата - Время - Текст напоминания - <u>Получатели</u>\n\n{text_responce}.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберете получателей:"
            buttons['end'] = {"Сохранить": "select_send_command"}
        else:
            self.state_stack = dict(list(self.state_stack.items())[:3])
            response_text = f"Вы находитесь в разделе: Главное меню - Управление - Редактировать опрос - <u>Изменить получателей</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберете команды:"
            buttons['end'] = {"Сохранить": "select_send_command"}
        await self.edit_message(response_text, buttons=buttons)

    async def select_date_send_survey(self):
        text_responce = "\n".join(f"{k}: {v}" for game_data in self.user_data.values() for k, v in game_data.items())
        response_text = f"Вы находитесь в разделе: Главное меню - Управление - Новый опрос - {self.user_data[self.unique_id]['Тип']} - Дата - Время - Адрес - Цена - Выбор команды для опроса - <u>Дата отправки опроса</u>\n\n{text_responce}.\n\nИспользуйте кнопки для навигации. Чтобы вернуться на шаг назад, используйте команду /back. В начало /start\n\nВыберите дату отправки опроса:"
        now = datetime.now()
        await self.generate_calendar(now.year, now.month, response_text)

    async def timesendsurvey(self):
        self.send_serveys = self.call.data
        time = [f"{hour:02}:{minute:02}" for hour in range(9, 24) for minute in [0, 30]]
        text_responce = "\n".join(f"{k}: {v}" for game_data in self.user_data.values() for k, v in game_data.items())
        buttons = [[InlineKeyboardButton(key, callback_data=f"time_{key}") for key in time]]
        # Разбиваем список кнопок на подсписки по 5 элементов
        if list(self.state_stack.keys())[-1] == 'Новый опрос':
            response_text = f"Вы находитесь в разделе: Главное меню - Управление - Новый опрос - {self.user_data[self.unique_id]['Тип']} - Дата - Время - Адрес - Цена - Выбор команды для опроса - Дата отправки опроса - <u>Время отправки опроса</u>\n\n{text_responce}.\n\nИспользуйте кнопки для навигации. Чтобы вернуться на шаг назад, используйте команду /back. В начало /start\n\nВыберите время отправки опроса:"
        elif 'Новый опрос' not in list(self.state_stack.keys()) and 'Редактировать опрос' not in list(
                self.state_stack.keys()):
            response_text = f"Вы находитесь в разделе: Главное меню - Управление - Напоминание - Создать напоминание - Дата - <u>Время</u>\n\n{text_responce}.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите время:"
        else:
            self.state_stack = dict(list(self.state_stack.items())[:3])
            response_text = "Вы находитесь в разделе: Главное меню - Управление - Редактировать опрос - <u>Изменить время отправки опроса</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите время:"
        await self.edit_message(response_text, buttons=buttons)

    async def save_survey(self):
        text_responce = "\n".join(f"{k}: {v}" for game_data in self.user_data.values() for k, v in game_data.items())
        if 'Новый опрос' in list(self.state_stack.keys()):
            buttons = {"Отмена": "cancel_send_survey", "Запланировать опрос": "save_send_survey"}

            response_text = (
                f"Вы находитесь в разделе: Главное меню - Управление - Новый опрос - {self.user_data[self.unique_id]['Тип']} - Дата - Время - Адрес - Цена - Выбор команды для опроса - Дата отправки опроса - Время отправки опроса - <u>Сохранение опроса</u>\n\n{text_responce}.\n\nИспользуйте кнопки для навигации. Чтобы вернуться на шаг назад, используйте команду /back. В начало /start\n\nПроверьте подготовленный опрос и выберете раздел")
        else:
            response_text = (
                f"Вы находитесь в разделе: Главное меню - Управление - Напоминание - Создать напоминание - Дата - Время - Текст напоминания - Получатели - <u>Сохранение напоминания</u>\n\n{text_responce}.\n\nИспользуйте кнопки для навигации. Чтобы вернуться на шаг назад, используйте команду /back. В начало /start\n\nПроверьте подготовленное напоминание и выберете раздел")

            buttons = {"Отмена": "cancel_send_survey", "Запланировать напоминание": "save_send_survey"}
        await self.edit_message(response_text, buttons=buttons)

    async def save(self):
        data = await self.load_data()
        if 'Новый опрос' in list(self.state_stack.keys()):
            self.user_data[self.unique_id]['Опрос открыт'] = "Нет"
            self.user_data[self.unique_id]['Опрос отправлен'] = "Нет"
            self.user_data[self.unique_id]['Отметились'] = {}
            self.user_data[self.unique_id]['Количество отметившихся'] = 0
            self.user_data[self.unique_id]['id опроса'] = 0

            if "surveys" not in data:
                data["surveys"] = {}
                # Добавляем данные правильно (без .values())
            data["surveys"][self.unique_id] = self.user_data[self.unique_id]
            response_text = 'Задание запланировано'
        else:
            self.user_data[self.unique_id]['Напоминание отправлено'] = "Нет"
            if "surveys" not in data:
                data["reminder"] = {}
            data["reminder"][self.unique_id] = self.user_data[self.unique_id]
            response_text = 'Напоминание запланировано'
        # Проверяем, есть ли "surveys" в config, если нет - создаем пустой словарь

        # Сохраняем обновленные данные обратно в файл
        await self.write_data(data)

        await bot.answer_callback_query(self.call.id, response_text, show_alert=True)

        # Очищаем временные данные
        self.user_data.clear()
        self.selected_list.clear()
        if 'Новый опрос' in list(self.state_stack.keys()):
            self.state_stack = dict(list(self.state_stack.items())[:-2])
            await self.state_stack[list(self.state_stack.keys())[-1]]()
        else:
            self.state_stack = dict(list(self.state_stack.items())[:-1])
            await self.state_stack[list(self.state_stack.keys())[-1]]()

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
        response_text = f"Вы находитесь в разделе: Главное меню - Управление - <u>Удалить опрос</u>.\n\n"

        response_text += f"<b>Опрос {self.current_index + 1} из {len(self.surveys)}</b>\n\n"
        response_text += "\n".join(f"{k}: {v}" for k, v in survey_data.items() if k not in (
            'Опрос открыт', 'Опрос отправлен', 'Отметились', 'Количество отметившихся', 'id опроса'))
        response_text += '\n\nИспользуйте кнопки для навигации. Чтобы вернуться на шаг назад, используйте команду /back. В начало /start\n\nВыбирете опрос для удаления:'
        add = {
            "<": "prevdell" if self.current_index > 0 else None,
            ">": "nextdell" if self.current_index < len(self.surveys) - 1 else None
        }

        # Убираем ключи с значением None
        add = {key: value for key, value in add.items() if value is not None}

        add['end'] = {"Отмена": "cansel_survey", "Удалить опрос": "dell_survey"}

        await self.edit_message(response_text, buttons=add, buttons_row=2)

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
        response_text = f"Вы находитесь в разделе: Главное меню - Управление - <u>Редактировать опрос</u>.\n\n"

        response_text += f"<b>Опрос {self.current_index + 1} из {len(self.surveys)}</b>\n\n"
        response_text += "\n".join(f"{k}: {v}" for k, v in survey_data.items() if k not in (
            'Отметились', 'Количество отметившихся', 'id опроса', 'Опрос отправлен', 'Опрос открыт'))
        response_text += ('\n\nИспользуйте кнопки для навигации. Чтобы вернуться на шаг назад, '
                          'используйте команду /back. В начало /start\n\nВыберите раздел:')

        add = {
            "<": "mainprevedit" if self.current_index > 0 else None,
            ">": "mainnextedit" if self.current_index < len(self.surveys) - 1 else None
        }

        # Убираем ключи с значением None
        add = {key: value for key, value in add.items() if value is not None}

        add['edit'] = {
            "Изменить тип": "edit_typeplay",
            "Изменить дату тренировки/игры": "edit_newsurvey",
            "Изменить время тренировки/игры": "edit_generatetime",
            "Изменить адрес": "edit_getaddress",
            "Изменить цену": "edit_getprice",
            "Изменить получателей": "edit_selectsendsurvey",
            "Изменить дату отправки опроса": "edit_newsurveysend",
            "Изменить время отправки опроса": "edit_timesendsurvey",
        }

        await self.edit_message(response_text, buttons=add, buttons_row=3)

    async def save_edit(self):
        data = await self.load_data()
        key_del = self.surveys[self.current_index][0]
        new_value = self.call.data.split("_")

        if new_value[0] != 'Получатели опроса':
            data["surveys"][key_del][new_value[0]] = new_value[-1]
        else:
            data["surveys"][key_del][new_value[0]] = ', '.join(self.selected_list)

        await self.write_data(data)  # Передаем измененные данные в функцию сохранения
        response_text = (
            f'{new_value[0]} изменен' if new_value[0] in ("Тип", "Адрес") else
            f'{new_value[0]} изменена' if new_value[0] in ("Дата тренировки/игры", "Цена") else
            f'{new_value[0]} изменены' if new_value[0] == "Получатели опроса" else
            f'{new_value[0]} изменено'
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
        response_text = f"Вы находитесь в разделе: Главное меню - Управление - <u>Результаты опросов</u>.\n\n"

        response_text += f"<b>Опрос {self.current_index + 1} из {len(self.surveys)}</b>\n\n"
        response_text += "\n".join(f"{k}: {v}" for k, v in survey_data.items() if k not in ('id опроса', 'Отметились'))
        # Генерация текста
        response_text += "\nОтметились:\n" + await self.format_dict(survey_data["Отметились"], base_indent=4)
        response_text += ('\n\nИспользуйте кнопки для навигации. Чтобы вернуться на шаг назад, '
                          'используйте команду /back. В начало /start\n\nВыберите опрос для удаления:')

        add = {
            "<": "mainprevedit" if self.current_index > 0 else None,
            ">": "mainnextedit" if self.current_index < len(self.surveys) - 1 else None
        }

        # Убираем ключи с значением None
        add = {key: value for key, value in add.items() if value is not None}

        await self.edit_message(response_text, buttons=add)

    async def reminder(self):
        buttons_name = ["Создать напоминание", "Редактировать напоминание", "Результаты напоминаний"]
        buttons = {name: name for name in buttons_name}
        response_text = f"Вы находитесь в разделе: Главное меню - Управление - <u>Напоминание</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"
        await self.edit_message(response_text, buttons)

    async def receipts_reminder(self):
        text_responce = "\n".join(f"{k}: {v}" for game_data in self.user_data.values() for k, v in game_data.items())
        buttons_name = ["Команды", "Пользователи"]
        buttons = {name: name for name in buttons_name}
        response_text = f"Вы находитесь в разделе: Главное меню - Управление - Напоминание - Создать напоминание - Дата - Время - Текст напоминания - <u>Получатели</u>\n\n{text_responce}.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберете получателей:"
        await self.edit_message(response_text, buttons)

    async def user_receipts_reminder(self):
        data = await self.load_data()
        self.surveys = [command for command in data["commands"].keys() if data["commands"][command]['users']] + [
            'Админы']  # Преобразуем в список для удобства доступа по индексу
        users = self.surveys[self.current_index]

        # Инициализация "Получатели напоминания" если его еще нет
        if 'Получатели напоминания' not in self.user_data[self.unique_id]:
            self.user_data[self.unique_id]['Получатели напоминания'] = {}

        # Инициализация получателей напоминаний, если еще не существует
        if users not in self.user_data[self.unique_id]['Получатели напоминания']:
            self.user_data[self.unique_id]['Получатели напоминания'][users] = {}

        # Удаляем пользователей, которых больше нет в списке
        users_to_remove = [user for user in self.user_data[self.unique_id]['Получатели напоминания'][users] if
                           user not in self.selected_list]
        for user in users_to_remove:
            del self.user_data[self.unique_id]['Получатели напоминания'][users][user]

        # Добавляем выбранных пользователей в список получателей напоминаний
        for user in self.selected_list:
            if users != 'Админы':
                for key, value in data["commands"][users]["users"].items():
                    if user == value:
                        self.user_data[self.unique_id]['Получатели напоминания'][users][str(key)] = str(
                            value.split('_')[-1])
            else:
                for key, value in data["admins"].items():
                    if user == value:
                        self.user_data[self.unique_id]['Получатели напоминания'][users][str(key)] = str(
                            value.split('_')[-1])

        # Проверяем, если в команде нет пользователей, удаляем команду из "Получатели напоминания"
        if not self.user_data[self.unique_id]['Получатели напоминания'][users]:
            del self.user_data[self.unique_id]['Получатели напоминания'][users]

        # Формируем ответ
        text_responce = "\n".join(
            f"{k}: {v}"
            for game_data in self.user_data.values()
            for k, v in game_data.items()
            if k != 'Получатели напоминания'
        )
        text_responce += '\nПолучатели напоминания:\n' + await self.format_dict(
            self.user_data[self.unique_id]['Получатели напоминания'], base_indent=4)
        response_text = f"Вы находитесь в разделе: Главное меню - Управление - Напоминание - Создать напоминание - Дата - Время - Текст напоминания - <u>Получатели</u>\n\n{text_responce}\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nКоманда: {users} \n\nВыберите получателей:"

        # Формирование кнопок для получателей на основе команды
        if users != 'Админы':
            buttons = {f"{'✅' if value in self.selected_list else '❌'} {key}": f"toggle_{value}"
                       for key, value in data["commands"][users]["users"].items()}
        else:
            buttons = {f"{'✅' if value in self.selected_list else '❌'} {key}": f"toggle_{value}"
                       for key, value in data["admins"].items()}

        # Кнопки навигации для перехода между командами
        buttons['end'] = {
            "<": "mainprevedit" if self.current_index > 0 else None,
            ">": "mainnextedit" if self.current_index < len(self.surveys) - 1 else None
        }

        # Убираем ключи с значением None
        buttons['end'] = {key: value for key, value in buttons['end'].items() if value is not None}
        buttons['Закрыть'] = {'Отмена!': 'cancel_send_survey', '💾 Сохранить!': 'save_send_survey'}
        # Отправка сообщения с кнопками
        await self.edit_message(response_text, buttons=buttons)


async def main():
    bot_instance = Main()

    # Запускаем async_survey в отдельной задаче
    survey_task = asyncio.create_task(bot_instance.async_survey())
    # Ждём завершения async_init
    await bot_instance.async_init()
    # Ожидаем завершения опроса бота
    await bot.infinity_polling()
    # Опционально: дожидаемся завершения survey_task
    await survey_task


if __name__ == "__main__":
    asyncio.run(main())
