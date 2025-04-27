import asyncio
from datetime import datetime, timedelta
from telebot.async_telebot import AsyncTeleBot
from config import config
from core.storage import storage

bot = AsyncTeleBot(config.BOT_TOKEN, parse_mode='HTML')


async def get_users(command_list, data):
    if isinstance(command_list, str):
        return set(
            str(user).split('_')[-1]
            for command in command_list.split(',')
            for user in (
                    data['commands'].get(command, {}).get('users', {}).values() if command != 'Админы' else data['Админы'].values()
            )
        )
    else:
        return set(
            str(user).split('_')[-1]
            for command in command_list.keys()
            for user in command_list[command].values()
        )


async def send_reminder():
    try:
        data = await storage.load_data()
        current_date = datetime.now().replace(second=0, microsecond=0)

        for survey_id, survey_data in data['reminder'].items():
            target_date = datetime.strptime(
                f"{survey_data.get('Дата отправки напоминания')} {survey_data.get('Время отправки напоминания')}",
                "%d-%m-%Y %H:%M"
            )

            if survey_data.get('Текст напоминания') and target_date == current_date and survey_data.get(
                    'Напоминание отправлено') == 'Нет':
                users = await get_users(survey_data.get('Получатели напоминания'), data)

                await asyncio.gather(
                    *(bot.send_message(user, survey_data.get('Текст напоминания')) for user in users)
                )

                survey_data['Напоминание отправлено'] = "Да"
                await storage.write_data(data)
    except Exception as e:
        print(f"Ошибка в send_reminder: {e}")


async def send_survey():
    try:
        data = await storage.load_data()
        current_date = datetime.now().replace(second=0, microsecond=0)

        for survey_id, survey_data in data['surveys'].items():
            if survey_data.get('Получатели опроса'):
                users = await get_users(survey_data.get('Получатели опроса'), data)

                if users:
                    target_date = datetime.strptime(
                        f"{survey_data.get('Дата отправки опроса')} {survey_data.get('Время отправки опроса')}",
                        "%d-%m-%Y %H:%M"
                    )

                    target_date2 = datetime.strptime(
                        f"{survey_data.get('Дата тренировки/игры')} {survey_data.get('Время тренировки/игры').split(' - ')[0]}",
                        "%d-%m-%Y %H:%M"
                    ) - timedelta(minutes=30)

                    day_index = config.WEEK_DAYS[target_date2.weekday()]

                    if target_date == current_date and target_date2 >= current_date and survey_data.get(
                            'Опрос отправлен') == 'Нет':
                        question = f"{survey_data.get('Тип')} {survey_data.get('Дата тренировки/игры')} ({day_index}) c {survey_data.get('Время тренировки/игры').replace(' - ', ' до ')} стоймость {survey_data.get('Цена')}р .\nАдрес: {survey_data.get('Адрес')}"

                        poll_message = await asyncio.gather(
                            *(bot.send_poll(
                                chat_id=user,
                                question=question,
                                options=["Буду", "+1"],
                                close_date=target_date2,
                                is_anonymous=False,
                                allows_multiple_answers=False,
                                explanation_parse_mode='HTML'
                            ) for user in users)
                        )

                        survey_data['Опрос отправлен'] = "Да"
                        survey_data["Опрос открыт"] = "Да"
                        survey_data['id опроса'] = poll_message[0].poll.id

                        await storage.write_data(data)
                    elif target_date2 <= current_date and 'Да' in (
                            survey_data.get('Опрос открыт'), survey_data.get('Опрос отправлен')):
                        survey_data["Опрос открыт"] = "Нет"
                        await storage.write_data(data)

    except Exception as e:
        print(f"Ошибка в send_survey: {e}")


async def run_service():
    while True:
        await send_reminder()
        await send_survey()
        await asyncio.sleep(60)  # Ждем 1 минуту перед следующим запуском
