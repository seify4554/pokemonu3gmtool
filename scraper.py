import sqlite3
import requests
import json
import re

# Fallback for Paradox and other special Pokémon
FALLBACK_ABILITIES = {
    "Slither Wing": ["Protosynthesis"],
    "Iron Jugulis": ["Quark Drive"],
    "Roaring Moon": ["Protosynthesis"],
    "Sandy Shocks": ["Protosynthesis"],
    "Iron Valiant": ["Quark Drive"],
    "Scream Tail": ["Protosynthesis"],
    "Iron Hands": ["Quark Drive"],
    "Iron Moth": ["Quark Drive"],
    "Flutter Mane": ["Protosynthesis"],
    "Brute Bonnet": ["Protosynthesis"],
    "Great Tusk": ["Protosynthesis"],
    "Iron Treads": ["Quark Drive"],
    "Iron Bundle": ["Quark Drive"],
    "Iron Thorns": ["Quark Drive"],
    "Buzzwole": ["Beast Boost"],
    "Pheromosa": ["Beast Boost"],
    "Guzzlord": ["Beast Boost"],
    "Xurkitree": ["Beast Boost"],
    "Blacephalon": ["Beast Boost"],
    "Kartana": ["Beast Boost"],
    "Poipole": ["Beast Boost"],
    "Naganadel": ["Beast Boost"],
    "Nihilego": ["Beast Boost"],
    "Stakataka": ["Beast Boost"],
    "Celesteela": ["Beast Boost"],
    "Tauros (Combat Breed)": ["Intimidate", "Anger Point", "Cud Chew"],
    "Tauros (Blaze Breed)": ["Intimidate", "Anger Point", "Cud Chew"],
    "Tauros (Aqua Breed)": ["Intimidate", "Anger Point", "Cud Chew"],
    # Add more if needed
}

def clean_slug(name):
    n = name.lower().strip()
    # Remove parentheses for forms, but add prefix for regional
    form = re.search(r'\((.*)\)', n)
    if form:
        form_type = form.group(1).lower().replace(' ', '-')
        n = re.sub(r'\s*\(.*\)', '', n).strip()
        if "paldea" in form_type or "hisui" in form_type or "gala" in form_type:
            n = form_type + '-' + n
    n = n.replace(' ', '-').replace("'", "").replace('.', "").replace('’', "")
    return n

conn = sqlite3.connect('database.db')
c = conn.cursor()

c.execute("SELECT name FROM pokemon")
rows = c.fetchall()
pokemon_names = [row[0] for row in rows]
print(f"Found {len(pokemon_names)} Pokémon in DB.")

updated = 0
failed = 0

for name in pokemon_names:
    abilities = FALLBACK_ABILITIES.get(name, [])
    
    if not abilities:
        slug = clean_slug(name)
        url = f"https://pokeapi.co/api/v2/pokemon/{slug}"
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                abilities = [a['ability']['name'] for a in data['abilities']]
                print(f"Scraped for {name} ({slug}): {', '.join(abilities)}")
            else:
                print(f"404 for {name} ({slug})")
                failed += 1
                continue
        except Exception as e:
            print(f"Error for {name}: {str(e)}")
            failed += 1
            continue

    if abilities:
        abilities_json = json.dumps(abilities)
        c.execute("UPDATE pokemon SET abilities = ? WHERE name = ?", (abilities_json, name))
        updated += 1

conn.commit()
conn.close()

print(f"\nUpdated {updated} Pokémon with abilities.")
print(f"Failed {failed} (add to fallback if needed).")
print("Done! Refresh /pokemon to see abilities.")