import sqlite3
import json
import re
import requests
import time
from bs4 import BeautifulSoup
from pypdf import PdfReader
import unicodedata
import sys

print("Starting extraction...")

conn = sqlite3.connect('database.db')
c = conn.cursor()

# Tables
c.execute('''CREATE TABLE IF NOT EXISTS pokemon
             (name TEXT PRIMARY KEY, 
              stats TEXT, 
              capabilities TEXT, 
              skills TEXT, 
              abilities TEXT,
              HP INTEGER DEFAULT 0,
              Atk INTEGER DEFAULT 0,
              Def INTEGER DEFAULT 0,
              SpA INTEGER DEFAULT 0,
              SpD INTEGER DEFAULT 0,
              Spe INTEGER DEFAULT 0)''')

conn.commit()

# Enhanced fallback abilities for PTE
FALLBACK_ABILITIES = {
    # Keep your existing fallback abilities here
    "Bulbasaur": ["Overgrow"],
    "Ivysaur": ["Overgrow"],
    "Venusaur": ["Overgrow"],
    "Charmander": ["Blaze"],
    "Charmeleon": ["Blaze"],
    "Charizard": ["Blaze"],
    "Squirtle": ["Torrent"],
    "Wartortle": ["Torrent"],
    "Blastoise": ["Torrent"],
    "Pikachu": ["Static"],
    "Raichu": ["Static"],
    "Eevee": ["Adaptability", "Run Away"],
    "Vaporeon": ["Water Absorb"],
    "Jolteon": ["Volt Absorb"],
    "Flareon": ["Flash Fire"],
    "Espeon": ["Synchronize"],
    "Umbreon": ["Synchronize"],
    "Leafeon": ["Leaf Guard"],
    "Glaceon": ["Snow Cloak"],
    "Sylveon": ["Cute Charm"],
    # Add ALL other Pokémon here...
}

def clean_toc_name(toc_name: str) -> str:
    """Clean the fucked up TOC names with dots."""
    # Remove all trailing dots and spaces
    clean = re.sub(r'\s*\.+\s*$', '', toc_name).strip()
    # Remove multiple spaces
    clean = re.sub(r'\s+', ' ', clean)
    # Remove any remaining dots in the middle
    clean = re.sub(r'\s*\.\s*', ' ', clean)
    return clean

def clean_name_for_api(name: str) -> str:
    """Clean Pokémon name for PokéAPI requests."""
    if not name:
        return ""
    
    # First clean TOC name
    name = clean_toc_name(name)
    
    # Normalize unicode
    name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('ascii')
    name = name.strip()
    
    # Handle special characters
    name = re.sub(r'[^\w\s-]', '', name)
    
    # Remove anything in parentheses for API call
    name = re.sub(r'\s*\([^)]*\)', '', name).strip()
    
    # Regional forms
    name_lower = name.lower()
    if 'alolan' in name_lower:
        base = re.sub(r'alolan\s+', '', name_lower, flags=re.IGNORECASE).strip()
        return f"{base}-alola"
    elif 'galarian' in name_lower:
        base = re.sub(r'galarian\s+', '', name_lower, flags=re.IGNORECASE).strip()
        return f"{base}-galar"
    elif 'hisuian' in name_lower:
        base = re.sub(r'hisuian\s+', '', name_lower, flags=re.IGNORECASE).strip()
        return f"{base}-hisui"
    
    # Standard cleanup
    name = name.lower()
    name = name.replace(' ', '-').replace("'", "").replace(".", "").replace("♂", "-m").replace("♀", "-f")
    name = name.replace("nidoran-m", "nidoran-m").replace("nidoran-f", "nidoran-f")
    name = name.replace("mr-mime", "mr-mime").replace("mime-jr", "mime-jr")
    name = name.replace("flabébé", "flabebe").replace("farfetchd", "farfetchd")
    
    return name

