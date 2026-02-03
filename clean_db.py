import sqlite3
import re

DB_FILE = "database.db"

def clean_name(name):
    """Remove dots, extra spaces, and trailing dashes from DB names."""
    n = name.strip()
    n = re.sub(r'\.+', '', n)          # Remove all dots
    n = re.sub(r'\s+', ' ', n)         # Collapse multiple spaces
    n = n.strip('-')                    # Remove leading/trailing dashes
    return n

conn = sqlite3.connect(DB_FILE)
c = conn.cursor()

c.execute("SELECT name FROM pokemon")
rows = c.fetchall()
cleaned = 0

for (name,) in rows:
    new_name = clean_name(name)
    if new_name != name:
        c.execute("UPDATE pokemon SET name = ? WHERE name = ?", (new_name, name))
        cleaned += 1

conn.commit()
conn.close()
print(f"Cleaned up {cleaned} Pokémon names.")
