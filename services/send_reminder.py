from datetime import datetime
from telebot.async_telebot import AsyncTeleBot

from config.config import config
from core.storage import storage

bot = AsyncTeleBot(config.BOT_TOKEN, parse_mode='HTML')


async def send_reminder():
    while True:
        try:
            data = await storage.load_data()
            for survey_id, survey_data in data['reminder'].items():

                target_date = datetime.strptime(
                    f"{survey_data.get('Дата отправки напоминания')} {survey_data.get('Время отправки напоминания')}",
                    "%d-%m-%Y %H:%M")
                current_date = datetime.now().replace(second=0, microsecond=0)
                command_list = survey_data.get('Получатели напоминания')

                if survey_data.get('Текст напоминания') and target_date == current_date and survey_data.get(
                        'Напоминание отправлено') == 'Нет':
                    if type(command_list) == str:
                        users = set([
                                        str(user).split('_')[-1]
                                        for command in str(command_list).split(',')
                                        if command != 'Админы'
                                        for user in data['commands'][command]['users'].values()
                                    ] + [str(user).split('_')[-1] for command in str(command_list).split(',') if
                                         command == 'Админы' for user in data['admins'].values()])

                        for user in users:
                            try:
                                response_text = survey_data.get('Текст напоминания')
                                await bot.send_message(user, response_text)
                            except:
                                pass
                        survey_data['Напоминание отправлено'] = "Да"
                        await storage.write_data(data)

                    else:

                        users = set([user for command in command_list.keys() for keys, user in
                                     command_list[command].items()])
                        for user in users:
                            try:
                                response_text = survey_data.get('Текст напоминания')
                                await bot.send_message(user, response_text)
                            except:
                                pass

                        survey_data['Напоминание отправлено'] = "Да"
                        await storage.write_data(data)
        except:
            pass
