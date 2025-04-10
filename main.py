from telebot.async_telebot import AsyncTeleBot
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
        if any(state in self.state_stack for state in
               ['Новый опрос', 'Новое напоминание']):
            if 'Новый опрос' in self.state_stack:
                # Предположим, что self.state_stack и original_keys уже определены
                original_keys = {
                    "Новый опрос": self.process_buttons,
                    "Тип": self.process_buttons,
                    "Дата тренировки/игры": self.process_buttons,
                    "Время тренировки/игры": self.process_buttons,
                    "Адрес": self.process_buttons,
                    "Цена": self.process_buttons,
                    "Получатели опроса": self.process_buttons,
                    "Дата отправки опроса": self.process_buttons,
                    "Время отправки опроса": self.process_buttons,
                    "Результаты": self.process_buttons
                }
            else:
                original_keys = {
                    "Новое напоминание": self.process_buttons,
                    "Дата отправки напоминания": self.process_buttons,
                    "Время отправки напоминания": self.process_buttons,
                    "Текст напоминания": self.process_buttons,
                    "Выбор получателей": self.process_buttons,
                    f"{'Команды' if 'Команды' in self.state_stack else 'Пользователи'}": self.process_buttons,
                    "Получатели напоминания": self.process_buttons,
                    "Результаты": self.process_buttons
                }
            # Получаем список ключей из original_keys
            keys = list(original_keys.keys())

            # Находим последний ключ из self.state_stack
            last_key = next((key for key in reversed(self.state_stack.keys()) if key in keys), None)

            if last_key is not None:
                # Находим индекс последнего ключа
                last_index = keys.index(last_key)

                # Проверяем, есть ли следующий ключ
                if last_index + 1 < len(keys):
                    next_key = keys[last_index + 1]
                    # Добавляем следующий ключ в self.state_stack
                    self.state_stack[next_key] = original_keys[next_key]  # или любое другое значение, которое вам нужно
            found_key = []
            for name in self.state_stack.keys():
                if name in original_keys.keys():
                    found_key.append(name)

            result = found_key if len(found_key) - 2 > len(
                [k for game_data in self.user_data.values() for k, v in game_data.items()]) else None
            if result:
                del self.state_stack[result[-1]]

        response_text = ' - '.join(list(self.state_stack.keys())[:-1]) + ' - <u>' + list(self.state_stack.keys())[
            -1] + '</u>' if self.state_stack else ''

        response_text = f"Вы находитесь в разделе: {response_text.replace('- <u>Главное меню</u>', '<u>Главное меню</u>')}"

        if len(self.state_stack) > 2:
            data = await storage.load_data()
            response_text += f"\n\nНапишите Ник и id пользователя для добавления через двоеточие, пример:\n Вася:2938214371 или Петя:@petya (можно без @). \nТакже можно добавлять списком нескольких пользователей через запятую, пример:\nВася:2938214371, Петя:@petya, Lena:lenusik" if \
                list(self.state_stack.keys())[-2] in ('Открыть доступ') else ''
            response_text += f"\n\nНапишите название  и ссылку для добавления через двоеточие, пример:\nСезон 2024-2025:https://disk.yandex.ru/d/bWFMzczzg\nТакже можно добавлять списком несколько ссылок через запятую, пример:\nСезон 2024-2025:https://disk.yandex.ru/d/bWFMzczzg, Сезон 2025-2026:https://disk.yandex.ru/d/bW343Mzczzg" if \
                list(self.state_stack.keys())[-2] in ['Добавить статистику', 'Добавить видео'] else ''

            text = 'surveys' if any(state in self.state_stack for state in
                                    ['Редактировать опрос', 'Удалить опрос', 'Результаты опросов',
                                     'Новый опрос']) else 'reminder'

            surveys_items = list(data[text].items())
            if surveys_items:
                _, value = surveys_items[self.current_index]
                text_ = 'Напоминание' if text == 'reminder' else 'Опрос'
                if any(state in self.state_stack for state in
                       ['Редактировать опрос', 'Редактировать напоминание', 'Удалить опрос', 'Удалить напоминание',
                        'Результаты опросов', 'Результаты напоминаний']):
                    response_text += f"\n\n<b>{text_} {self.current_index + 1} из {len(surveys_items)}</b>\n\n"

                if any(state in self.state_stack for state in
                       ['Новый опрос', 'Новое напоминание', 'Удалить опрос', 'Удалить напоминание']):
                    response_text += '\n\n' + "\n".join(f"{k}: {v}" for game_data in self.user_data.values() for k, v in
                                                        game_data.items() if k not in (
                                                            'Отметились', 'Количество отметившихся',
                                                            'id опроса'))
                if any(state in self.state_stack for state in
                       ['Результаты опросов', 'Результаты напоминаний']):
                    response_text += '\n\n' + "\n".join(f"{k}: {v}" for game_data in self.user_data.values() for k, v in
                                                        game_data.items() if k not in (
                                                            'id опроса'))
                if any(state in self.state_stack for state in
                       ['Редактировать опрос', 'Редактировать напоминание']):
                    response_text += '\n\n' + "\n".join(f"{k}: {v}" for game_data in self.user_data.values() for k, v in
                                                        game_data.items() if k not in (
                                                            'Отметились', 'Количество отметившихся', 'id опроса',
                                                            'Опрос отправлен',
                                                            'Опрос открыт', 'Получатели напоминания'))
                    response_text += f"'\nПолучатели напоминания:\n{await self.format_dict(value['Получатели напоминания'], base_indent=4)}\n" if 'Редактировать напоминание' in self.state_stack and type(
                        value['Получатели напоминания']) != str else '\nПолучатели напоминания: ' + value[
                        'Получатели напоминания'] if 'Редактировать напоминание' in self.state_stack or 'Результаты напоминаний' in self.state_stack else ''

        response_text += f"""\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start \n\nВыберите раздел {f'(интервал - {f"{self.hour}ч" if self.hour != 2.5 else "2ч30м"} )' if 'Дата тренировки/игры' in [k for game_data in self.user_data.values() for k, v in game_data.items()] and "Время тренировки/игры" not in [k for game_data in self.user_data.values() for k, v in game_data.items()] else ''}:"""

        return response_text.replace('\n\n\n', '\n')

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

                # Если произошла ошибка, удаляем элемент и продолжаем цикл
                if self.user_data.values():
                    keys_to_delete = []  # Список для хранения ключей, которые нужно удалить
                    for game_data in self.user_data.values():
                        for k, v in game_data.items():
                            if last_key in (k, v):
                                keys_to_delete.append(k)  # Добавляем ключ в список на удаление
                    for key in keys_to_delete:
                        del self.user_data[self.unique_id][key]

                try:
                    if 'Время тренировки/игры' in self.state_stack or 'Время отправки напоминания' in self.state_stack:
                        self.user_states[message.chat.id] = "add"
                    # Попытка вызвать функцию
                    await last_function()
                    break  # Выход из цикла, если вызов завершился успешно
                except:
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
            self.state_stack.clear()
            self.user_data.clear()
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
                "Новое напоминание": self.generate_calendar,
                "save": self.save,
                "Удалить опрос": self.dell_edit_survey,
                "cansel_survey": self.the_survey,
                "save_dell_survey": self.dell_list,
                "Редактировать опрос": self.dell_edit_survey,
                "Изменить тип": self.typeplay,
                "Изменить дату тренировки/игры": self.generate_calendar,
                "Изменить время тренировки/игры": self.generatetime,
                "Изменить адрес": self.distribution_center,
                "Изменить цену": self.getprice,
                "Изменить получателей": self.selectsendsurvey,
                "Изменить дату отправки опроса": self.generate_calendar,
                "Изменить время отправки опроса": self.timesendsurvey,
                "Результаты опросов": self.dell_edit_survey,
                "Напоминание": self.reminder,
                "Команды": self.selectsendsurvey,
                "Редактировать напоминание": self.dell_edit_survey

            }
            # Объединяем словари
            actions = {**actions, **extra_actions}

            if self.call.data == 'cancellation':
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

                elif self.call.data.startswith("toggle_"):
                    user_key = '_'.join(self.call.data.split("_")[1:])  # Извлекаем имя пользователя
                    if list(self.state_stack.keys())[-2] in ('Закрыть доступ', 'Удалить видео', 'Удалить статистику'):
                        if user_key in self.selected_list:
                            self.selected_list.remove(user_key)  # Убираем из списка
                        else:
                            self.selected_list.add(user_key)  # Добавляем в список
                        await self.close()  # Перерисовываем кнопки с обновленными значениями
                    elif 'Новый опрос' in self.state_stack or 'Редактировать опрос' in self.state_stack or 'Новое напоминание' in self.state_stack:
                        if user_key in self.selected_list:
                            self.selected_list.remove(user_key)  # Убираем из списка
                        else:
                            self.selected_list.add(user_key)  # Добавляем в список
                        await self.selectsendsurvey()

                elif call.data.startswith("prev_") or call.data.startswith("next_"):
                    _, year, month = call.data.split("_")
                    await self.generate_calendar(int(year), int(month))

                elif call.data.startswith("day_"):
                    _, year, month, day = call.data.split("_")
                    if 'Новый опрос' in self.state_stack:
                        if 'Время тренировки/игры' not in self.state_stack:

                            self.user_data[self.unique_id][
                                'Дата тренировки/игры'] = f"{int(day):02d}-{int(month):02d}-{year}"
                            self.state_stack['Дата тренировки/игры'] = self.generate_calendar
                            await self.generatetime()
                        elif 'Время отправки опроса' not in self.state_stack:
                            self.user_data[self.unique_id][
                                'Дата отправки опроса'] = f"{int(day):02d}-{int(month):02d}-{year}"
                            self.state_stack['Дата отправки опроса'] = self.generate_calendar
                            await self.timesendsurvey()
                    elif 'Новое напоминание' in self.state_stack:
                        self.user_data[self.unique_id][
                            'Дата отправки напоминания'] = f"{int(day):02d}-{int(month):02d}-{year}"
                        self.state_stack['Дата отправки напоминания'] = self.generate_calendar
                        await self.timesendsurvey()
                    elif 'Редактировать опрос' in self.state_stack:
                        if 'Изменить дату тренировки/игры' in self.state_stack:
                            self.user_data[self.unique_id][
                                'Дата тренировки/игры'] = f"{int(day):02d}-{int(month):02d}-{year}"
                        elif 'Изменить дату отправки опроса' in self.state_stack:
                            self.user_data[self.unique_id][
                                'Дата отправки опроса'] = f"{int(day):02d}-{int(month):02d}-{year}"
                        await self.save()
                elif call.data in ("Товарищеская игра", "Тренировка", "Игра"):
                    if 'Тип' not in self.user_data.values():
                        self.user_data[self.unique_id]['Тип'] = f"{self.call.data}"
                    if 'Новый опрос' in self.state_stack:
                        await self.generate_calendar()
                    elif 'Редактировать опрос' in self.state_stack:
                        self.user_data[self.unique_id]['Тип'] = f"{self.call.data}"
                        await self.save()

                elif call.data.startswith("time_"):
                    _, time = call.data.split("_")
                    if 'Новый опрос' in self.state_stack:
                        if 'Адрес' not in self.state_stack:
                            self.user_data[self.unique_id]['Время тренировки/игры'] = f"{time}"
                            self.state_stack["Время тренировки/игры"] = self.generatetime
                            await self.distribution_center()
                        elif 'Результаты' not in self.state_stack:
                            self.user_data[self.unique_id]['Время отправки опроса'] = f"{time}"
                            self.state_stack["Время отправки опроса"] = self.timesendsurvey
                            await self.survey_save()
                    elif 'Редактировать опрос' in self.state_stack:
                        self.user_data[self.unique_id]['Время отправки опроса'] = f"{time}"
                        await self.save()
                    elif 'Новое напоминание' in self.state_stack:
                        self.user_data[self.unique_id]['Время отправки напоминания'] = f"{time}"
                        self.state_stack["Время отправки напоминания"] = self.timesendsurvey
                        await self.distribution_center()
                elif call.data == 'continue':
                    if 'Новый опрос' in self.state_stack:
                        self.user_data[self.unique_id]['Получатели опроса'] = ','.join(self.selected_list)
                        self.state_stack["Получатели опроса"] = self.selectsendsurvey
                        await self.generate_calendar()
                    elif 'Редактировать опрос' in self.state_stack:
                        self.user_data[self.unique_id]['Получатели опроса'] = ','.join(self.selected_list)
                        await self.save()
                    elif 'Новое напоминание' in self.state_stack:
                        self.user_data[self.unique_id]['Получатели напоминания'] = ','.join(self.selected_list)
                        await self.survey_save()
                elif call.data in ("back_hours", "up_hour"):
                    hours_list = [2, 2.5, 3]
                    current_index = hours_list.index(self.hour)
                    next_index = (current_index + 1) % len(hours_list)
                    self.hour = hours_list[next_index]
                    await self.generatetime()

                elif call.data.startswith("price_"):
                    _, price = call.data.split("_")
                    if 'Новый опрос' in self.state_stack:
                        self.state_stack['Цена'] = self.getprice
                        self.user_data[self.unique_id]['Цена'] = f"{price}"
                        await self.selectsendsurvey()
                    elif 'Редактировать опрос' in self.state_stack:
                        self.user_data[self.unique_id]['Цена'] = f"{price}"
                        await self.save()

                elif self.call.data in ("nextdell", "prevdell"):
                    data = await storage.load_data()
                    """Отображает текущий опрос с кнопками навигации"""
                    # Предположим, что data["surveys"] - это словарь
                    surveys_items = list(data["surveys"].items())
                    direction = {"nextdell": 1, "prevdell": -1}[self.call.data]
                    new_index = self.current_index + direction
                    if 0 <= new_index < len(surveys_items):
                        self.current_index = new_index
                        await self.dell_edit_survey()

            else:
                await self.back_history(call.message)

    async def distribution_center(self):
        self.select_command = str(self.call.data).replace('Админы', 'admins')
        if list(self.state_stack.keys())[-2] in ('Закрыть доступ', 'Удалить видео', 'Удалить статистику'):
            await self.close()
        elif list(self.state_stack.keys())[-2] in (
                'Добавить видео', 'Добавить статистику', 'Открыть доступ') or list(self.state_stack.keys())[-1] in (
                "Время тренировки/игры", 'Время отправки напоминания') or 'Редактировать опрос' in self.state_stack:
            # Редактируем текущее сообщение, чтобы запросить имя сотрудника
            self.user_states[self.call.message.chat.id] = "add"

            await self.edit_message()
        # elif list(self.state_stack.keys())[-2] in ('Команды'):
        #     self.user_states[self.call.message.chat.id] = "add"
        #     await self.edit_message()

    async def edit_message(self, response_text=None, buttons=None, buttons_row=4):
        if not response_text:
            response_text = await self.history()

        self.markup = InlineKeyboardMarkup()

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
        if 'Главное меню' not in self.state_stack:
            self.state_stack['Главное меню'] = self.show_start_menu
        buttons_name = ["Начать"]
        data = await storage.load_data()
        if self.admin["is_admin"]:
            buttons_name.append('Управление')
        try:
            buttons = {name: name for name in buttons_name}
            await self.edit_message(buttons=buttons)
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

            await bot.send_message(chat_id=message.chat.id, text=await self.history(), reply_markup=self.markup,
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
            if 'Новый опрос' in self.state_stack:
                self.user_data[self.unique_id]['Адрес'] = f"{message.text}"
                self.state_stack['Адрес'] = self.edit_message
                await self.delete_message(message)
                await self.getprice()
                return
            elif 'Новое напоминание' in self.state_stack:
                self.user_data[self.unique_id]['Текст напоминания'] = f"{message.text}"
                self.state_stack['Текст напоминания'] = self.edit_message
                await self.delete_message(message)
                await self.receipts_reminder()
                return
            elif ":" in str(message.text):
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
            elif 'Редактировать опрос' in self.state_stack:
                self.user_data[self.unique_id]['Адрес'] = f"{message.text}"
                await self.delete_message(message)
                await self.save()
                return
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
        if 'Закрыть доступ' in self.state_stack:
            add['Удалить'] = {"Отмена!": 'cancellation', '💾 Закрыть доступ!': 'dell_data'}
        await self.edit_message(buttons=add)

    async def dell_list(self):

        # Загружаем данные из файла
        data = await storage.load_data()
        if self.select_command and self.selected_list:
            if 'Закрыть доступ' in self.state_stack:
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

            elif 'Редактирование команд' in self.state_stack:
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
        elif 'Удалить опрос' in self.state_stack:
            surveys_items = list(data["surveys"].items())
            surveys_key, _ = surveys_items[self.current_index]
            del data["surveys"][surveys_key]
            # Сохраняем обновленные данные обратно в файл
            await storage.write_data(data)  # Передаем измененные данные в функцию сохранения
            response_text = 'Опрос удален'
            await bot.answer_callback_query(self.call.id, response_text,
                                            show_alert=True)
            self.state_stack = dict(list(self.state_stack.items())[:-1]) if len(surveys_items) != 1 else dict(
                list(self.state_stack.items())[:-2])
            self.current_index = 0
            await self.back_history(self.call.message)

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
        if 'Новый опрос' in self.state_stack:
            self.unique_id = str(uuid.uuid4())
            self.user_data[self.unique_id] = {}

        buttons_name = ["Игра", "Тренировка", "Товарищеская игра"]
        buttons = {name: name for name in buttons_name}
        await self.edit_message(buttons=buttons)

    async def generate_calendar(self, year=None, month=None):
        if 'Новое напоминание' in self.state_stack:
            self.user_data = {}
            self.unique_id = str(uuid.uuid4())
            self.user_data[self.unique_id] = {}

        if not year and not month:
            now = datetime.now()
            year, month = now.year, now.month
        cal = calendar.monthcalendar(year, month)
        buttons = [[InlineKeyboardButton(f"{config.MONTH_NAMES[month]} {year}", callback_data="ignore")],
                   [InlineKeyboardButton(day, callback_data="ignore") for day in
                    ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]]]
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
        await self.edit_message(buttons=buttons)

    async def generatetime(self):
        # Генерация слотов времени в зависимости от выбранной длительности
        times = None
        if self.hour == 2:
            times = [f"{hour:02d}:{minute:02d} - {hour + 2:02d}:{minute:02d}"
                     for hour in range(9, 21)
                     for minute in [0, 30]]
        elif self.hour == 2.5:
            times = [f"{hour:02d}:{minute:02d} - {(hour + 2 + (minute + 30) // 60) % 24:02d}:{(minute + 30) % 60:02d}"
                     for hour in range(9, 22)
                     for minute in [0, 30]]
        elif self.hour == 3:
            times = [f"{hour:02d}:{minute:02d} - {hour + 3:02d}:{minute:02d}"
                     for hour in range(9, 21)
                     for minute in [0, 30]]

        # Кнопки таймслотов
        buttons = []
        for i in range(0, len(times), 4):
            buttons.append([
                InlineKeyboardButton(time, callback_data=f"time_{time}")
                for time in times[i:i + 4]
            ])

        # Кнопки навигации по длительности
        hours_list = [2, 2.5, 3]
        index = hours_list.index(self.hour)

        nav_buttons = {
            "<": "back_hours" if index > 0 else None,
            ">": "up_hour" if index < len(hours_list) - 1 else None
        }

        # Убираем пустые
        nav_buttons = {k: v for k, v in nav_buttons.items() if v is not None}
        if nav_buttons:
            buttons.append([
                InlineKeyboardButton(k, callback_data=v)
                for k, v in nav_buttons.items()
            ])

        await self.edit_message(buttons=buttons)

    async def getprice(self):
        prices = [x for x in range(300, 1501, 50)]
        buttons = [
            [InlineKeyboardButton(str(price), callback_data=f"price_{price}") for price in prices]
        ]
        await self.edit_message(buttons=buttons)

    async def selectsendsurvey(self):
        data = await storage.load_data()
        users = {name: name for name in data["commands"].keys()}
        users['Админы'] = 'Админы'
        # Создание кнопок
        buttons = {f"{'✅' if value in self.selected_list else '❌'} {key}": f"toggle_{value}" for key, value in
                   users.items()}

        buttons['end'] = {f"{'Продолжить' if 'Новый опрос' in self.state_stack  or 'Новое напоминание' in self.state_stack else 'Изменить'}": "continue"}
        await self.edit_message(buttons=buttons)

    async def survey_save(self):
        buttons = {"Отмена": "cancellation", "Запланировать": "save"}
        await self.edit_message(buttons=buttons)

    async def timesendsurvey(self):
        time = [f"{hour:02}:{minute:02}" for hour in range(9, 24) for minute in [0, 30]]
        buttons = [[InlineKeyboardButton(key, callback_data=f"time_{key}") for key in time]]
        await self.edit_message(buttons=buttons)

    async def save(self):
        data = await storage.load_data()
        response_text = None
        if 'Новый опрос' in self.state_stack:
            self.user_data[self.unique_id]['Опрос открыт'] = "Нет"
            self.user_data[self.unique_id]['Опрос отправлен'] = "Нет"
            self.user_data[self.unique_id]['Количество отметившихся'] = 0
            self.user_data[self.unique_id]['Отметились'] = {}
            self.user_data[self.unique_id]['id опроса'] = 0
            list_user_data = [k for game_data in self.user_data.values() for k, v in game_data.items()] + [
                'Новый опрос']
            for i in list_user_data:
                if i in self.state_stack:
                    del self.state_stack[i]

            if "surveys" not in data:
                data["surveys"] = {}
                # Добавляем данные правильно (без .values())
            data["surveys"][self.unique_id] = self.user_data[self.unique_id]
            response_text = 'Опрос запланирован'
        elif 'Редактировать опрос' in self.state_stack or 'Редактировать напоминание' in self.state_stack:
            text = 'surveys' if 'Редактировать опрос' in self.state_stack else 'reminder'
            if self.unique_id not in data[text]:
                data[text][self.unique_id] = {}
            data[text][self.unique_id] = self.user_data[self.unique_id]
            response_text = 'Изменено'
            self.state_stack = dict(list(self.state_stack.items())[:-1])
        elif 'Новое напоминание' in self.state_stack:
            self.user_data[self.unique_id]['Напоминание отправлено'] = "Нет"
            list_user_data = [k for game_data in self.user_data.values() for k, v in game_data.items()] + [
                'Новое напоминание']
            for i in list_user_data:
                if i in self.state_stack:
                    del self.state_stack[i]

            if "reminder" not in data:
                data["reminder"] = {}
                # Добавляем данные правильно (без .values())
            data["reminder"][self.unique_id] = self.user_data[self.unique_id]
            response_text = 'Напоминание запланировано'
        # Сохраняем обновленные данные обратно в файл
        await storage.write_data(data)

        await bot.answer_callback_query(self.call.id, response_text, show_alert=True)

        # Очищаем временные данные
        self.user_data.clear()
        self.selected_list.clear()
        await self.back_history(self.call.message)

    async def dell_edit_survey(self):
        self.user_data = {}
        data = await storage.load_data()
        text = 'surveys' if any(state in self.state_stack for state in
                                ['Редактировать опрос', 'Удалить опрос', 'Результаты опросов']) else 'reminder'

        surveys_items = list(data[text].items())

        if not surveys_items:
            response_text = f'Нет доступных {"опросов" if text == "surveys" else "напоминаний"}.'
            await bot.answer_callback_query(self.call.id, response_text, show_alert=True)
            return
        surveys_key, user_data = surveys_items[self.current_index]
        self.unique_id = surveys_key
        self.user_data[surveys_key] = user_data
        """Отображает текущий опрос с кнопками навигации"""

        add = {
            "<": "prevdell" if self.current_index > 0 else None,
            ">": "nextdell" if self.current_index < len(surveys_items) - 1 else None
        }

        # Убираем ключи с значением None
        add = {key: value for key, value in add.items() if value is not None}
        if 'Редактировать опрос' in self.state_stack:
            add['edit'] = {
                "Изменить тип": "Изменить тип",
                "Изменить дату тренировки/игры": "Изменить дату тренировки/игры",
                "Изменить время тренировки/игры": "Изменить время тренировки/игры",
                "Изменить адрес": "Изменить адрес",
                "Изменить цену": "Изменить цену",
                "Изменить получателей": "Изменить получателей",
                "Изменить дату отправки опроса": "Изменить дату отправки опроса",
                "Изменить время отправки опроса": "Изменить время отправки опроса",
            }
        elif 'Редактировать напоминание' in self.state_stack:
            add['edit'] = {
                "Изменить дату отправки напоминания": "Изменить дату отправки напоминания",
                "Изменить время отправки напоминания": "Изменить время отправки напоминания",
                "Изменить текст напоминания": "Изменить текст напоминания",
                "Изменить получателей напоминания": "Изменить получателей напоминания"
            }
        elif 'Удалить опрос' in self.state_stack:
            add['end'] = {"Назад": "cancellation", "Удалить опрос": "save_dell_survey"}
        await self.edit_message(buttons=add, buttons_row=3)

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

    async def reminder(self):
        buttons_name = ["Новое напоминание", "Удалить напоминание", "Редактировать напоминание",
                        "Результаты напоминаний"]
        buttons = {name: name for name in buttons_name}
        await self.edit_message(buttons=buttons)

    async def receipts_reminder(self):
        self.state_stack['Выбор получателей'] = self.receipts_reminder
        buttons_name = ["Команды", "Пользователи"]
        buttons = {name: name for name in buttons_name}
        await self.edit_message(buttons=buttons)


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
