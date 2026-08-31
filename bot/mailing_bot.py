import time
from aiogram import Bot, Dispatcher
import os
from aiogram.enums import ParseMode
from aiogram.types import FSInputFile
from asgiref.sync import sync_to_async
from datetime import datetime
from django.db.models import Q
from core.models import Mailings, Users
from django.utils import timezone


@sync_to_async
def get_mailings():
    current_date = timezone.now()
    incomplete_mailings = Mailings.objects.filter(
        Q(complete=False) & Q(mailing_date__lt=current_date)
    )
    return incomplete_mailings


@sync_to_async
def update_complete_status(mailing):
    mailing.complete = True
    mailing.save()


@sync_to_async
def get_users():
    users = Users.objects.all()
    return users


async def start():
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    bot = Bot(BOT_TOKEN, parse_mode=ParseMode.HTML)
    while True:
        time.sleep(5)
        async for mailing in await get_mailings():
            print(mailing)
            await update_complete_status(mailing)
            users = await get_users()
            image_from_pc = None
            if mailing.image:
                image_from_pc = FSInputFile(str(mailing.image))
            async for user in users:
                print(user)
                try:
                    if image_from_pc:
                        await bot.send_photo(chat_id=user.id, photo=image_from_pc, caption=mailing.message)
                    else:
                        await bot.send_message(
                            text=mailing.message,
                            chat_id=user.id,
                        )
                except:
                    pass
