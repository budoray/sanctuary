"""Sanctuary database schema and access."""
from __future__ import annotations

import psycopg.types.json
from tenshin_db import configure, db, init_schema

from config import settings

configure(settings.database_url)

SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS characters (
        id SERIAL PRIMARY KEY,
        account_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        ancestry TEXT NOT NULL,
        class TEXT NOT NULL,
        alignment TEXT NOT NULL DEFAULT 'Neutral',
        strength INTEGER NOT NULL,
        intelligence INTEGER NOT NULL,
        wisdom INTEGER NOT NULL,
        dexterity INTEGER NOT NULL,
        constitution INTEGER NOT NULL,
        charisma INTEGER NOT NULL,
        hit_points INTEGER NOT NULL,
        sheet JSONB NOT NULL DEFAULT '{}',
        ac INTEGER NOT NULL DEFAULT 10,
        thac0 INTEGER NOT NULL DEFAULT 20,
        movement INTEGER NOT NULL DEFAULT 120,
        starting_gold INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    )
    """,
    """
    ALTER TABLE characters
    ADD COLUMN IF NOT EXISTS sheet JSONB NOT NULL DEFAULT '{}'
    """,
    """
    ALTER TABLE characters
    ADD COLUMN IF NOT EXISTS ac INTEGER NOT NULL DEFAULT 10
    """,
    """
    ALTER TABLE characters
    ADD COLUMN IF NOT EXISTS thac0 INTEGER NOT NULL DEFAULT 20
    """,
    """
    ALTER TABLE characters
    ADD COLUMN IF NOT EXISTS movement INTEGER NOT NULL DEFAULT 120
    """,
    """
    ALTER TABLE characters
    ADD COLUMN IF NOT EXISTS starting_gold INTEGER NOT NULL DEFAULT 0
    """,
    """
    ALTER TABLE characters
    ADD COLUMN IF NOT EXISTS inventory JSONB NOT NULL DEFAULT '[]'
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_characters_account ON characters(account_id)
    """,
    """
    CREATE TABLE IF NOT EXISTS test_ground_tokens (
        character_id INTEGER PRIMARY KEY REFERENCES characters(id) ON DELETE CASCADE,
        x INTEGER NOT NULL,
        y INTEGER NOT NULL,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    )
    """,
]


def init_sanctuary_schema():
    init_schema(SCHEMA)


def create_character(
    account_id: int,
    name: str,
    ancestry: str,
    klass: str,
    alignment: str,
    abilities: dict[str, int],
    hit_points: int,
    sheet: dict,
    inventory: list[dict] | None = None,
) -> int:
    inventory = inventory or []
    c = db()
    cur = c.execute(
        """
        INSERT INTO characters
        (account_id, name, ancestry, class, alignment, strength, intelligence,
         wisdom, dexterity, constitution, charisma, hit_points, sheet, ac,
         thac0, movement, starting_gold, inventory)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            account_id,
            name,
            ancestry,
            klass,
            alignment,
            abilities["strength"],
            abilities["intelligence"],
            abilities["wisdom"],
            abilities["dexterity"],
            abilities["constitution"],
            abilities["charisma"],
            hit_points,
            psycopg.types.json.Jsonb(sheet),
            sheet.get("armour_class", 10),
            sheet.get("thac0", 20),
            sheet.get("movement", sheet.get("base_movement", 120)),
            sheet.get("starting_gold", 0),
            psycopg.types.json.Jsonb(inventory),
        ),
    )
    row = cur.fetchone()
    c.commit()
    return row["id"]


def list_characters(account_id: int):
    c = db()
    cur = c.execute(
        """
        SELECT id, name, ancestry, class, alignment, strength, intelligence,
               wisdom, dexterity, constitution, charisma, hit_points, sheet,
               inventory, starting_gold, created_at
        FROM characters
        WHERE account_id = %s
        ORDER BY created_at DESC
        """,
        (account_id,),
    )
    return cur.fetchall()


def get_character(character_id: int, account_id: int):
    c = db()
    cur = c.execute(
        """
        SELECT * FROM characters
        WHERE id = %s AND account_id = %s
        """,
        (character_id, account_id),
    )
    return cur.fetchone()


def place_token(character_id: int, x: int, y: int):
    c = db()
    cur = c.execute(
        """
        INSERT INTO test_ground_tokens (character_id, x, y)
        VALUES (%s, %s, %s)
        ON CONFLICT (character_id)
        DO UPDATE SET x = EXCLUDED.x, y = EXCLUDED.y,
                      updated_at = NOW()
        RETURNING x, y
        """,
        (character_id, x, y),
    )
    row = cur.fetchone()
    c.commit()
    return row


def get_token(character_id: int):
    c = db()
    cur = c.execute(
        """
        SELECT x, y FROM test_ground_tokens
        WHERE character_id = %s
        """,
        (character_id,),
    )
    return cur.fetchone()


def list_tokens():
    c = db()
    cur = c.execute(
        """
        SELECT t.character_id, t.x, t.y, c.name, c.ancestry, c.class
        FROM test_ground_tokens t
        JOIN characters c ON c.id = t.character_id
        """
    )
    return cur.fetchall()


def get_inventory(character_id: int, account_id: int):
    c = db()
    cur = c.execute(
        """
        SELECT inventory FROM characters
        WHERE id = %s AND account_id = %s
        """,
        (character_id, account_id),
    )
    row = cur.fetchone()
    return row["inventory"] if row else []


def set_inventory(character_id: int, account_id: int, inventory: list):
    c = db()
    cur = c.execute(
        """
        UPDATE characters
        SET inventory = %s
        WHERE id = %s AND account_id = %s
        RETURNING inventory
        """,
        (psycopg.types.json.Jsonb(inventory), character_id, account_id),
    )
    row = cur.fetchone()
    c.commit()
    return row["inventory"] if row else []
