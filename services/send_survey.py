from datetime import datetime, timedelta
from telebot.async_telebot import AsyncTeleBot
from core.storage import storage

from config.config import config

bot = AsyncTeleBot(config.BOT_TOKEN, parse_mode='HTML')


async def send_survey():
    while True:
        try:
            data = await storage.load_data()
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

                        current_date = datetime.now().replace(second=0, microsecond=0)
                        poll_message = None
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

                                except Exception as e:
                                    print(f"Ошибка при отправке опроса пользователю {user}: {e}")

                            survey_data['Опрос отправлен'] = "Да"
                            survey_data["Опрос открыт"] = "Да"
                            survey_data['id опроса'] = poll_message.poll.id
                            await storage.write_data(data)

                        # опрос автоматически закрывается, когда наступает время закрытие, то изменяем также значения
                        elif target_date2 <= current_date and 'Да' in (
                                survey_data.get('Опрос открыт'), survey_data.get('Опрос отправлен')):
                            survey_data["Опрос открыт"] = "Нет"
                            await storage.write_data(data)

        except:
            pass
