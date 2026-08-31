from aiogram.types import InlineKeyboardButton
import math


async def paginator(items, total_items, offset, limit, menu_callback):
    buttons = []
    for item in items:
        buttons.append(
            [InlineKeyboardButton(text=item["text"], callback_data=f"{item['callback']}:{offset}")]
        )
    buttons.append(
        [
            InlineKeyboardButton(text=f"ᐊ" if offset > 0 else " ", callback_data=f"{menu_callback}:{offset - limit}" if offset > 0 else " "),
            InlineKeyboardButton(text=f"{math.ceil((offset + limit) / limit)}/{math.ceil(total_items / limit)}", callback_data=f" "),
            InlineKeyboardButton(text=f"ᐅ" if offset + limit < total_items else " ",
                                 callback_data=f"{menu_callback}:{offset + limit}" if offset + limit < total_items else " ")
        ]
    )
    return buttons

