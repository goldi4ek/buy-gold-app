import asyncpg
import os
from dotenv import load_dotenv
from decimal import Decimal

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")


async def create_pool():
    return await asyncpg.create_pool(dsn=DATABASE_URL)


async def init_db(pool):
    async with pool.acquire() as connection:
        await connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                username VARCHAR(255),
                photo TEXT,
                gold DECIMAL(15,3) DEFAULT 0,
                silver DECIMAL(15,3) DEFAULT 1000
            )
        """
        )

        await connection.execute(
            """
                CREATE TABLE IF NOT EXISTS token_data (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                initial_supply NUMERIC NOT NULL,
                silver_balance NUMERIC NOT NULL,
                weight DECIMAL(2,2) NOT NULL,
                gold_supply NUMERIC NOT NULL
            )
        """
        )


async def get_user_info(pool, user_id):
    async with pool.acquire() as connection:
        user = await connection.fetchrow(
            "SELECT * FROM users WHERE user_id = $1", user_id
        )
        return user


async def add_user(pool, user_id, username, photo, gold=0, silver=1000):
    user = await get_user_info(pool, user_id)
    if user is None:
        async with pool.acquire() as connection:
            await connection.execute(
                """
                INSERT INTO users (user_id, username, photo, gold, silver)
                VALUES ($1, $2, $3, $4, $5)
                """,
                user_id,
                username,
                photo,
                gold,
                silver,
            )


async def update_user_balance(pool, user_id, gold, silver):
    async with pool.acquire() as connection:
        await connection.execute(
            """
            UPDATE users 
            SET gold = $2, silver = $3
            WHERE user_id = $1
            """,
            user_id,
            gold,
            silver,
        )


async def get_all_users(pool):
    async with pool.acquire() as connection:
        users = await connection.fetch("SELECT * FROM users")
        return users


async def get_token_data(pool, name):
    async with pool.acquire() as connection:
        token_data = await connection.fetchrow(
            "SELECT * FROM token_data where name = $1", name
        )
        return token_data


async def add_token_if_not_exists(
    pool, name, initial_supply, silver_balance, weight, gold_supply
):
    if await get_token_data(pool, name) is None:
        async with pool.acquire() as connection:
            await connection.execute(
                """
                INSERT INTO token_data (name, initial_supply, silver_balance, weight, gold_supply)
                VALUES ($1, $2, $3, $4, $5)
                """,
                name,
                initial_supply,
                silver_balance,
                weight,
                gold_supply,
            )


async def update_token_data(pool, name, gold_supply, silver_balance):
    async with pool.acquire() as connection:
        await connection.execute(
            """
            UPDATE token_data 
            SET gold_supply = $2, silver_balance = $3
            WHERE name = $1
            """,
            name,
            gold_supply,
            silver_balance,
        )