def get_abilities_from_api(pokemon_name: str):
    """Get abilities from PokéAPI with fallback."""
    # First clean the TOC name
    clean_pokemon_name = clean_toc_name(pokemon_name)
    
    # Check fallback first
    if clean_pokemon_name in FALLBACK_ABILITIES:
        return FALLBACK_ABILITIES[clean_pokemon_name]
    
    # Try to get from API
    slug = clean_name_for_api(clean_pokemon_name)
    
    if not slug:
        print(f"  Could not clean name: {clean_pokemon_name}")
        return ["Unknown"]
    
    url = f"https://pokeapi.co/api/v2/pokemon/{slug}"
    
    try:
        print(f"  Fetching abilities for {clean_pokemon_name}...")
        resp = requests.get(url, timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            abilities = []
            for ability_data in data['abilities']:
                if ability_data['is_hidden']:
                    continue  # Skip hidden for now
                ability_name = ability_data['ability']['name']
                # Format nicely
                ability_name = ' '.join(word.capitalize() for word in ability_name.split('-'))
                abilities.append(ability_name)
            
            return abilities if abilities else ["Unknown"]
        else:
            print(f"  API error {resp.status_code} for {clean_pokemon_name}")
            
            # Try without the form suffix (e.g., "Lycanroc (Midday)" -> "Lycanroc")
            base_name = re.sub(r'\s*\([^)]*\)', '', clean_pokemon_name).strip()
            if base_name != clean_pokemon_name:
                print(f"  Trying base form: {base_name}")
                return get_abilities_from_api(base_name)
            
            return ["Unknown"]
            
    except Exception as e:
        print(f"  API fetch error: {e}")
        return ["Unknown"]

def extract_stats_fixed(text: str):
    """FIXED STAT EXTRACTION - PROPERLY EXTRACTS JUST THE NUMBERS"""
    stats_dict = {}
    
    # Try multiple patterns to handle different formats
    
    # Pattern 1: HP: 45 Attack: 49 Defense: 49 Sp. Atk: 65 Sp. Def: 65 Speed: 45
    pattern1 = r'HP\s*[:=]?\s*(\d+)\s+(?:Attack|Atk)\s*[:=]?\s*(\d+)\s+(?:Defense|Def)\s*[:=]?\s*(\d+)\s+(?:Sp\.?\s*Atk|Special Attack)\s*[:=]?\s*(\d+)\s+(?:Sp\.?\s*Def|Special Defense)\s*[:=]?\s*(\d+)\s+Speed\s*[:=]?\s*(\d+)'
    
    # Pattern 2: One per line format
    patterns = [
        r'HP\s*[:=]?\s*(\d+)',
        r'(?:Attack|Atk)\s*[:=]?\s*(\d+)',
        r'(?:Defense|Def)\s*[:=]?\s*(\d+)',
        r'(?:Sp\.?\s*Atk|Special Attack)\s*[:=]?\s*(\d+)',
        r'(?:Sp\.?\s*Def|Special Defense)\s*[:=]?\s*(\d+)',
        r'Speed\s*[:=]?\s*(\d+)'
    ]
    
    # Try pattern 1 first (all in one line)
    match1 = re.search(pattern1, text, re.IGNORECASE)
    if match1:
        stats = [int(x) for x in match1.groups()]
        if len(stats) == 6:
            return {
                'HP': stats[0],
                'Attack': stats[1],
                'Defense': stats[2],
                'SpAtk': stats[3],
                'SpDef': stats[4],
                'Speed': stats[5]
            }
    
    # Try pattern 2 (find each stat separately)
    stats = []
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            stats.append(int(match.group(1)))
        else:
            # If we can't find a stat, return empty
            return {}
    
    if len(stats) == 6:
        return {
            'HP': stats[0],
            'Attack': stats[1],
            'Defense': stats[2],
            'SpAtk': stats[3],
            'SpDef': stats[4],
            'Speed': stats[5]
        }
    
    return {}

# TOC
pdf_file = 'PTE PokeDex.pdf'
reader = PdfReader(pdf_file)
name_page_map = {}

print("\nScanning Table of Contents...")
for page_num in range(2, 11):  # TOC is usually on pages 2-10
    try:
        page = reader.pages[page_num - 1]
        text = page.extract_text() or ""
        lines = text.split('\n')
        
        for line in lines:
            # More flexible pattern for TOC entries
            match = re.match(r'^(.*?)\s*\.+\s*(\d+)$', line.strip())
            if match:
                name = match.group(1).strip()
                page = int(match.group(2))
                
                if name and len(name) > 1:  # Valid name
                    name_page_map[name] = page
    except Exception as e:
        print(f"Error reading page {page_num}: {e}")

print(f"\nFound {len(name_page_map)} Pokémon in TOC.")

# Process ALL Pokémon (CHANGED FROM [:50] to .items())
processed = 0
errors = 0
successful = 0

for orig_name, page_num in name_page_map.items():  # REMOVED THE [:50] !!!
    try:
        print(f"\n[{processed+1}/{len(name_page_map)}] Processing {orig_name} (page {page_num})...")
        
        # Clean the TOC name for database
        clean_name = clean_toc_name(orig_name)
        
        page = reader.pages[page_num - 1]
        text = page.extract_text() or ""
        
        if not text:
            print(f"  No text on page {page_num}")
            errors += 1
            processed += 1
            continue
        
        # Extract stats using FIXED function
        stats_dict = extract_stats_fixed(text)
        
        if stats_dict:
            print(f"  ✓ Stats found: {stats_dict}")
            
            # Create stats JSON
            stats_json = json.dumps(stats_dict)
            
            # Extract individual stat values
            hp = stats_dict.get('HP', 0)
            attack = stats_dict.get('Attack', 0)
            defense = stats_dict.get('Defense', 0)
            sp_atk = stats_dict.get('SpAtk', 0)
            sp_def = stats_dict.get('SpDef', 0)
            speed = stats_dict.get('Speed', 0)
            
            # Capabilities & Skills
            cap_match = re.search(r'Capability Information\s*(.*?)(?=Skill Information|Other Information|$)', text, re.DOTALL | re.IGNORECASE)
            capabilities = cap_match.group(1).strip() if cap_match else ''
            
            skill_match = re.search(r'Skill Information\s*(.*?)(?=Other Information|Dex Entry|$)', text, re.DOTALL | re.IGNORECASE)
            skills = skill_match.group(1).strip() if skill_match else ''
            
            # Clean up capabilities and skills
            if capabilities:
                capabilities = re.sub(r'\s+', ' ', capabilities)  # Remove extra whitespace
                capabilities = capabilities[:500]  # Limit length
            
            if skills:
                skills = re.sub(r'\s+', ' ', skills)
                skills = skills[:500]
            
            # Get abilities from API with fallback
            abilities = get_abilities_from_api(clean_name)
            abilities_json = json.dumps(abilities)
            
            # Insert or update
            c.execute('''INSERT OR REPLACE INTO pokemon 
                         (name, stats, capabilities, skills, abilities, HP, Atk, Def, SpA, SpD, Spe)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                      (clean_name, stats_json, capabilities, skills, abilities_json, 
                       hp, attack, defense, sp_atk, sp_def, speed))
            
            successful += 1
            print(f"  ✓ Saved {clean_name}")
            
        else:
            print(f"  ✗ No stats found for {clean_name}")
            errors += 1
            
        processed += 1
        
        # Rate limiting for API calls (1 request per second)
        time.sleep(0.5)
            
    except Exception as e:
        print(f"  ✗ Error processing {orig_name}: {str(e)[:100]}")
        errors += 1
        processed += 1

conn.commit()

# Show what we got
print("\n" + "="*60)
print("EXTRACTION SUMMARY")
print("="*60)

c.execute("SELECT COUNT(*) FROM pokemon WHERE HP > 0")
with_stats = c.fetchone()[0]

c.execute("SELECT COUNT(DISTINCT name) FROM pokemon")
total_in_db = c.fetchone()[0]

print(f"Total Pokémon in TOC: {len(name_page_map)}")
print(f"Successfully processed: {successful}")
print(f"Errors: {errors}")
print(f"Pokémon with stats in DB: {with_stats}")
print(f"Total unique Pokémon in DB: {total_in_db}")

# Show a sample
print("\nSample of recently added Pokémon:")
c.execute("SELECT name, HP, Atk, Def, SpA, SpD, Spe FROM pokemon WHERE HP > 0 ORDER BY ROWID DESC LIMIT 10")
sample = c.fetchall()

for name, hp, atk, defense, spa, spd, spe in sample:
    print(f"  {name:25} HP:{hp:3} Atk:{atk:3} Def:{defense:3} SpA:{spa:3} SpD:{spd:3} Spe:{spe:3}")

conn.close()
print("\nExtraction complete.")
