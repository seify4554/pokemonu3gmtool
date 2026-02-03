import sqlite3
import json
import re
from pypdf import PdfReader
import unicodedata

DB_FILE = "database.db"
PDF_FILE = "PTE PokeDex.pdf"

def clean_toc_name(toc_name: str) -> str:
    """Clean the fucked up TOC names with dots."""
    # Remove all trailing dots and spaces
    clean = re.sub(r'\s*\.+\s*$', '', toc_name).strip()
    # Remove multiple spaces
    clean = re.sub(r'\s+', ' ', clean)
    # Remove any remaining dots in the middle
    clean = re.sub(r'\s*\.\s*', ' ', clean)
    return clean

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

def extract_all_pokemon_stats():
    """
    Extract stats for ALL Pokémon from the PDF and update database.
    NO NEW INSERTS - ONLY UPDATES!
    """
    print("="*80)
    print("PDF STATS EXTRACTOR - UPDATE ONLY")
    print("="*80)
    
    # Connect to database
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Get all Pokémon that exist in the database
    c.execute("SELECT name FROM pokemon")
    existing_pokemon = {row[0] for row in c.fetchall()}
    
    print(f"Found {len(existing_pokemon)} Pokémon in database")
    
    # First, get all Pokémon with 0 stats
    c.execute("""
        SELECT DISTINCT name 
        FROM pokemon 
        WHERE (HP = 0 OR HP IS NULL) 
           OR (Atk = 0 OR Atk IS NULL)
           OR (Def = 0 OR Def IS NULL)
        ORDER BY name
    """)
    
    pokemon_needing_stats = [row[0] for row in c.fetchall()]
    
    print(f"\nFound {len(pokemon_needing_stats)} Pokémon needing stats")
    print("\nFirst 20 Pokémon needing stats:")
    for name in pokemon_needing_stats[:20]:
        print(f"  {name}")
    if len(pokemon_needing_stats) > 20:
        print(f"  ... and {len(pokemon_needing_stats) - 20} more")
    
    if not pokemon_needing_stats:
        print("✅ All Pokémon already have stats!")
        conn.close()
        return
    
    # Read PDF
    print(f"\nReading PDF: {PDF_FILE}")
    reader = PdfReader(PDF_FILE)
    
    # First, let's scan the TOC to find page numbers for each Pokémon
    print("\nScanning Table of Contents...")
    name_page_map = {}
    
    # Look for TOC pages (usually pages 2-15)
    for page_num in range(1, min(20, len(reader.pages))):
        try:
            page = reader.pages[page_num]
            text = page.extract_text() or ""
            lines = text.split('\n')
            
            for line in lines:
                # Look for TOC entries like "Pokémon Name ...... 123"
                match = re.search(r'^(.+?)[ \.]*(\d+)$', line.strip())
                if match:
                    name = match.group(1).strip()
                    page_num_ref = int(match.group(2))
                    
                    # Clean the name
                    clean_name = clean_toc_name(name)
                    
                    # Only add if it looks like a Pokémon name (not a section header)
                    if (clean_name and len(clean_name) < 50 and 
                        not clean_name.lower() in ['contents', 'table of contents', 'introduction', 'index'] and
                        clean_name[0].isupper()):
                        
                        # Check if this Pokémon exists in our database
                        for db_name in existing_pokemon:
                            # Try to match cleaned names
                            db_clean = db_name.strip()
                            if (db_clean.lower() == clean_name.lower() or 
                                clean_name.lower() in db_clean.lower() or 
                                db_clean.lower() in clean_name.lower()):
                                
                                name_page_map[db_name] = page_num_ref
                                # print(f"  TOC Match: {db_name} -> page {page_num_ref}")
                                break
                                
        except Exception as e:
            print(f"Error reading TOC page {page_num + 1}: {e}")
    
    print(f"Found {len(name_page_map)} Pokémon in TOC")
    
    # Now extract stats from each page and update database
    print(f"\nExtracting stats from PDF...")
    
    # We'll also try to extract stats by scanning all pages for stats
    print("Scanning all pages for stats...")
    
    updated_count = 0
    not_found_count = 0
    error_count = 0
    
    # Try TOC-based extraction first
    for db_name, page_num in name_page_map.items():
        if db_name not in pokemon_needing_stats:
            continue
            
        try:
            # Make sure page number is valid
            if page_num < 1 or page_num > len(reader.pages):
                continue
                
            page = reader.pages[page_num - 1]  # PDF pages are 0-indexed
            text = page.extract_text() or ""
            
            # Extract stats
            stats = extract_stats_fixed(text)
            
            if stats:
                # Update the database
                stats_json = json.dumps({
                    "HP": stats['HP'],
                    "Attack": stats['Attack'],
                    "Defense": stats['Defense'],
                    "Special Attack": stats['SpAtk'],
                    "Special Defense": stats['SpDef'],
                    "Speed": stats['Speed']
                })
                
                c.execute("""
                    UPDATE pokemon 
                    SET HP=?, Atk=?, Def=?, SpA=?, SpD=?, Spe=?, stats=?
                    WHERE name=?
                """, (stats['HP'], stats['Attack'], stats['Defense'],
                      stats['SpAtk'], stats['SpDef'], stats['Speed'],
                      stats_json, db_name))
                
                updated_count += 1
                print(f"✓ {db_name}: Updated from page {page_num}")
            else:
                not_found_count += 1
                # print(f"✗ {db_name}: No stats found on page {page_num}")
                
        except Exception as e:
            error_count += 1
            print(f"✗ Error processing {db_name}: {e}")
    
    # Now try to find remaining Pokémon by scanning all pages
    print(f"\nSearching for remaining {len(pokemon_needing_stats) - updated_count} Pokémon...")
    
    # Create a set of Pokémon still needing stats
    remaining_pokemon = set(pokemon_needing_stats) - set(name_page_map.keys())
    
    # For each remaining Pokémon, scan the PDF
    for db_name in list(remaining_pokemon)[:100]:  # Limit to 100 for now
        print(f"  Searching for {db_name}...")
        
        # Try to find this Pokémon in the PDF
        found = False
        
        for page_num in range(len(reader.pages)):
            try:
                page = reader.pages[page_num]
                text = page.extract_text() or ""
                
                # Check if this Pokémon's name appears on the page
                # Use fuzzy matching for names
                search_terms = [
                    db_name,
                    db_name.replace("'", "").replace("’", ""),
                    re.sub(r'\s*\([^)]*\)', '', db_name),  # Remove parentheses
                ]
                
                for term in search_terms:
                    if term and len(term) > 2:
                        if term.lower() in text.lower():
                            # Found the page, now extract stats
                            stats = extract_stats_fixed(text)
                            
                            if stats:
                                # Update the database
                                stats_json = json.dumps({
                                    "HP": stats['HP'],
                                    "Attack": stats['Attack'],
                                    "Defense": stats['Defense'],
                                    "Special Attack": stats['SpAtk'],
                                    "Special Defense": stats['SpDef'],
                                    "Speed": stats['Speed']
                                })
                                
                                c.execute("""
                                    UPDATE pokemon 
                                    SET HP=?, Atk=?, Def=?, SpA=?, SpD=?, Spe=?, stats=?
                                    WHERE name=?
                                """, (stats['HP'], stats['Attack'], stats['Defense'],
                                      stats['SpAtk'], stats['SpDef'], stats['Speed'],
                                      stats_json, db_name))
                                
                                updated_count += 1
                                print(f"    ✓ Found on page {page_num + 1}")
                                found = True
                                break
                
                if found:
                    break
                    
            except Exception as e:
                continue
        
        if not found:
            not_found_count += 1
            print(f"    ✗ Not found")
    
    # Commit changes
    conn.commit()
    
    # Final statistics
    c.execute("SELECT COUNT(*) FROM pokemon WHERE HP > 0")
    with_stats = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM pokemon WHERE HP = 0 OR HP IS NULL")
    still_zero = c.fetchone()[0]
    
    conn.close()
    
    # Show results
    print("\n" + "="*80)
    print("RESULTS")
    print("="*80)
    print(f"Total Pokémon needing stats: {len(pokemon_needing_stats)}")
    print(f"Successfully updated: {updated_count}")
    print(f"Not found in PDF: {not_found_count}")
    print(f"Errors: {error_count}")
    print(f"\nTotal Pokémon with stats: {with_stats}")
    print(f"Pokémon still with 0 stats: {still_zero}")
    
    # Show sample of what was updated
    print("\nLast 10 Pokémon updated:")
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        SELECT name, HP, Atk, Def, SpA, SpD, Spe 
        FROM pokemon 
        WHERE HP > 0 
        ORDER BY ROWID DESC 
        LIMIT 10
    """)
    
    for row in c.fetchall():
        print(f"  {row[0]:25} HP:{row[1]:3} Atk:{row[2]:3} Def:{row[3]:3} SpA:{row[4]:3} SpD:{row[5]:3} Spe:{row[6]:3}")
    
    conn.close()
    
    if still_zero > 0:
        # Save list of Pokémon still with 0 stats
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("""
            SELECT name 
            FROM pokemon 
            WHERE HP = 0 OR HP IS NULL
            ORDER BY name
        """)
        
        still_missing = [row[0] for row in c.fetchall()]
        conn.close()
        
        with open("still_missing_stats.txt", "w") as f:
            f.write("Pokémon still missing stats:\n")
            f.write("="*50 + "\n")
            for name in still_missing:
                f.write(f"{name}\n")
        
        print(f"\nList of {len(still_missing)} still missing Pokémon saved to: still_missing_stats.txt")

def main():
    """Main function."""
    print("PDF STATS UPDATER - NO DUPLICATES, UPDATE ONLY")
    print("="*80)
    
    # Backup first (just in case)
    import shutil
    try:
        shutil.copy2(DB_FILE, DB_FILE + ".backup")
        print(f"✅ Created backup: {DB_FILE}.backup")
    except:
        print("⚠️  Could not create backup")
    
    # Extract and update
    extract_all_pokemon_stats()
    
    print("\n" + "="*80)
    print("DONE!")
    print("Restart Flask and check /pokemon page.")
    print("="*80)

if __name__ == "__main__":
    main()