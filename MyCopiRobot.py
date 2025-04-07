import os
import asyncio
import logging
import re
from telethon import TelegramClient
from telethon.tl.types import (
    MessageEntityUrl,
    MessageEntityTextUrl,
    MessageMediaPhoto,
    MessageMediaDocument
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
    """
    Проверяем, нужно ли удалять какие-то строки (есть ли ссылки на t.me или инлайн-ссылки).
    Если ничего удалять не нужно, вернём (original_text, False).
    Если что-то удалили, вернём (modified_text, True).
    
    Обратите внимание, что если ссылок t.me и инлайн-ссылок нет, мы НЕ трогаем сообщение.
    """
    text = message.raw_text or ""
    if not text:
        return text, False

    lines = text.split('\n')
    lines_to_remove = set()
    removed_any = False

    # Шаблон для прямых ссылок на Telegram
    telegram_link_pattern = re.compile(r'(?:https?://)?(?:www\.)?t\.me/\S+', re.IGNORECASE)

    # 1) Проверяем inline-ссылки (MessageEntityTextUrl / MessageEntityUrl), удаляем строку,
    #    только если это t.me.
    if message.entities:
        for entity in message.entities:
            offset = entity.offset
            total = 0
            for i, line in enumerate(lines):
                line_length = len(line)
                if offset >= total and offset < total + line_length:
                    # Если это цитата (начинается с '>'), не трогаем — как пример, вдруг захотите.
                    # Но можно и удалять цитаты, если нужно.
                    if not line.lstrip().startswith('>'):
                        # Проверяем, действительно ли это t.me:
                        if isinstance(entity, MessageEntityTextUrl):
                            # Это всегда «кликабельная» ссылка, удаляем строку без разбора
                            # или можно проверить URL из entity.url, если хотите.
                            # Но обычно TextUrl = любая ссылка.
                            # Если хотите удалять только t.me, тогда сравните entity.url
                            # с регуляркой.
                            pass
                            # Чтобы удалять только t.me, раскомментируйте:
                            # if re.search(telegram_link_pattern, entity.url):
                            lines_to_remove.add(i)
                            removed_any = True

                        elif isinstance(entity, MessageEntityUrl):
                            url_text = text[entity.offset: entity.offset + entity.length]
                            # Удаляем строку, только если t.me
                            if re.search(telegram_link_pattern, url_text):
                                lines_to_remove.add(i)
                                removed_any = True
                    break
                total += line_length + 1

    # 2) Проверяем прямые ссылки вида t.me/... (не как сущности, а просто текст).
    for i, line in enumerate(lines):
        if i not in lines_to_remove:
            # Если это цитата — решите сами, удалять или нет.
            if not line.lstrip().startswith('>'):
                if re.search(telegram_link_pattern, line):
                    lines_to_remove.add(i)
                    removed_any = True

    # Если ничего не удаляли, просто возвращаем исходный текст
    if not removed_any:
        return text, False

    # Иначе убираем строки
    new_lines = [line for i, line in enumerate(lines) if i not in lines_to_remove]
    new_text = "\n".join(new_lines).strip()
    return new_text, True

async def process_message(message, source_channel, target_channel):
    # Не отправляем повторно одно и то же сообщение
    if message.id in sent_messages.get(target_channel, []):
        return

    # Сначала проверяем, нужно ли вообще что-то чистить
    modified_text, removed_any = remove_all_link_lines(message)

    if not removed_any:
        # Если никаких "вредных" ссылок нет, просто форвардим сообщение "как есть"
        await client.forward_messages(
            entity=target_channel,
            messages=message.id,
            from_peer=source_channel
        )
        logger.info(f"Сообщение {message.id} переслано (forward) без изменений в {target_channel}")
    else:
        # Если что-то удалили, отправляем заново (с уже очищенным текстом).
        # По желанию добавляем свою ссылку, если хотим.
        final_text = modified_text + "\n[The Crypto Currency](https://t.me/+gOxTz-7iTuhlYThi)"

        # Проверяем, есть ли медиа
        media_files = []
        if message.media:
            if isinstance(message.media, MessageMediaPhoto):
                media_files.append(message.photo)
            elif isinstance(message.media, MessageMediaDocument):
                media_files.append(message.document)

        try:
            if media_files:
                await client.send_file(target_channel, media_files[0],
                                       caption=final_text,
                                       parse_mode='markdown')
            else:
                await client.send_message(target_channel,
                                          final_text,
                                          parse_mode='markdown')
            logger.info(f"Сообщение {message.id} отправлено с удалёнными ссылками в {target_channel}")
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения в {target_channel}: {e}")

    # Помечаем, что сообщение уже обработано
    sent_messages.setdefault(target_channel, []).append(message.id)

async def main():
    try:
        if phone_number:
            await client.start(phone_number)
        else:
            await client.start()
    except SessionPasswordNeededError:
        logger.error("Необходим пароль для входа в аккаунт")
        return
    except Exception as e:
        logger.error(f"Ошибка аутентификации: {e}")
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
