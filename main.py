import os
from dotenv import load_dotenv
import asyncio

import logging
from typing import Callable, Awaitable, Any
from aiogram import Bot, Dispatcher, BaseMiddleware
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart
from aiogram.types import Message, Update, WebAppInfo
from aiogram.enums import ParseMode
from aiogram.utils.keyboard import InlineKeyboardBuilder

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from decimal import Decimal
import uvicorn
import math


from app.models import models


load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL")
PORT = int(os.getenv("PORT"))


async def lifespan(app: FastAPI):
    await bot.set_webhook(
        url=f"{WEBAPP_URL}:{PORT}/webhook",
        allowed_updates=dp.resolve_used_update_types(),
        drop_pending_updates=True,
    )
    global pool
    pool = await models.create_pool()
    await models.init_db(pool)
    await models.add_token_if_not_exists(
        pool, "Gold", 1000000000, 100000000, 0.1, 1000000000
    )
    yield
    await pool.close()


app = FastAPI(lifespan=lifespan)

templates = Jinja2Templates(directory="./templates")
app.mount("/static", StaticFiles(directory="./static"), name="static")

bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

pool = None


async def add_user(user):
    profile_photos = await bot.get_user_profile_photos(user.id)
    photo = (
        profile_photos.photos[0][-1].file_id if profile_photos.total_count > 0 else None
    )

    global pool
    await models.add_user(pool, user.id, user.username, photo)


async def bancor_price(gold_supply, silver_balance, weight):
    return round(silver_balance / (gold_supply * weight), 2)


async def calculate_buy_price(gold_supply, silver_balance, gold_amount, weight):
    return silver_balance * (math.pow(1 + gold_amount / gold_supply, 1 / weight) - 1)


async def calculate_sell_price(gold_supply, silver_balance, gold_amount, weight):
    return silver_balance * (1 - math.pow(1 - gold_amount / gold_supply, 1 / weight))


async def calculate_gold_price():
    token_data = await models.get_token_data(pool, "Gold")
    gold_supply = float(token_data["gold_supply"])
    silver_balance = float(token_data["silver_balance"])
    weight = float(token_data["weight"])
    return await bancor_price(gold_supply, silver_balance, weight)


async def buy_gold_function(user_id, amount):
    user = await models.get_user_info(pool, user_id)
    token_data = await models.get_token_data(pool, "Gold")

    gold_supply = float(token_data["gold_supply"])
    silver_balance = float(token_data["silver_balance"])
    weight = float(token_data["weight"])

    total_cost = await calculate_buy_price(gold_supply, silver_balance, amount, weight)

    if float(user["silver"]) >= total_cost:
        new_silver = round(float(user["silver"]) - total_cost, 2)
        new_gold = round(float(user["gold"]) + amount, 2)
        new_supply = round(gold_supply + amount, 2)
        new_silver_balance = round(silver_balance - total_cost, 2)

        await models.update_user_balance(pool, user_id, new_gold, new_silver)
        await models.update_token_data(pool, "Gold", new_supply, new_silver_balance)

        new_price = await bancor_price(new_supply, new_silver_balance, weight)

        return {
            "success": True,
            "new_silver": new_silver,
            "new_gold": new_gold,
            "new_price": round(new_price, 2),
        }
    else:
        return {"success": False, "message": "Insufficient silver"}


async def sell_gold_function(user_id, amount):
    user = await models.get_user_info(pool, user_id)
    token_data = await models.get_token_data(pool, "Gold")

    gold_supply = float(token_data["gold_supply"])
    silver_balance = float(token_data["silver_balance"])
    weight = float(token_data["weight"])

    total_return = await calculate_sell_price(
        gold_supply, silver_balance, amount, weight
    )

    if float(user["gold"]) >= amount:
        new_silver = round(float(user["silver"]) + total_return, 2)
        new_gold = round(float(user["gold"]) - amount, 2)
        new_supply = round(gold_supply - amount, 2)
        new_silver_balance = round(silver_balance + total_return, 2)

        await models.update_user_balance(pool, user_id, new_gold, new_silver)
        await models.update_token_data(pool, "Gold", new_supply, new_silver_balance)

        new_price = await bancor_price(new_supply, new_silver_balance, weight)

        return {
            "success": True,
            "new_silver": new_silver,
            "new_gold": new_gold,
            "new_price": round(new_price, 2),
        }
    else:
        return {"success": False, "message": "Insufficient gold"}


@dp.message(CommandStart())
async def command_start_handler(message: Message):
    await add_user(message.from_user)
    markup = (
        InlineKeyboardBuilder()
        .button(
            text="Buy gold",
            web_app=WebAppInfo(url=f"{WEBAPP_URL}/{message.from_user.id}"),
        )
        .as_markup()
    )

    await message.answer("You can buy gold for silver!!!", reply_markup=markup)


@app.post("/webhook")
async def webhook(request: Request):
    update = Update.model_validate(await request.json(), context={"bot": bot})
    await dp.feed_update(bot, update)


@app.get("/{user_id}")
async def root(request: Request, user_id: int):
    user_data = await models.get_user_info(pool, user_id)

    gold_price = await calculate_gold_price()

    all_users = await models.get_all_users(pool)

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "user": user_data,
            "gold_price": gold_price,
            "users": all_users,
        },
    )


@app.get("/user_info/{user_id}")
async def user_info(request: Request, user_id: int):
    user_data = await models.get_user_info(pool, user_id)
    if user_data["photo"]:
        photo = await bot.get_file(user_data["photo"])
        photo_url = photo.file_path
        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{photo_url}"
    else:
        file_url = None
    return templates.TemplateResponse(
        "user_info.html", {"request": request, "user": user_data, "photo": file_url}
    )


@app.post("/buy_gold/{user_id}")
async def buy_gold(request: Request, user_id: int):
    body = await request.json()
    amount = body.get("amount")
    result = await buy_gold_function(user_id, amount)
    if result["success"]:
        return JSONResponse(content=result)
    else:
        raise HTTPException(status_code=400, detail=result["message"])


@app.post("/sell_gold/{user_id}")
async def sell_gold_endpoint(request: Request, user_id: int):
    body = await request.json()
    amount = body.get("amount")
    result = await sell_gold_function(user_id, amount)
    if result["success"]:
        return JSONResponse(content=result)
    else:
        raise HTTPException(status_code=400, detail=result["message"])


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
