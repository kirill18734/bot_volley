import json
from telebot.async_telebot import AsyncTeleBot
from telebot import types
from telebot.types import BotCommand, InlineKeyboardMarkup, InlineKeyboardButton
import calendar
import uuid
from datetime import datetime, timedelta
import asyncio
from config.config import config
from core.AuthService import access
from core.storage import storage
from services.send_reminder import send_reminder
from services.send_survey import send_survey

bot = AsyncTeleBot(config.BOT_TOKEN, parse_mode='HTML')


class Main:
    def __init__(self):
        self.state_stack = {}  # Стек для хранения состояний
        self.selected_list = set()
        self.user_states = {}
        self.current_index = 0
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

    async def block_control(self, message):
        try:
            response_text = 'У вас нет доступа к данному боту'
            await bot.send_message(message.chat.id, response_text)
            try:
                await bot.delete_message(message.chat.id, message.message_id)
            except:
                pass
        except:
            pass

    async def async_init(self):
        await self.start_main()

    async def history(self):
        response_text = ' - '.join(list(self.state_stack.keys())[:-1]) + ' - <u>' + list(self.state_stack.keys())[
            -1] + '</u>' if self.state_stack else ''
        return f"Вы находитесь в разделе: {response_text}\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"

    async def delete_message(self, message):
        if message.message_id:
            try:
                await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
            except:
                pass

    async def back_history(self, message):
        while self.state_stack:
            if len(self.state_stack.keys()) != 1:
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
                await self.show_start_menu(message)
                break
        else:
            await self.show_start_menu(message)

    async def start_main(self):
        await bot.set_my_commands([BotCommand("start", "В начало"), BotCommand("back", "Назад")])

        @bot.poll_answer_handler(func=lambda answer: True)
        async def handle_poll_answer(answer):
            user_id = answer.user.id
            poll_id = answer.poll_id
            option_ids = 0 if not answer.option_ids else '+1' if answer.option_ids[0] == 1 else 'Буду'

            data = await storage.load_data()
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

                        await storage.write_data(data)

        @bot.message_handler(commands=['start'])
        async def handle_start(message):
            await self.delete_message(message)
            self.admin = await access.check_access(message)
            if not self.admin['has_access']:
                await self.block_control(message)
                return
            await self.show_start_menu(message)

        @bot.message_handler(commands=['back'])
        async def handle_back(message):
            await self.delete_message(message)
            self.admin = await access.check_access(message)
            if not self.admin['has_access']:
                await self.block_control(message)
                return
            elif 'Начать' in self.state_stack.keys() and self.keys:
                self.keys.pop()
                await self.navigate()
                return
            await self.back_history(message)

        @bot.message_handler(
            func=lambda message: self.user_states.get(message.chat.id) in ("add"))
        async def get_description_reminder(message):
            self.select_command = str(self.select_command).replace('Админы', 'admins')
            if self.user_states.get(message.chat.id) == 'add':
                await self.add_list(message)
            self.user_states.clear()

        @bot.callback_query_handler(func=lambda call: True)
        async def handle_query(call):
            self.admin = await access.check_access(call.message)
            self.call = call
            if not self.admin['has_access']:
                await self.block_control(call.message)
                return
            if 'Главное меню' not in list(self.state_stack.keys()):
                await self.show_start_menu(call.message)
                return

            data = await storage.load_data()

            # Добавляем команды из data["commands"] и "Админы", все указывают на self.open
            extra_actions = {name: self.distribution_center for name in list(data["commands"].keys()) + ['Админы']}
            actions = {
                "Управление": self.control_buttons,
                "Доступ к боту": self.main_control,
                "Открыть доступ": self.open_control,
                "Закрыть доступ": self.close_control,
                "Редактирование команд": self.edit_command,
                "Редактировать видео": self.edit_video,
                "Редактировать статистику": self.edit_statistic,
                "Добавить видео": self.edit_commands,
                "Удалить видео": self.edit_commands,
                "Добавить статистику": self.edit_commands,
                "Удалить статистику": self.edit_commands,
                "dell_data": self.dell_list,
                "Опрос": self.the_survey,
                "Новый опрос": self.typeplay,
                "Удалить опрос": self.del_survey,
                "cansel_survey": self.the_survey,
                "dell_survey": self.save_dell_survey,
                "Результаты опросов": self.result_surveys,
                "Редактировать опрос": self.edit_survey,
                "Напоминание": self.reminder,
                "Редактировать напоминание": self.edit_survey
            }
            # Объединяем словари
            actions = {**actions, **extra_actions}

            if self.call.data == 'Команды':
                await self.selectsendsurvey()
            elif self.call.data == 'cancellation':
                self.selected_list.clear()
                await self.back_history(call.message)
            elif 'Начать' in [self.call.data] + list(self.state_stack.keys()):
                if 'Начать' not in list(self.state_stack.keys()):
                    self.state_stack[self.call.data] = self.navigate
                else:
                    self.keys.append(self.call.data)
                await self.navigate()

            elif self.admin['is_admin']:
                if self.call.data in (actions.keys()):
                    self.state_stack[self.call.data] = actions[self.call.data]
                    await actions[self.call.data]()

                elif self.call.data.startswith("cal_"):
                    date_str = self.call.data[4:]  # Убираем "cal_"
                    await bot.send_message(self.call.message.chat.id, f"Вы выбрали {date_str}",
                                           reply_markup=types.ReplyKeyboardRemove())
                elif self.call.data == 'Пользователи':
                    await self.user_receipts_reminder()
                elif self.call.data.startswith("edit_"):
                    _, function = str(self.call.data).split('_', 1)
                    self.send_serveys = None
                    if function == 'newsurveysend':
                        self.send_serveys = function
                        function = 'newsurvey'
                    await getattr(self, function, None)()
                elif self.call.data.startswith("toggle_"):
                    user_key = '_'.join(self.call.data.split("_")[1:])  # Извлекаем имя пользователя
                    if list(self.state_stack.keys())[-2] in ('Закрыть доступ', 'Удалить видео', 'Удалить статистику'):
                        if user_key in self.selected_list:
                            self.selected_list.remove(user_key)  # Убираем из списка
                        else:
                            self.selected_list.add(user_key)  # Добавляем в список
                        await self.close()  # Перерисовываем кнопки с обновленными значениями
                    elif list(self.state_stack.keys())[-2] in ('Новый опрос', 'Редактировать опрос'):
                        if user_key in self.selected_list:
                            self.selected_list.remove(user_key)  # Убираем из списка
                        else:
                            self.selected_list.add(user_key)  # Добавляем в список
                        await self.selectsendsurvey()
                    elif 'Новый опрос' not in list(self.state_stack.keys()) and 'Редактировать опрос' not in list(
                            self.state_stack.keys()) and 'Напоминание' not in list(
                        self.state_stack.keys()) and list(self.state_stack.keys())[
                        -1] != 'Редактировать напоминание':
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
                    elif list(self.state_stack.keys())[-1] == 'Редактировать напоминание':
                        if user_key in self.selected_list:
                            self.selected_list.remove(user_key)  # Убираем из списка
                        else:
                            self.selected_list.add(user_key)  # Добавляем в список
                        await self.selectsendsurvey()
                # elif call.data in ("Товарищеская игра", "Тренировка", "Игра"):
                #     if list(self.state_stack.keys())[-1] == 'Новый опрос':
                #         self.unique_id = str(uuid.uuid4())  # Генерирует случайный UUID версии 4
                #         if self.unique_id not in self.user_data:
                #             self.user_data[self.unique_id] = {}  # Создаем запись для уникального ID
                #         self.user_data[self.unique_id]['Тип'] = f"{call.data}"
                #         if not self.state_stack:
                #             self.state_stack[self.call.data] = self.typeplay
                #         await self.newsurvey()
                #     else:
                #         self.call.data = 'Тип_' + self.call.data
                #         await self.save_edit()
                # elif self.call.data == 'Создать напоминание':
                #     self.unique_id = str(uuid.uuid4())  # Генерирует случайный UUID версии 4
                #     self.user_data.clear()
                #     if self.unique_id not in self.user_data:
                #         self.user_data[self.unique_id] = {}  # Создаем запись для уникального ID
                #     now = datetime.now()
                #     await self.generate_calendar(now.year, now.month)
                # elif call.data.startswith("prev_") or call.data.startswith("next_"):
                #     _, year, month = call.data.split("_")
                #     if list(self.state_stack.keys())[-1] == 'Новый опрос':
                #         await self.generate_calendar(int(year), int(month))
                #     elif 'Новый опрос' not in list(self.state_stack.keys()) and 'Редактировать опрос' not in list(
                #             self.state_stack.keys()) and list(self.state_stack.keys())[
                #         -1] != 'Редактировать напоминание':
                #         await self.generate_calendar(int(year), int(month))
                #     elif list(self.state_stack.keys())[-1] == 'Редактировать напоминание':
                #         await self.generate_calendar(int(year), int(month))
                #     else:
                #         if not self.send_serveys:
                #             response_text = f"Вы находитесь в разделе: Главное меню - Управление - Редактировать опрос - <u>Изменить дату тренировки/игры</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите дату:"
                #         else:
                #             self.send_serveys = None
                #             self.state_stack = dict(list(self.state_stack.items())[:3])
                #             response_text = f"Вы находитесь в разделе: Главное меню - Управление - Редактировать опрос - <u>Изменить дату отправки опроса</u>.\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите дату:"
                #         await self.generate_calendar(int(year), int(month), response_text=response_text)
                #
                # elif call.data.startswith("prevsend_") or call.data.startswith("nextsend_"):
                #     _, year, month = call.data.split("_")
                #     await self.generate_calendar(int(year), int(month))
                #
                # elif call.data.startswith("time_"):
                #     _, time = call.data.split("_")
                #     if list(self.state_stack.keys())[-1] == 'Новый опрос':
                #         if 'Время тренировки/игры' not in (self.user_data[self.unique_id].keys()):
                #             # Теперь можно безопасно записать дату
                #             self.user_data[self.unique_id]['Время тренировки/игры'] = f"{time}"
                #             await self.getaddress()
                #         # Передаем дату в функцию (убрал .value(), так как строка не имеет такого метода)
                #
                #         elif 'Время отправки опроса' not in (self.user_data[self.unique_id].keys()):
                #             # Теперь можно безопасно записать дату
                #             self.user_data[self.unique_id]['Время отправки опроса'] = f"{time}"
                #             await self.save_survey()
                #     elif 'Новый опрос' not in list(self.state_stack.keys()) and 'Редактировать опрос' not in list(
                #             self.state_stack.keys()) and list(self.state_stack.keys())[
                #         -1] != 'Редактировать напоминание':
                #         self.user_data[self.unique_id]['Время отправки напоминания'] = f"{time}"
                #         await self.getaddress()
                #     elif list(self.state_stack.keys())[-1] == 'Редактировать напоминание':
                #         self.call.data = f"Время отправки напоминания_{time}"
                #         await self.save_edit()
                #     else:
                #         if not self.send_serveys:
                #             self.call.data = f"Время тренировки/игры_{time}"
                #         else:
                #             self.call.data = f"Время отправки опроса_{time}"
                #         await self.save_edit()
                #
                # elif call.data.startswith("day_"):
                #     _, year, month, day = call.data.split("_")
                #     if list(self.state_stack.keys())[-1] == 'Новый опрос':
                #         if 'Дата тренировки/игры' not in (self.user_data[self.unique_id].keys()):
                #             # Теперь можно безопасно записать дату
                #             self.user_data[self.unique_id][
                #                 'Дата тренировки/игры'] = f"{int(day):02d}-{int(month):02d}-{year}"
                #             await self.generatetime()
                #         elif 'Дата отправки опроса' not in (self.user_data[self.unique_id].keys()):
                #             self.user_data[self.unique_id][
                #                 'Дата отправки опроса'] = f"{int(day):02d}-{int(month):02d}-{year}"
                #             await self.timesendsurvey()
                #
                #     elif 'Новый опрос' not in list(self.state_stack.keys()) and 'Редактировать опрос' not in list(
                #             self.state_stack.keys()) and list(self.state_stack.keys())[
                #         -1] != 'Редактировать напоминание':
                #         self.user_data[self.unique_id][
                #             'Дата отправки напоминания'] = f"{int(day):02d}-{int(month):02d}-{year}"
                #         await self.timesendsurvey()
                #
                #     elif list(self.state_stack.keys())[-1] == 'Редактировать напоминание':
                #         self.call.data = f"Дата отправки напоминания_{int(day):02d}-{int(month):02d}-{year}"
                #         await self.save_edit()
                #     else:
                #         if not self.send_serveys:
                #             self.call.data = f"Дата тренировки/игры_{int(day):02d}-{int(month):02d}-{year}"
                #         else:
                #             self.call.data = f"Дата отправки опроса_{int(day):02d}-{int(month):02d}-{year}"
                #         await self.save_edit()
                #     # Передаем дату в функцию (убрал .value(), так как строка не имеет такого метода)
                #
                # elif call.data == 'select_send_command':
                #     if list(self.state_stack.keys())[-1] == 'Новый опрос':
                #         # Теперь можно безопасно записать дату
                #         self.user_data[self.unique_id]['Получатели опроса'] = ','.join(self.selected_list)
                #         # Передаем дату в функцию (убрал .value(), так как строка не имеет такого метода)
                #         await self.select_date_send_survey()
                #     elif 'Новый опрос' not in list(self.state_stack.keys()) and 'Редактировать опрос' not in list(
                #             self.state_stack.keys()) and list(self.state_stack.keys())[
                #         -1] != 'Редактировать напоминание':
                #         self.user_data[self.unique_id]['Получатели напоминания'] = ','.join(self.selected_list)
                #         await self.save_survey()
                #     elif list(self.state_stack.keys())[-1] == 'Редактировать напоминание':
                #         self.call.data = f'Получатели напоминания_{self.selected_list}'
                #         await self.save_edit()
                #     else:
                #         self.call.data = f'Получатели опроса_{self.selected_list}'
                #         await self.save_edit()
                #
                # elif call.data == "back_hours":
                #     # Переход назад (цикл через 2 -> 2.5 -> 3)
                #     if self.hour == 2:
                #         self.hour = 3
                #     elif self.hour == 3:
                #         self.hour = 2.5
                #     elif self.hour == 2.5:
                #         self.hour = 2
                #     await self.generatetime()
                # elif call.data == "up_hour":
                #     # Переход назад (цикл через 2 -> 2.5 -> 3)
                #     if self.hour == 2:
                #         self.hour = 2.5
                #     elif self.hour == 2.5:
                #         self.hour = 3
                #     elif self.hour == 3:
                #         self.hour = 2
                #     await self.generatetime()
                #
                # elif call.data.startswith("price_"):
                #     _, price = call.data.split("_")
                #     if list(self.state_stack.keys())[-1] == 'Новый опрос':
                #         self.user_data[self.unique_id]['Цена'] = f"{price}"
                #         await self.selectsendsurvey()
                #     else:
                #         self.call.data = f"Цена_{price}"
                #         await self.save_edit()
                # elif self.call.data == "nextdell" and self.current_index < len(self.surveys) - 1:
                #     self.current_index += 1
                #     await self.del_survey()
                # elif self.call.data == "prevdell" and self.current_index > 0:
                #     self.current_index -= 1
                #     await self.del_survey()
                # elif self.call.data == "mainnextedit" and self.current_index < len(self.surveys) - 1:
                #     self.current_index += 1
                #
                #     if list(self.state_stack.keys())[-1] not in ('Результаты опросов', 'Напоминание'):
                #         await self.edit_survey()
                #     elif list(self.state_stack.keys())[-1] == 'Напоминание':
                #         await self.user_receipts_reminder()
                #     else:
                #         await self.result_surveys()
                # elif self.call.data == "mainprevedit" and self.current_index > 0:
                #     self.current_index -= 1
                #
                #     if list(self.state_stack.keys())[-1] not in ('Результаты опросов', 'Напоминание'):
                #         await self.edit_survey()
                #     elif list(self.state_stack.keys())[-1] == 'Напоминание':
                #         await self.user_receipts_reminder()
                #     else:
                #         await self.result_surveys()
            else:
                await self.back_history(call.message)

    async def distribution_center(self):
        self.select_command = str(self.call.data).replace('Админы', 'admins')
        if 'Закрыть доступ' in list(self.state_stack.keys()) or 'Удалить видео' in list(
                self.state_stack.keys()) or 'Удалить статистику' in list(self.state_stack.keys()):
            await self.close()
        elif 'Открыть доступ' in list(self.state_stack.keys()):
            response_text = str(await self.history()).replace('\n\nВыберите раздел:',
                                                              '') + f"Напишите Ник и id пользователя для добавления через двоеточие, пример:\n Вася:2938214371 или Петя:@petya (можно без @). \nТакже можно добавлять списком нескольких пользователей через запятую, пример:\nВася:2938214371, Петя:@petya, Lena:lenusik"
            self.user_states[self.call.message.chat.id] = "add"
            await self.edit_message(response_text)
        elif 'Добавить видео' in list(self.state_stack.keys()) or 'Добавить статистику' in list(
                self.state_stack.keys()):
            response_text = str(await self.history()).replace('\n\nВыберите раздел:',
                                                              '') + f"Напишите название  и ссылку для добавления через двоеточие, пример:\nСезон 2024-2025:https://disk.yandex.ru/d/bWFMzczzg\nТакже можно добавлять списком несколько ссылок через запятую, пример:\nСезон 2024-2025:https://disk.yandex.ru/d/bWFMzczzg, Сезон 2025-2026:https://disk.yandex.ru/d/bW343Mzczzg"
            # Редактируем текущее сообщение, чтобы запросить имя сотрудника
            self.user_states[self.call.message.chat.id] = "add"
            await self.edit_message(response_text)

    async def edit_message(self, response_text=None, buttons=None, buttons_row=4):
        if not response_text:
            response_text = await self.history()
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
        if 'Главное меню' not in list(self.state_stack.keys()):
            self.state_stack['Главное меню'] = self.show_start_menu
        buttons_name = ["Начать"]
        data = await storage.load_data()
        response_text = f"""Вы находитесь в разделе: <u>Главное меню</u>\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел:"""
        if self.admin["is_admin"]:
            buttons_name.append('Управление')
        try:
            buttons = {name: name for name in buttons_name}
            await self.edit_message(response_text, buttons)
        except:
            users = [str(name.replace('@', '')).split('_')[0] for name in
                     data["commands"]['RedHeads']["users"].values()]

            if users:
                if any(user in users for user in [message.chat.id, str(message.chat.username).replace('@', '')]):
                    with open(config.IMG_FISH_PATH, 'rb') as photo:
                        await bot.send_photo(message.chat.id, photo)
                else:
                    with open(config.IMG_VOLLEY_PATH, 'rb') as photo:
                        await bot.send_photo(message.chat.id, photo)
            else:
                with open(config.IMG_VOLLEY_PATH, 'rb') as photo:
                    await bot.send_photo(message.chat.id, photo)

            await bot.send_message(chat_id=message.chat.id, text=response_text, reply_markup=self.markup,
                                   parse_mode="HTML")

    # Запуск бота
    async def navigate(self):
        get_data = await storage.load_data()
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
        await self.edit_message(buttons=buttons)

    async def main_control(self):
        buttons_name = ["Открыть доступ", "Закрыть доступ"]
        buttons = {name: name for name in buttons_name}
        await self.edit_message(buttons=buttons)

    async def open_control(self):
        data = await storage.load_data()
        buttons_name = [key for key in data["commands"].keys()] + ['Админы']
        buttons = {name: name for name in buttons_name}
        await self.edit_message(buttons=buttons)

    async def add_list(self, message):
        if message.text not in ['/back',
                                '/start']:
            if ":" in str(message.text):
                new_video_stats = str(message.text).replace(' ', '').replace('\n', ',').replace(',,', ',').replace('@',
                                                                                                                   '').split(
                    ',')  # Получаем введенное имя сотрудника

                data = await storage.load_data()
                users_not_write = {}
                count = 1
                for new_name in new_video_stats:
                    if ":" in str(new_name) and len(new_name.split(":", 1)[0]) >= 3 <= len(new_name.split(":", 1)[1]):
                        name, value = new_name.split(":", 1)
                        text = 'Открыть доступ' if 'Добавить видео' not in self.state_stack and 'Добавить статистику' not in self.state_stack else 'Видео' if 'Добавить видео' in self.state_stack else 'Статистика'

                        if text != 'Открыть доступ':

                            if value not in data["commands"][self.select_command][text].values():
                                data["commands"][self.select_command][text][name] = value
                        else:
                            if self.select_command != 'admins' and value not in data["commands"][self.select_command][
                                "users"].values():
                                data["commands"][self.select_command]["users"][name] = value
                            elif self.select_command == 'admins' and value not in data["admins"].values():
                                data["admins"][name] = value
                    else:
                        users_not_write[str(count)] = new_name
                    count += 1
                await storage.write_data(data)

                if len(users_not_write) == len(new_video_stats):
                    response_test = 'Некорректное добавление, ознакомьтесь с примерами и попробуйте еще раз'
                elif len(users_not_write) != len(new_video_stats) and users_not_write:
                    response_test = f"Некорректное добавление некоторых данных из переданного списка. Номера в списке, которые не удалось добавить: {', '.join(list(users_not_write.keys()))}. Пожалуйста, ознакомьтесь с примерами и попробуйте снова."
                else:
                    response_test = f'Успешно добавлено'

                await bot.answer_callback_query(self.call.id, response_test,
                                                show_alert=True)
                await self.delete_message(message)
                await self.back_history(message)
            else:
                response_test = 'Некорректное добавление, ознакомьтесь с примерами и попробуйте еще раз'
                await bot.answer_callback_query(self.call.id, response_test,
                                                show_alert=True)
                await self.delete_message(message)
                await self.back_history(message)

    async def close_control(self):
        data = await storage.load_data()
        buttons_name = [key for key in data["commands"].keys()] + ['Админы']
        buttons = {name: name for name in buttons_name}
        await self.edit_message(buttons=buttons)

    async def edit_commands(self):
        data = await storage.load_data()
        buttons_name = [key for key in data["commands"].keys()]
        buttons = {name: name for name in buttons_name}
        await self.edit_message(buttons=buttons)

    async def close(self):
        data = await storage.load_data()
        keys_mapping = {
            'Удалить видео': 'Видео',
            'Удалить статистику': 'Статистика'
        }

        text = next((value for key, value in keys_mapping.items() if key in self.state_stack), 'Закрыть доступ')
        get_data = (data["commands"][self.select_command][
                        "users"].items() if self.select_command != 'admins' and text == 'Закрыть доступ' else data[
            'admins'].items() if self.select_command == 'admins' and text == 'Закрыть доступ' else
        data["commands"][self.select_command][text].items())

        if not get_data:
            self.state_stack = dict(list(self.state_stack.items())[:-1])
            response_text = f'Пользователи отсутствуют'
            await bot.answer_callback_query(self.call.id, response_text,
                                            show_alert=True)
            return
        add = {}

        for keys, value in get_data:
            value = str(value).split("_")[0]
            is_selected = f"{value if text == 'Закрыть доступ' else keys}" in self.selected_list
            icon = "✅" if is_selected else "❌"  # Меняем иконку
            button_text = f"{icon} {keys}{'(' + value + ')' if text == 'Закрыть доступ' else ''}"
            add[button_text] = f"toggle_{value if text == 'Закрыть доступ' else keys}"

        add['Удалить'] = {'Отмена!': 'cancellation', "💾 Сохранить!": 'dell_data'}
        if get_data == 'Закрыть доступ':
            add['Удалить'] = {"Отмена!": 'cancellation', '💾 Закрыть доступ!': 'dell_data'}
        await self.edit_message(buttons=add)

    async def dell_list(self):

        # Загружаем данные из файла
        data = await storage.load_data()
        if self.select_command and self.selected_list:
            if 'Закрыть доступ' in list(self.state_stack.keys()):
                if self.select_command == 'admins' and (
                        len(data['admins'].keys()) == 1 or len(data['admins'].keys()) == len(
                    self.selected_list)) and self.selected_list:
                    text = 'пользователи НЕ УДАЛЕНЫ' if len(self.selected_list) > 1 else 'пользователь НЕ УДАЛЕН'
                    response_text = f'Должен быть минимум 1 админ, {text}'
                    self.state_stack = dict(list(self.state_stack.items())[:-2])
                    await bot.answer_callback_query(self.call.id, response_text,
                                                    show_alert=True)
                    await self.back_history(self.call.message)
                else:
                    # Удаляем пользователей
                    for user in self.selected_list:
                        if self.select_command != 'admins':
                            # Проходим по всем пользователям в выбранной команде
                            for username, userid in data["commands"][self.select_command]["users"].items():
                                if str(userid).split('_')[0] == user:
                                    del data["commands"][self.select_command]["users"][username]
                                    break
                        else:
                            for username, userid in data["admins"].items():
                                if str(userid).split('_')[0] == user:
                                    del data["admins"][username]
                                    break
                    self.state_stack = dict(list(self.state_stack.items())[:-2])
                    # Сохраняем обновленные данные обратно в файл
                    await storage.write_data(data)  # Передаем измененные данные в функцию сохранения
                    await self.back_history(self.call.message)
                    response_text = 'Пользователи удалены' if len(self.selected_list) > 1 else 'Пользователь удален'
                    await bot.answer_callback_query(self.call.id, response_text,
                                                    show_alert=True)

            else:
                text = 'Видео' if 'Удалить видео' in list(self.state_stack.keys()) else 'Статистика'
                # Удаляем пользователей
                if self.selected_list:
                    for sel_data in self.selected_list:
                        for username, userid in data["commands"][self.select_command][text].items():
                            if str(username) == sel_data:
                                del data["commands"][self.select_command][text][sel_data]
                                break
                    # Сохраняем обновленные данные обратно в файл
                    self.state_stack = dict(list(self.state_stack.items())[:-2])
                    await storage.write_data(data)  # Передаем измененные данные в функцию сохранения
                    await self.back_history(self.call.message)
                    response_text = 'Ссылки удалены' if len(self.selected_list) > 1 else 'Ссылка удалена'
                    await bot.answer_callback_query(self.call.id, response_text,
                                                    show_alert=True)

        else:
            self.state_stack = dict(list(self.state_stack.items())[:-2])
            await self.back_history(self.call.message)
        self.selected_list.clear()

    async def edit_command(self):
        buttons_name = ["Редактировать видео", "Редактировать статистику"]
        buttons = {name: name for name in buttons_name}
        await self.edit_message(buttons=buttons)

    async def edit_video(self):
        buttons_name = ["Добавить видео", "Удалить видео"]
        buttons = {name: name for name in buttons_name}
        await self.edit_message(buttons=buttons)

    async def edit_statistic(self):
        buttons_name = ["Добавить статистику", "Удалить статистику"]
        buttons = {name: name for name in buttons_name}
        await self.edit_message(buttons=buttons)

    async def the_survey(self):
        buttons_name = ["Новый опрос", "Удалить опрос", "Редактировать опрос", "Результаты опросов"]
        buttons = {name: name for name in buttons_name}
        await self.edit_message(buttons=buttons)

    async def typeplay(self):
        if not self.user_data:
            self.unique_id = str(uuid.uuid4())
            self.user_data[self.unique_id] = {}

        buttons_name = ["Игра", "Тренировка", "Товарищеская игра"]
        buttons = {name: name for name in buttons_name}
        await self.edit_message(buttons=buttons)

    async def generate_calendar(self, year, month, response_text=None):
        text_responce = "\n".join(
            f"{k}: {v}" for game_data in self.user_data.values() for k, v in game_data.items())

        cal = calendar.monthcalendar(year, month)

        buttons = []

        # Заголовок: Апрель 2025
        buttons.append([InlineKeyboardButton(f"{storage.MONTH_NAMES[month]} {year}", callback_data="ignore")])

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
        await self.edit_message(await self.history() + text_responce, buttons=buttons)

    async def newsurvey(self):
        text_responce = "\n".join(
            f"{k}: {v}" for game_data in self.user_data.values() for k, v in game_data.items())

        now = datetime.now()
        await self.generate_calendar(now.year, now.month, await self.history() + text_responce)

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
        text_responce = "\n".join(
            f"{k}: {v}" for game_data in self.user_data.values() for k, v in game_data.items())
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

        await self.edit_message(await self.history() + text_responce, buttons=buttons)

    async def getaddress(self):
        text_responce = "\n".join(
            f"{k}: {v}" for game_data in self.user_data.values() for k, v in game_data.items())

        self.user_states[self.call.message.chat.id] = "add_address"
        await self.edit_message(await self.history() + text_responce)

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
                    self.state_stack.keys()) and list(self.state_stack.keys())[-1] != 'Редактировать напоминание':
                self.user_data[self.unique_id]['Текст напоминания'] = message.text
                await self.receipts_reminder()
            elif list(self.state_stack.keys())[-1] == 'Редактировать напоминание':
                self.call.data = f"Текст напоминания_{message.text}"
                await self.save_edit()
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
        text_responce = "\n".join(
            f"{k}: {v}" for game_data in self.user_data.values() for k, v in game_data.items())

        buttons = [
            [InlineKeyboardButton(str(price), callback_data=f"price_{price}") for price in prices]
        ]

        await self.edit_message(await self.history() + text_responce, buttons=buttons)

    async def selectsendsurvey(self):

        text_responce = "\n".join(f"{k}: {v}" for game_data in self.user_data.values() for k, v in game_data.items())
        data = await storage.load_data()
        users = {name: name for name in data["commands"].keys()}
        users['Админы'] = 'Админы'

        # Создание кнопок
        buttons = {f"{'✅' if value in self.selected_list else '❌'} {key}": f"toggle_{value}" for key, value in
                   users.items()}

        buttons['end'] = {"Сохранить": "select_send_command"}
        await self.edit_message(await self.history() + text_responce, buttons=buttons)

    async def select_date_send_survey(self):
        text_responce = "\n".join(f"{k}: {v}" for game_data in self.user_data.values() for k, v in game_data.items())

        now = datetime.now()
        await self.generate_calendar(now.year, now.month, await self.history() + text_responce)

    async def timesendsurvey(self):
        self.send_serveys = self.call.data
        time = [f"{hour:02}:{minute:02}" for hour in range(9, 24) for minute in [0, 30]]
        text_responce = "\n".join(f"{k}: {v}" for game_data in self.user_data.values() for k, v in game_data.items())
        buttons = [[InlineKeyboardButton(key, callback_data=f"time_{key}") for key in time]]
        await self.edit_message(await self.history() + text_responce, buttons=buttons)

    async def save_survey(self):
        text_responce = "\n".join(f"{k}: {v}" for game_data in self.user_data.values() for k, v in game_data.items())

        buttons = {"Отмена": "cancellation", "Запланировать напоминание": "save_send_survey"}
        await self.edit_message(await self.history() + text_responce, buttons=buttons)

    async def save(self):
        data = await storage.load_data()
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
        await storage.write_data(data)

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
        self.data = await storage.load_data()
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

        add['end'] = {"Отмена": "cancellation", "Удалить опрос": "dell_survey"}

        await self.edit_message(response_text, buttons=add, buttons_row=2)

    async def save_dell_survey(self):
        data = await storage.load_data()
        key_del = self.surveys[self.current_index][0]
        del data["surveys"][key_del]
        # Сохраняем обновленные данные обратно в файл
        await storage.write_data(data)  # Передаем измененные данные в функцию сохранения
        response_text = 'Опрос удален'
        await bot.answer_callback_query(self.call.id, response_text,
                                        show_alert=True)
        self.current_index = 0
        await self.the_survey()

    async def edit_survey(self):
        self.data = await storage.load_data()
        """Отображает текущий опрос с кнопками навигации"""
        if list(self.state_stack.keys())[-1] != 'Редактировать напоминание':
            self.surveys = list(self.data["surveys"].items())
            if not self.surveys:
                response_text = 'Нет доступных опросов.'
                await bot.answer_callback_query(self.call.id, response_text, show_alert=True)
                return
        else:
            self.surveys = list(self.data["reminder"].items())
            if not self.surveys:
                response_text = 'Нет доступных напоминаний.'
                await bot.answer_callback_query(self.call.id, response_text, show_alert=True)
                return

        survey_id, survey_data = self.surveys[self.current_index]

        if list(self.state_stack.keys())[-1] != 'Редактировать напоминание':
            response_text = f"Вы находитесь в разделе: Главное меню - Управление - <u>Редактировать опрос</u>.\n\n"

            response_text += f"<b>Опрос {self.current_index + 1} из {len(self.surveys)}</b>\n\n"
            response_text += "\n".join(f"{k}: {v}" for k, v in survey_data.items() if k not in (
                'Отметились', 'Количество отметившихся', 'id опроса', 'Опрос отправлен', 'Опрос открыт'))
            response_text += ('\n\nИспользуйте кнопки для навигации. Чтобы вернуться на шаг назад, '
                              'используйте команду /back. В начало /start\n\nВыберите раздел:')
        else:
            response_text = f"Вы находитесь в разделе: Главное меню - Управление - Напоминание - <u>Редактировать напоминание</u>.\n\n"

            response_text += f"<b>Напоминание {self.current_index + 1} из {len(self.surveys)}</b>\n\n"

            response_text += "\n".join(
                f"{k}: {v}"
                for k, v in survey_data.items()
                if k not in ('Получатели напоминания', 'Напоминание отправлено')
            )

            if type(self.data["reminder"][survey_id]['Получатели напоминания']) != str:
                response_text += '\nПолучатели напоминания:\n' + await self.format_dict(
                    self.data["reminder"][survey_id]['Получатели напоминания'], base_indent=4)
            else:
                response_text += '\nПолучатели напоминания:' + self.data["reminder"][survey_id][
                    'Получатели напоминания']
            response_text += ('\n\nИспользуйте кнопки для навигации. Чтобы вернуться на шаг назад, '
                              'используйте команду /back. В начало /start\n\nВыберите раздел:')
        add = {
            "<": "mainprevedit" if self.current_index > 0 else None,
            ">": "mainnextedit" if self.current_index < len(self.surveys) - 1 else None
        }

        # Убираем ключи с значением None
        add = {key: value for key, value in add.items() if value is not None}
        if list(self.state_stack.keys())[-1] != 'Редактировать напоминание':
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
        else:
            add['edit'] = {
                "Изменить дату отправки напоминания": "edit_newsurvey",
                "Изменить время отправки напоминания": "edit_timesendsurvey",
                "Изменить текст напоминания": "edit_getaddress",
                "Изменить получателей напоминания": "edit_receipts_reminder"
            }

        await self.edit_message(response_text, buttons=add, buttons_row=3)

    async def save_edit(self):
        data = await storage.load_data()
        key_del = self.surveys[self.current_index][0]
        new_value = self.call.data.split("_")

        if new_value[0] != 'Получатели опроса' and list(self.state_stack.keys())[-1] != 'Редактировать напоминание':
            data["surveys"][key_del][new_value[0]] = new_value[-1]
        elif list(self.state_stack.keys())[-1] == 'Редактировать напоминание' and new_value[
            0] != 'Получатели напоминания':
            data["reminder"][key_del][new_value[0]] = new_value[-1]
        elif list(self.state_stack.keys())[-1] == 'Редактировать напоминание' and new_value[
            0] == 'Получатели напоминания':
            data["reminder"][key_del][new_value[0]] = ', '.join(self.selected_list)
        else:
            data["surveys"][key_del][new_value[0]] = ', '.join(self.selected_list)

        await storage.write_data(data)  # Передаем измененные данные в функцию сохранения
        response_text = (
            f'{new_value[0]} изменен' if new_value[0] in ("Тип", "Адрес", "Текст напоминания") else
            f'{new_value[0]} изменена' if new_value[0] in (
                "Дата тренировки/игры", 'Дата отправки напоминания', "Цена") else
            f'{new_value[0]} изменены' if new_value[0] in ("Получатели опроса", 'Получатели напоминания') else
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
        self.data = await storage.load_data()
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
        await self.edit_message(await self.history(), buttons)

    async def receipts_reminder(self):
        text_responce = "\n".join(f"{k}: {v}" for game_data in self.user_data.values() for k, v in game_data.items())
        buttons_name = ["Команды", "Пользователи"]
        buttons = {name: name for name in buttons_name}
        await self.edit_message(await self.history() + text_responce, buttons)

    async def user_receipts_reminder(self):
        data = await storage.load_data()
        self.surveys = [command for command in data["commands"].keys() if data["commands"][command]['users']] + [
            'Админы']  # Преобразуем в список для удобства доступа по индексу
        users = self.surveys[self.current_index]

        # Инициализация "Получатели напоминания" если его еще не
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
        buttons['Закрыть'] = {'Отмена!': 'cancellation', '💾 Сохранить!': 'save_send_survey'}
        # Отправка сообщения с кнопками
        await self.edit_message(await self.history() + text_responce, buttons=buttons)


async def main():
    bot_instance = Main()

    # Запускаем async_survey в отдельной задаче
    survey_task = asyncio.create_task(send_survey())
    survey_task_2 = asyncio.create_task(send_reminder())
    # Ждём завершения async_init
    await bot_instance.async_init()
    # Ожидаем завершения опроса бота
    await bot.infinity_polling()
    # Опционально: дожидаемся завершения survey_task
    await survey_task
    await survey_task_2


if __name__ == "__main__":
    asyncio.run(main())
