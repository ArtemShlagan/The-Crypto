import os
import asyncio
import logging
import re
from telethon import TelegramClient
from telethon.tl.types import MessageEntityUrl
from telethon.tl.types import (
    MessageMediaPhoto,
    MessageMediaDocument,
    MessageEntityTextUrl
)
from telethon.errors import SessionPasswordNeededError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('MyCopiRobot')

api_id = '23415626'
api_hash = '84407a767ffbbd9ce175bb9dba5948f2'

channel_pairs = [
    ('@crypto_sekta', -1002188335470),
    ('@trade001k', -1002188335470),
    ('@kripota4', -1002188335470),
    ('@cryptogram_web3', -1002188335470),
]

session_path = os.getenv('SESSION_PATH', 'session_name')
phone_number = +380930290555

client = TelegramClient(session_path, api_id, api_hash)
sent_messages = {}

def remove_all_link_lines(message):
    text = message.raw_text or ""
    if not text:
        return text

    lines = text.split('\n')
    
    # Регулярка для пошуку будь-якого URL (http, https, www, t.me тощо)
    link_pattern = re.compile(r'(https?://\S+|http?://\S+|www\.\S+|t\.me/\S+)', re.IGNORECASE)

    lines_to_remove = set()
    removed_any = False  # прапорець для відслідковування видалення хоча б одного рядка

    # 1) Видаляємо рядки з inline-посиланнями (Telethon позначає їх як MessageEntityTextUrl або MessageEntityUrl)
    if message.entities:
        for entity in message.entities:
            if isinstance(entity, (MessageEntityTextUrl, MessageEntityUrl)):
                offset = entity.offset
                total = 0
                for i, line in enumerate(lines):
                    line_length = len(line)
                    if offset >= total and offset < total + line_length:
                        lines_to_remove.add(i)
                        removed_any = True
                        break
                    total += line_length + 1  # +1 для символу нового рядка

    # 2) Видаляємо рядки з прямих посилань
    for i, line in enumerate(lines):
        if re.search(link_pattern, line):
            lines_to_remove.add(i)
            removed_any = True

    # 3) Формуємо новий текст з "хороших" рядків
    new_lines = [line for i, line in enumerate(lines) if i not in lines_to_remove]
    new_text = "\n".join(new_lines).strip()

    # Якщо хоча б один рядок було видалено, додаємо інлайн-ссилку з HTML форматуванням
    if removed_any:
        inline_link = '<a href="https://t.me/+gOxTz-7iTuhlYThi">The Crypto Currency</a>'
        if new_text:
            new_text += "\n" + inline_link
        else:
            new_text = inline_link

    return new_text

async def process_message(message, source_channel, target_channel):
    if message.id in sent_messages.get(target_channel, []):
        return

    text = remove_all_link_lines(message)

    media_files = []
    if message.media:
        if isinstance(message.media, MessageMediaPhoto):
            media_files.append(message.photo)
        elif isinstance(message.media, MessageMediaDocument):
            media_files.append(message.document)

    try:
        if media_files:
            await client.send_file(target_channel, media_files[0], caption=text, parse_mode='html')
        else:
            await client.send_message(target_channel, text, parse_mode='html')
        logger.info(f"Сообщення {message.id} відправлено в {target_channel}")
        sent_messages.setdefault(target_channel, []).append(message.id)
    except Exception as e:
        logger.error(f"Помилка відправки повідомлення в {target_channel}: {e}")

async def main():
    try:
        if phone_number:
            await client.start(phone_number)
        else:
            await client.start()
    except SessionPasswordNeededError:
        logger.error("Необхідний пароль для входу в аккаунт")
        return
    except Exception as e:
        logger.error(f"Помилка аутентифікації: {e}")
        return

    last_message_ids = {source: None for source, target in channel_pairs}

    while True:
        for source_channel, target_channel in channel_pairs:
            if last_message_ids[source_channel] is None:
                async for message in client.iter_messages(source_channel, limit=1):
                    last_message_ids[source_channel] = message.id

            async for message in client.iter_messages(source_channel, min_id=last_message_ids[source_channel]):
                if message:
                    last_message_ids[source_channel] = message.id
                    await process_message(message, source_channel, target_channel)

        await asyncio.sleep(30)

if __name__ == '__main__':
    asyncio.run(main())
