"""
Drops and recreates the adk_sessions tables so ADK uses the v1 JSON schema.
Run once:  python reset_db.py
"""
import asyncio
import sys
import aiomysql

DB = dict(host="127.0.0.1", port=3306, user="root", password="root123", db="adk_sessions")


async def reset():
    print("Connecting to MySQL...")
    conn = await aiomysql.connect(**DB)
    print("Connected.")
    async with conn.cursor() as cur:
        await cur.execute("SET FOREIGN_KEY_CHECKS=0")
        await cur.execute("DROP TABLE IF EXISTS events")
        print("Dropped table: events")
        await cur.execute("DROP TABLE IF EXISTS sessions")
        print("Dropped table: sessions")
        await cur.execute("SET FOREIGN_KEY_CHECKS=1")
        await conn.commit()
        await cur.execute("SHOW TABLES")
        rows = await cur.fetchall()
        print(f"Tables remaining: {rows}")
    conn.close()
    print("Done. ADK will recreate the tables with v1 JSON schema on next run.")


if __name__ == "__main__":
    asyncio.run(reset())

