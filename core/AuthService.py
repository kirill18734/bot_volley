from core.storage import storage
import re
from typing import List, Tuple, Union


class AuthService:
    async def check_access(self, message):
        """Проверяет права доступа пользователя"""
        data = await storage.load_data()

        admins = [str(v).replace('@', '').split('_')[0] for v in data["admins"].values()]
        users = [str(name).replace('@', '').split('_')[0]
                 for command in data["commands"].values()
                 for name in command["users"].values()]

        username = str(message.chat.username).replace('@', '')
        user_id = message.chat.id
        access_info = {
            'is_admin': any(user in admins for user in [user_id, username]),
            'is_user': any(user in users for user in [user_id, username]),
            'has_access': any(user in admins + users for user in [user_id, username])
        }

        # Обновляем данные пользователей при необходимости
        if access_info['is_admin'] or access_info['is_user']:
            await self._update_user_ids(data, user_id, username)

        return access_info

    async def _update_user_ids(self, data, user_id: int, username: str):
        """Обновляет ID пользователей в хранилище"""
        updated = False
        username = str(username).replace('@', '')

        # Для админов
        for key, value in data["admins"].items():
            if value.replace("@", '') in (username, str(user_id)) and len(value.split('_')) == 1:
                data["admins"][key] = f"{value}_{user_id}"
                updated = True

        # Для обычных пользователей
        for command in data["commands"].values():
            for key, value in command["users"].items():
                if value.replace("@", '') in (username, str(user_id)) and len(value.split('_')) == 1:
                    command["users"][key] = f"{value}_{user_id}"
                    updated = True

        if updated:
            await storage.write_data(data)

    async def parse_kv_input(self, text: str, mode: str):
        items = [item.strip() for item in text.replace('\n', ',').split(',') if item.strip()]
        result = []
        errors = []

        for idx, item in enumerate(items, start=1):
            if ':' not in item:
                errors.append((idx, item, "нет двоеточия"))
                continue

            key, value = map(str.strip, item.split(':', 1))
            if not key:
                errors.append((idx, item, "пустой ключ"))
                continue
            if not value:
                errors.append((idx, item, "пустое значение"))
                continue

            if mode == 'Открыть доступ':
                if not re.match(r"^@?[a-zA-Z0-9_]+$|^\d{6,15}$", value):
                    errors.append((idx, item, "невалидный ID или username"))
                    continue
            else:
                if not re.match(r'^https?://[^\s]+$', value):
                    errors.append((idx, item, "невалидная ссылка"))
                    continue

            result.append((key, value))

        return result, errors


access = AuthService()
