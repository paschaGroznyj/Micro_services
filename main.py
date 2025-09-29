import asyncio
from database.create_tables import DataBase

async def main():
    db = DataBase()
    await db.init_db_pool()
    await db.add_user("pascha123", "password")

if __name__ == "__main__":
    asyncio.run(main())