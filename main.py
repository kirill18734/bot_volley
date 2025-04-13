from copy import deepcopy
from time import sleep

from telebot.async_telebot import AsyncTeleBot
from telebot.types import BotCommand, InlineKeyboardMarkup, InlineKeyboardButton
import calendar
import uuid
from datetime import datetime
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
                    "Дата отправки опроса": self.process_buttons,
                    "Время отправки опроса": self.process_buttons,
                    "Получатели опроса": self.process_buttons
                }

            else:
                original_keys = {
                    "Новое напоминание": self.process_buttons,
                    "Дата отправки напоминания": self.process_buttons,
                    "Время отправки напоминания": self.process_buttons,
                    "Текст напоминания": self.process_buttons,
                    "Выбор получателей": self.process_buttons,
                }
                if "Команда" in self.state_stack:
                    original_keys["Команда"] = self.process_buttons
                if "Пользователи" in self.state_stack:
                    original_keys["Команда"] = self.process_buttons

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

        response_text = f"Вы находитесь в разделе: {response_text.replace('- <u>Главное меню</u>', '<u>Главное меню</u>').replace('admins', 'Админы').replace('Изменить получателей нап', 'Изменить получателей напоминания')}"
        if len(self.state_stack) > 3:
            if any(state in list(self.state_stack.keys())[-2] for state in ['Открыть доступ']):
                response_text += f"\n\nНапишите Ник и id пользователя для добавления через двоеточие, пример:\n Вася:2938214371 или Петя:@petya (можно без @). \nТакже можно добавлять списком нескольких пользователей через запятую, пример:\nВася:2938214371, Петя:@petya, Lena:lenusik"
            if any(state in list(self.state_stack.keys())[-2] for state in ['Добавить статистику', 'Добавить видео']):
                response_text += f"\n\nНапишите название  и ссылку для добавления через двоеточие, пример:\nСезон 2024-2025:https://disk.yandex.ru/d/bWFMzczzg\nТакже можно добавлять списком несколько ссылок через запятую, пример:\nСезон 2024-2025:https://disk.yandex.ru/d/bWFMzczzg, Сезон 2025-2026:https://disk.yandex.ru/d/bW343Mzczzg"

        if self.user_data:
            text = 'surveys' if any(state in self.state_stack for state in
                                    ['Редактировать опрос', 'Удалить опрос', 'Результаты опросов',
                                     'Новый опрос']) else 'reminder'
            data = await storage.load_data()
            text_ = 'Напоминание' if text == 'reminder' else 'Опрос'
            if any(state in self.state_stack for state in
                   ['Редактировать опрос', 'Редактировать напоминание', 'Удалить опрос', 'Удалить напоминание',
                    'Результаты опросов', 'Результаты напоминаний']):
                response_text += f"\n\n<b>{text_} {self.current_index + 1} из {len(data[text])}</b>\n\n"
            if any(state in self.state_stack for state in
                   ['Пользователи']):
                list_command = [command for command in data["commands"].keys() if
                                data["commands"][command]['users']] + [
                                   'Админы']
                response_text += f"\n\n<b>Команда: {list_command[self.current_index]}</b>\n\n"
            if any(state in self.state_stack for state in
                   ['Новый опрос', 'Новое напоминание', 'Удалить опрос', 'Удалить напоминание']):
                response_text += '\n\n' + "\n".join(f"{k}: {v}" for game_data in self.user_data.values() for k, v in
                                                    game_data.items() if k not in (
                                                        'Отметились', 'Количество отметившихся',
                                                        'id опроса',
                                                        'Получатели напоминания'))

            if any(state in self.state_stack for state in
                   ['Результаты опросов', 'Результаты напоминаний']):
                response_text += '\n\n' + "\n".join(f"{k}: {v}" for game_data in self.user_data.values() for k, v in
                                                    game_data.items() if k not in (
                                                        'id опроса', 'Получатели напоминания', 'Отметились'))
            if any(state in self.state_stack for state in
                   ['Редактировать опрос', 'Редактировать напоминание']):
                response_text += '\n\n' + "\n".join(f"{k}: {v}" for game_data in self.user_data.values() for k, v in
                                                    game_data.items() if k not in (
                                                        'Отметились', 'Количество отметившихся', 'id опроса',
                                                        'Опрос отправлен', 'Напоминание отправлено',
                                                        'Опрос открыт', 'Получатели напоминания'))

            if any(state in self.state_stack for state in
                   ['Пользователи', 'Команды']) and 'Новое напоминание' in self.state_stack:
                new_data = deepcopy(self.user_data[self.unique_id]['Получатели напоминания'])
                # Обновляем значения в словаре
                if type(new_data) != str:
                    for outer_key in new_data:
                        for inner_key in new_data[outer_key]:
                            value = new_data[outer_key][inner_key]
                            new_data[outer_key][inner_key] = value.split('_')[0]

                response_text += f"\nПолучатели напоминания:\n{await self.format_dict(new_data, base_indent=4)}\n" if type(
                    new_data) != str else f'\nПолучатели напоминания: {",".join(self.selected_list)}'

            if any(state in self.state_stack for state in
                   ['Результаты опросов']):
                new_data = deepcopy(self.user_data[self.unique_id]['Отметились'])
                # Обновляем значения в словаре
                if type(new_data) != str:
                    for outer_key in new_data:
                        for inner_key in new_data[outer_key]:
                            value = new_data[outer_key][inner_key]
                            new_data[outer_key][inner_key] = value.split('_')[0]

                response_text += f"\nОтметились:\n{await self.format_dict(new_data, base_indent=4)}\n" if type(
                    new_data) != str else f'\nОтметились: {",".join(self.selected_list)}'
            if any(state in self.state_stack for state in
                   ['Редактировать напоминание', 'Удалить напоминание',
                    'Результаты напоминаний']):
                new_data = deepcopy(self.user_data[self.unique_id]['Получатели напоминания'])
                # Обновляем значения в словаре
                if type(new_data) != str:
                    for outer_key in new_data:
                        for inner_key in new_data[outer_key]:
                            value = new_data[outer_key][inner_key]
                            new_data[outer_key][inner_key] = value.split('_')[0]

                response_text += f"\nПолучатели напоминания:\n{await self.format_dict(new_data, base_indent=4)}\n" if type(
                    new_data) != str else f'\nПолучатели напоминания: {new_data}'

        response_text += f"""\n\nИспользуй кнопки для навигации. Чтобы вернуться на шаг назад, используй команду /back. В начало /start """
        if 'Результаты опросов' not in self.state_stack and 'Результаты напоминаний' not in self.state_stack:
            response_text += f"""\n\nВыберите раздел {f'(интервал - {f"{self.hour}ч" if self.hour != 2.5 else "2ч30м"} )' if 'Дата тренировки/игры' in [k for game_data in self.user_data.values() for k, v in game_data.items()] and "Время тренировки/игры" not in [k for game_data in self.user_data.values() for k, v in game_data.items()] else ''}:"""

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
                    if 'Время тренировки/игры' in self.state_stack or 'Время отправки' in self.state_stack:
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
                self.user_data.clear()
                self.selected_list.clear()
                await self.block_control(message)
                return
            await self.show_start_menu(message)

        @bot.message_handler(commands=['back'])
        async def handle_back(message):
            await self.delete_message(message)
            self.admin = await access.check_access(message)
            if not self.admin['has_access']:
                self.user_data.clear()
                self.selected_list.clear()
                await self.block_control(message)
            elif 'Начать' in self.state_stack.keys() and self.keys:
                self.user_data.clear()
                self.selected_list.clear()
                self.keys.pop()
                await self.navigate()
                return
            await self.back_history(message)

        @bot.message_handler(
            func=lambda message: self.user_states.get(message.chat.id) in ("add"))
        async def get_description_reminder(message):
            if self.user_states.get(message.chat.id) == 'add':
                self.user_states.clear()
                await self.add_list(message)

        @bot.callback_query_handler(func=lambda call: True)
        async def handle_query(call):
            self.admin = await access.check_access(call.message)
            self.call = call
            if not self.admin['has_access']:
                self.user_data.clear()
                self.selected_list.clear()
                await self.block_control(call.message)
                return
            if 'Главное меню' not in list(self.state_stack.keys()):
                self.user_data.clear()
                self.selected_list.clear()
                await self.show_start_menu(call.message)
                return

            data = await storage.load_data()
            # Добавляем команды из data["commands"] и "Админы", все указывают на self.open
            extra_actions = {name: self.distribution_center for name in list(data["commands"].keys()) + ['admins']}
            if call.data in extra_actions:
                self.select_command = call.data
            actions = {
                "Управление": self.control_buttons,
                "Доступ к боту": self.main_control,
                "Открыть доступ": self.list_commands,
                "Закрыть доступ": self.list_commands,
                "Редактирование команд": self.edit_command,
                "Редактировать видео": self.edit_video,
                "Редактировать статистику": self.edit_statistic,
                "Добавить видео": self.list_commands,
                "Удалить видео": self.list_commands,
                "Добавить статистику": self.list_commands,
                "Удалить статистику": self.list_commands,
                "dell_data": self.dell_list,
                "Опрос": self.the_survey,
                "Новый опрос": self.typeplay,
                "Новое напоминание": self.generate_calendar,
                "save": self.save,
                "Удалить опрос": self.dell_edit_survey,
                "Удалить напоминание": self.dell_edit_survey,
                "cansel_survey": self.the_survey,
                "save_dell_survey": self.dell_list,
                "Редактировать опрос": self.dell_edit_survey,
                "Изменить тип": self.typeplay,
                "Изменить дату тренировки/игры": self.generate_calendar,
                "Изменить время тренировки/игры": self.generatetime,
                "Изменить адрес": self.distribution_center,
                "Изменить текст": self.distribution_center,
                "Изменить цену": self.getprice,
                "Изменить получателей опроса": self.selectsendsurvey,
                "Изменить дату отправки": self.generate_calendar,
                "Изменить время отправки": self.timesendsurvey,
                "Результаты опросов": self.dell_edit_survey,
                "Результаты напоминаний": self.dell_edit_survey,
                "Напоминание": self.reminder,
                "Команды": self.selectsendsurvey,
                "Пользователи": self.user_receipts_reminder,
                "Редактировать напоминание": self.dell_edit_survey,
                "Изменить получателей нап": self.receipts_reminder

            }
            # Объединяем словари
            actions = {**actions, **extra_actions}

            if self.call.data == 'cancellation':
                self.selected_list.clear()
                if all(key in self.state_stack for key in ['Команды', 'Редактировать напоминание']) or all(
                        key in self.state_stack for key in ['Пользователи', 'Редактировать напоминание']):
                    await self.pop_state(3)
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
                    elif any(key in self.state_stack for key in
                             ['Новый опрос', 'Редактировать опрос', 'Команды', 'Редактировать напоминание',
                              'Пользователи']):
                        if user_key in self.selected_list:
                            self.selected_list.remove(user_key)  # Убираем из списка
                        else:
                            self.selected_list.add(user_key)  # Добавляем в список
                        if 'Пользователи' in self.state_stack:
                            await self.user_receipts_reminder()
                            return
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
                    elif any(key in self.state_stack for key in ['Редактировать опрос', 'Редактировать напоминание']):
                        if 'Изменить дату тренировки/игры' in self.state_stack:
                            self.user_data[self.unique_id][
                                'Дата тренировки/игры'] = f"{int(day):02d}-{int(month):02d}-{year}"
                        elif 'Изменить дату отправки' in self.state_stack:
                            text = 'Дата отправки опроса' if 'Редактировать опрос' in self.state_stack else 'Дата отправки напоминания'
                            self.user_data[self.unique_id][
                                text] = f"{int(day):02d}-{int(month):02d}-{year}"

                        await self.save()
                elif call.data in ("Товарищеская игра", "Тренировка", "Игра"):
                    if 'Новый опрос' in self.state_stack:
                        self.user_data[self.unique_id]['Тип'] = f"{self.call.data}"
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
                            await self.selectsendsurvey()

                    elif any(key in self.state_stack for key in ['Редактировать опрос', 'Редактировать напоминание']):
                        if 'Изменить время тренировки/игры' in self.state_stack:
                            text = 'Время тренировки/игры'
                        elif all(key in self.state_stack for key in ['Изменить время отправки', 'Редактировать опрос']):
                            text = 'Время отправки опроса'
                        else:
                            text = 'Время отправки напоминания'

                        self.user_data[self.unique_id][text] = f"{time}"
                        await self.save()

                    elif 'Новое напоминание' in self.state_stack:
                        self.user_data[self.unique_id]['Время отправки напоминания'] = f"{time}"
                        self.state_stack["Время отправки напоминания"] = self.timesendsurvey
                        await self.distribution_center()

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
                        await self.generate_calendar()
                    elif 'Редактировать опрос' in self.state_stack:
                        self.user_data[self.unique_id]['Цена'] = f"{price}"
                        await self.save()

                elif self.call.data in ("nextdell", "prevdell"):
                    data = await storage.load_data()
                    """Отображает текущий опрос с кнопками навигации"""
                    text = 'surveys' if any(state in self.state_stack for state in
                                            ['Редактировать опрос', 'Удалить опрос',
                                             'Результаты опросов']) else 'reminder'
                    surveys_items = list(data[text].items())
                    direction = {"nextdell": 1, "prevdell": -1}[self.call.data]
                    new_index = self.current_index + direction
                    if 0 <= new_index < len(surveys_items):
                        self.current_index = new_index
                        await self.dell_edit_survey()

                elif self.call.data in ("mainnextedit", "mainprevedit"):
                    data = await storage.load_data()
                    """Отображает текущий опрос с кнопками навигации"""
                    surveys_items = [command for command in data["commands"].keys() if
                                     data["commands"][command]['users']] + [
                                        'admins']
                    direction = {"mainnextedit": 1, "mainprevedit": -1}[self.call.data]
                    new_index = self.current_index + direction
                    if 0 <= new_index < len(surveys_items):
                        self.current_index = new_index

                        await self.user_receipts_reminder()

            else:
                await self.back_history(call.message)

    async def control_buttons(self):
        buttons_name = ["Доступ к боту", "Опрос", "Напоминание", "Редактирование команд"]
        buttons = {name: name for name in buttons_name}
        await self.edit_message(buttons=buttons)

    async def main_control(self):
        buttons_name = ["Открыть доступ", "Закрыть доступ"]
        buttons = {name: name for name in buttons_name}
        await self.edit_message(buttons=buttons)

    async def list_commands(self):
        data = await storage.load_data()
        buttons_name = [key for key in data["commands"].keys()]
        buttons = {name: name for name in buttons_name}
        if any(key in self.state_stack for key in ['Открыть доступ', 'Закрыть доступ']):
            buttons['Админы'] = 'admins'
        await self.edit_message(buttons=buttons)

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

    async def timesendsurvey(self):
        time = [f"{hour:02}:{minute:02}" for hour in range(9, 24) for minute in [0, 30]]
        buttons = [[InlineKeyboardButton(key, callback_data=f"time_{key}") for key in time]]
        await self.edit_message(buttons=buttons)

    async def typeplay(self):
        if 'Новый опрос' in self.state_stack:
            self.user_data.clear()
            self.unique_id = str(uuid.uuid4())
            self.user_data[self.unique_id] = {}

        buttons_name = ["Игра", "Тренировка", "Товарищеская игра"]
        buttons = {name: name for name in buttons_name}
        await self.edit_message(buttons=buttons)

    async def distribution_center(self):
        if any(key in self.state_stack for key in ['Закрыть доступ', 'Удалить видео', 'Удалить статистику']):
            await self.close()
        elif any(key in self.state_stack for key in
                 ['Добавить видео', 'Добавить статистику', 'Открыть доступ', 'Редактировать опрос',
                  "Время тренировки/игры", 'Время отправки напоминания', 'Редактировать напоминание']):
            # Редактируем текущее сообщение, чтобы запросить имя сотрудника
            self.user_states[self.call.message.chat.id] = "add"
            await self.edit_message()

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

    async def add_list(self, message):
        if message.text in ['/back', '/start']:
            return

        if 'Новый опрос' in self.state_stack:
            self.user_data[self.unique_id]['Адрес'] = message.text
            self.state_stack['Адрес'] = self.edit_message
            await self.delete_message(message)
            await self.getprice()
            return

        if 'Новое напоминание' in self.state_stack:
            self.user_data[self.unique_id]['Текст напоминания'] = message.text
            self.state_stack['Текст напоминания'] = self.edit_message
            await self.delete_message(message)
            await self.receipts_reminder()
            return

        if any(key in self.state_stack for key in ['Добавить видео', 'Добавить статистику', 'Открыть доступ']):
            mode = next(
                k for k in ['Добавить видео', 'Добавить статистику', 'Открыть доступ'] if k in self.state_stack)
            parsed, errors = await access.parse_kv_input(message.text, mode)

            if not parsed and errors:
                response_test = 'Некорректное добавление, ознакомьтесь с примерами и попробуйте еще раз.'
            else:
                data = await storage.load_data()
                priorities = {
                    'Добавить видео': 'Видео',
                    'Добавить статистику': 'Статистика',
                    'Открыть доступ': "users"
                }
                section = priorities[mode]

                for name, value in parsed:
                    if self.select_command != 'admins':
                        if name not in data["commands"][self.select_command][section] and value not in \
                                data["commands"][self.select_command][section].values():
                            data["commands"][self.select_command][section][name] = value
                    else:
                        if name not in data[self.select_command] and value not in data[
                            self.select_command].values():
                            data[self.select_command][name] = value

                await storage.write_data(data)

                if errors:
                    error_ids = [str(e[0]) for e in errors]
                    response_test = f"Некорректное добавление некоторых данных. Проблемные элементы: {', '.join(error_ids)}."
                else:
                    response_test = 'Успешно добавлено.'

            await bot.answer_callback_query(self.call.id, response_test, show_alert=True)
            await self.delete_message(message)
            await self.back_history(message)
            return

        if any(key in self.state_stack for key in ['Редактировать опрос', 'Редактировать напоминание']):
            text = 'Адрес' if 'Редактировать опрос' in self.state_stack else 'Текст напоминания'
            self.user_data[self.unique_id][text] = message.text
            await self.delete_message(message)
            await self.save()
            return

        # Если не попало ни в один кейс
        response_test = 'Некорректное добавление, ознакомьтесь с примерами и попробуйте еще раз'
        await bot.answer_callback_query(self.call.id, response_test, show_alert=True)
        await self.delete_message(message)
        await self.back_history(message)

    async def close(self):
        data = await storage.load_data()

        keys_mapping = {
            'Удалить видео': 'Видео',
            'Удалить статистику': 'Статистика'
        }

        text = next((value for key, value in keys_mapping.items() if key in self.state_stack), 'Закрыть доступ')

        if text == 'Закрыть доступ':
            if self.select_command == 'admins':
                get_data = data['admins'].items()
            else:
                get_data = data["commands"][self.select_command]["users"].items()

        else:
            get_data = data["commands"][self.select_command][text].items()

        if not get_data:
            self.state_stack.popitem()
            response_text = f'Пользователи отсутствуют' if text == 'Закрыть доступ' else 'Ссылки отсутствуют'
            self.user_data.clear()
            self.selected_list.clear()
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

        add['Удалить'] = {'Отмена!': 'cancellation', "🗑️ Удалить": 'dell_data'}
        if 'Закрыть доступ' in self.state_stack:
            add['Удалить'] = {"Отмена!": 'cancellation', '🔒 Закрыть доступ!': 'dell_data'}

        await self.edit_message(buttons=add)

    async def pop_state(self, count=1):
        """Удаляет последние count элементов из state_stack"""
        self.state_stack = dict(list(self.state_stack.items())[:-count])

    async def finish_deletion(self, message, data, response_text):
        """Сохраняет данные, очищает выбор, показывает сообщение и возвращается в меню"""
        try:
            await bot.answer_callback_query(self.call.id, response_text, show_alert=True)
            await storage.write_data(data)
        except Exception as e:
            print("Ошибка при завершении удаления: {e}")
        await self.back_history(message)
        self.selected_list.clear()

    async def dell_list(self):
        data = await storage.load_data()

        try:
            if self.select_command and self.selected_list:

                if 'Закрыть доступ' in self.state_stack:
                    # Проверка: нельзя удалить всех админов
                    if self.select_command == 'admins':
                        if len(data['admins']) <= len(self.selected_list):
                            text = 'пользователи НЕ УДАЛЕНЫ' if len(
                                self.selected_list) > 1 else 'пользователь НЕ УДАЛЕН'
                            await bot.answer_callback_query(self.call.id,
                                                            f'Должен быть минимум 1 админ, {text}', show_alert=True)
                            await self.pop_state(2)
                            await self.back_history(self.call.message)
                            return

                        # Удаление админов
                        data['admins'] = {
                            k: v for k, v in data['admins'].items()
                            if str(v).split('_')[0] not in self.selected_list
                        }

                    else:
                        # Удаление пользователей из команды
                        users = data["commands"][self.select_command]["users"]
                        data["commands"][self.select_command]["users"] = {
                            k: v for k, v in users.items()
                            if str(v).split('_')[0] not in self.selected_list
                        }

                    await self.pop_state(2)
                    response = 'Пользователи заблокированы' if len(
                        self.selected_list) > 1 else 'Пользователь заблокирован'
                    await self.finish_deletion(self.call.message, data, response)

                elif 'Редактирование команд' in self.state_stack:
                    section = 'Видео' if 'Удалить видео' in self.state_stack else 'Статистика'
                    command_section = data["commands"][self.select_command][section]

                    for key in self.selected_list:
                        command_section.pop(key, None)

                    await self.pop_state(2)
                    response = 'Ссылки удалены' if len(self.selected_list) > 1 else 'Ссылка удалена'
                    await self.finish_deletion(self.call.message, data, response)

            elif any(k in self.state_stack for k in ['Удалить опрос', 'Удалить напоминание']):
                section = 'surveys' if 'Удалить опрос' in self.state_stack else 'reminder'
                surveys_items = list(data.get(section, {}).items())

                if self.current_index < len(surveys_items):
                    key_to_delete = surveys_items[self.current_index][0]
                    del data[section][key_to_delete]

                await storage.write_data(data)

                response = 'Опрос удален' if section == 'surveys' else 'Напоминание удалено'
                await bot.answer_callback_query(self.call.id, response, show_alert=True)

                # Обновляем стек состояний
                await self.pop_state(1 if len(surveys_items) > 1 else 2)
                self.current_index = 0
                await self.back_history(self.call.message)

            else:
                await self.pop_state(2)
                await self.back_history(self.call.message)
            self.selected_list.clear()
        except Exception as e:
            await bot.answer_callback_query(self.call.id, "Произошла ошибка при удалении.", show_alert=True)
            await self.back_history(self.call.message)

    async def generate_calendar(self, year=None, month=None):
        if 'Новое напоминание' in self.state_stack:
            self.user_data.clear()
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
        users = list(data["commands"].keys()) + ["Админы"]
        # Название кнопки в зависимости от состояния
        is_survey = any(state in self.state_stack for state in ["Новый опрос", "Редактировать опрос"])
        button_name = "Получатели опроса" if is_survey else "Получатели напоминания"
        if button_name not in self.user_data[self.unique_id]:
            self.user_data[self.unique_id][button_name]
        if type(self.user_data[self.unique_id][button_name]) != str:
            self.selected_list.clear()
            self.user_data[self.unique_id][button_name] = ''
        # Формируем кнопки для выбора получателей
        toggle_buttons = {
            f"{'✅' if key in self.selected_list else '❌'} {key}": f"toggle_{key}"
            for key in users
        }

        self.user_data[self.unique_id][button_name] = ','.join(self.selected_list) if self.selected_list else ''

        # Кнопки завершения
        final_label = "Запланировать" if is_survey or "Новое напоминание" in self.state_stack else "Изменить"
        action_buttons = {"Отмена": "cancellation", final_label: "save"}

        # Объединяем кнопки
        buttons = {**toggle_buttons, 'end': action_buttons}

        # Показываем меню
        await self.edit_message(buttons=buttons)

    async def save(self):
        data = await storage.load_data()
        response_text = None
        if 'Новый опрос' in self.state_stack:
            self.user_data[self.unique_id].update({
                'Опрос открыт': "Нет",
                'Опрос отправлен': "Нет",
                'Количество отметившихся': 0,
                'Отметились': {},
                'id опроса': 0
            })

            list_user_data = [k for game_data in self.user_data.values() for k, v in game_data.items()] + [
                'Новый опрос']
            for i in list_user_data:
                if i in self.state_stack:
                    try:
                        del self.state_stack[i]
                    except:
                        continue
                # Добавляем данные правильно (без .values())
            data["surveys"][self.unique_id] = self.user_data[self.unique_id]
            await self.pop_state(1)
            response_text = 'Опрос запланирован'
        elif 'Редактировать опрос' in self.state_stack or 'Редактировать напоминание' in self.state_stack:
            text = 'surveys' if 'Редактировать опрос' in self.state_stack else 'reminder'
            data[text][self.unique_id] = self.user_data[self.unique_id]
            await self.pop_state(1 if 'Изменить получателей нап' not in self.state_stack else 4)
            response_text = 'Изменено'
        elif 'Новое напоминание' in self.state_stack:
            self.user_data[self.unique_id]['Напоминание отправлено'] = "Нет"
            list_user_data = [k for game_data in self.user_data.values() for k, v in game_data.items()] + [
                'Новое напоминание', 'Выбор получателей', 'Команды', 'Пользователи', 'save']

            for i in list_user_data:
                if i in self.state_stack:
                    try:
                        del self.state_stack[i]
                    except:
                        continue
                # Добавляем данные правильно (без .values())
            data["reminder"][self.unique_id] = self.user_data[self.unique_id]
            response_text = 'Напоминание запланировано'
        # Сохраняем обновленные данные обратно в файл
        await bot.answer_callback_query(self.call.id, response_text, show_alert=True)
        self.user_data.clear()
        self.selected_list.clear()
        await storage.write_data(data)
        await self.back_history(self.call.message)

    async def dell_edit_survey(self):
        self.user_data.clear()
        self.selected_list.clear()
        data = await storage.load_data()

        text = 'surveys' if any(state in self.state_stack for state in
                                ['Редактировать опрос', 'Удалить опрос', 'Результаты опросов']) else 'reminder'
        surveys_items = list(data.get(text, {}).items())

        # Если нет ни одного опроса/напоминания
        if not surveys_items:
            response_text = f'Нет доступных {"опросов" if text == "surveys" else "напоминаний"}.'
            await self.pop_state(1)
            await bot.answer_callback_query(self.call.id, response_text, show_alert=True)
            return

        # Безопасно выставляем индекс
        self.current_index = max(0, min(self.current_index, len(surveys_items) - 1))
        surveys_key, user_data = surveys_items[self.current_index]
        self.unique_id = surveys_key
        self.user_data[surveys_key] = user_data
        # Подгружаем выбранных получателей

        if any(key in self.state_stack for key in ['Редактировать опрос', 'Команды', 'Редактировать напоминание']):
            key_name = 'Получатели опроса' if 'Редактировать опрос' in self.state_stack else 'Получатели напоминания'
            receivers = self.user_data[self.unique_id].get(key_name)
            if isinstance(receivers, dict):
                # Рекурсивно собрать всех "имен" из вложенного словаря
                self.selected_list.update(
                    {f"{user}_{value}" if isinstance(value, str) else user
                     for command_data in receivers.values()
                     for user, value in command_data.items()}
                )
            elif isinstance(receivers, str):
                self.selected_list.update(receivers.split(','))

        # Сборка кнопок
        buttons = {}
        if self.current_index > 0:
            buttons["<"] = "prevdell"
        if self.current_index < len(surveys_items) - 1:
            buttons[">"] = "nextdell"

        if 'Редактировать опрос' in self.state_stack:
            buttons['edit'] = {
                "Изменить тип": "Изменить тип",
                "Изменить дату тренировки/игры": "Изменить дату тренировки/игры",
                "Изменить время тренировки/игры": "Изменить время тренировки/игры",
                "Изменить адрес": "Изменить адрес",
                "Изменить цену": "Изменить цену",
                "Изменить дату отправки опроса": "Изменить дату отправки",
                "Изменить время отправки опроса": "Изменить время отправки",
                "Изменить получателей опроса": "Изменить получателей опроса"
            }

        elif 'Редактировать напоминание' in self.state_stack:
            buttons['edit'] = {
                "Изменить дату отправки напоминания": "Изменить дату отправки",
                "Изменить время отправки напоминания": "Изменить время отправки",
                "Изменить текст напоминания": "Изменить текст",
                "Изменить получателей напоминания": "Изменить получателей нап"
            }

        elif 'Удалить опрос' in self.state_stack or 'Удалить напоминание' in self.state_stack:
            kind = 'опрос' if text == 'surveys' else 'напоминание'
            buttons['end'] = {
                "Назад": "cancellation",
                f"Удалить {kind}": "save_dell_survey"
            }

        await self.edit_message(buttons=buttons, buttons_row=3)

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

    async def user_receipts_reminder(self):
        data = await storage.load_data()
        list_command = [cmd for cmd in data["commands"] if data["commands"][cmd]['users']] + ['Админы']

        if not list_command or self.current_index >= len(list_command) or self.current_index < 0:
            self.current_index = 0

        command = list_command[self.current_index]

        users = (data["commands"][command]['users'] if command != 'Админы' else data["admins"])
        users = {username: value for username, value in users.items()}
        if type(self.user_data[self.unique_id]['Получатели напоминания']) == str:
            self.user_data[self.unique_id]['Получатели напоминания'] = {}
        reminder_data = self.user_data[self.unique_id].setdefault('Получатели напоминания', {})
        command_data = reminder_data.setdefault(command, {})

        for user, value in users.items():
            key = f"{user}_{value}"
            if key in self.selected_list:
                command_data[user] = value
            else:
                command_data.pop(user, None)

        if not command_data:
            reminder_data.pop(command, None)

        buttons = {
            f"{'✅' if f'{user}_{value}' in self.selected_list else '❌'} {user} ({str(value).split('_')[0]})": f"toggle_{user}_{value}"
            for user, value in users.items()
        }

        buttons['end'] = {
            "<": "mainprevedit" if self.current_index > 0 else None,
            ">": "mainnextedit" if self.current_index < len(list_command) - 1 else None
        }
        buttons['end'] = {k: v for k, v in buttons['end'].items() if v is not None}
        buttons['Закрыть'] = {'Отмена!': 'cancellation', '💾 Сохранить!': 'save'}

        await self.edit_message(buttons=buttons, buttons_row=3)


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
    while True:
        try:
            asyncio.run(main())
        except:
            print('Возникла ошибка:')
            sleep(10)
            continue
