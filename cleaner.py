import sqlite3
import json
import re

def fix_database_for_real():
    """FIX THIS SHIT FOR REAL - Clean names and remove duplicates."""
    print("="*80)
    print("DATABASE NUCLEAR CLEANUP - FIXING FUCKED UP NAMES")
    print("="*80)
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # First, fix the column types
    print("Fixing column types...")
    try:
        # Create a temp table with correct types
        c.execute("""
            CREATE TABLE pokemon_temp AS 
            SELECT 
                name,
                stats,
                capabilities,
                skills,
                abilities,
                CAST(HP AS INTEGER) as HP,
                CAST(Atk AS INTEGER) as Atk,
                CAST(Def AS INTEGER) as Def,
                CAST(SpA AS INTEGER) as SpA,
                CAST(SpD AS INTEGER) as SpD,
                CAST(Spe AS INTEGER) as Spe
            FROM pokemon
        """)
        
        # Replace the old table
        c.execute("DROP TABLE pokemon")
        c.execute("ALTER TABLE pokemon_temp RENAME TO pokemon")
        print("✅ Fixed column types")
    except Exception as e:
        print(f"⚠️ Could not fix types: {e}")
        conn.rollback()
    
    # Get all rows
    c.execute("SELECT rowid, name, stats, capabilities, skills, abilities, HP, Atk, Def, SpA, SpD, Spe FROM pokemon")
    rows = c.fetchall()
    
    print(f"Total rows before: {len(rows)}")
    
    # Create a mapping of clean name -> best row data
    pokemon_map = {}
    
    for row in rows:
        rowid, name, stats, capabilities, skills, abilities, hp, atk, defense, spa, spd, spe = row
        
        # Convert to proper types
        try:
            hp = int(hp) if hp is not None else 0
            atk = int(atk) if atk is not None else 0
            defense = int(defense) if defense is not None else 0
            spa = int(spa) if spa is not None else 0
            spd = int(spd) if spd is not None else 0
            spe = int(spe) if spe is not None else 0
        except:
            hp = atk = defense = spa = spd = spe = 0
        
        # CLEAN THE FUCKING NAME
        clean_name = clean_name_properly(name)
        
        if not clean_name or len(clean_name) < 2:
            print(f"⚠️ Skipping bad name: {name}")
            continue
        
        # Score this row (how complete is it?)
        score = 0
        if hp > 0: score += 1
        if atk > 0: score += 1
        if defense > 0: score += 1
        if spa > 0: score += 1
        if spd > 0: score += 1
        if spe > 0: score += 1
        
        # Check for capabilities (non-empty, not just "None")
        if capabilities and capabilities.strip() and capabilities.lower() not in ['none', 'null', '']:
            score += 2
            cap_quality = len(capabilities.split())
        else:
            cap_quality = 0
            
        # Check for skills (non-empty, not just "None")
        if skills and skills.strip() and skills.lower() not in ['none', 'null', '']:
            score += 2
            skill_quality = len(skills.split())
        else:
            skill_quality = 0
            
        # Check for abilities (non-empty, not generic)
        if abilities and abilities not in ['[]', '["Unknown"]', '["See PTE Rules"]', 'null', '', 'None']:
            try:
                abil_list = json.loads(abilities) if abilities.startswith('[') else []
                if abil_list and any(a.lower() not in ['unknown', 'none', 'see pte rules'] for a in abil_list):
                    score += 3
                    ability_quality = len(abil_list)
                else:
                    ability_quality = 0
            except:
                ability_quality = 0
        else:
            ability_quality = 0
        
        if clean_name not in pokemon_map:
            pokemon_map[clean_name] = {
                'rowid': rowid,
                'name': clean_name,
                'stats': stats,
                'capabilities': capabilities,
                'skills': skills,
                'abilities': abilities,
                'HP': hp,
                'Atk': atk,
                'Def': defense,
                'SpA': spa,
                'SpD': spd,
                'Spe': spe,
                'score': score,
                'cap_quality': cap_quality,
                'skill_quality': skill_quality,
                'ability_quality': ability_quality,
                'total_stats': hp + atk + defense + spa + spd + spe
            }
        else:
            # Keep the BETTER row
            current = pokemon_map[clean_name]
            
            # Compare and keep the better one
            # Priority: 1. Has abilities, 2. Has stats, 3. Has capabilities/skills
            keep_current = True
            
            # If new row has abilities and current doesn't
            if ability_quality > 0 and current['ability_quality'] == 0:
                keep_current = False
            # If both have abilities, check quality
            elif ability_quality > current['ability_quality']:
                keep_current = False
            # If abilities equal, check stats
            elif ability_quality == current['ability_quality']:
                if score > current['score']:
                    keep_current = False
                elif score == current['score']:
                    if hp + atk + defense + spa + spd + spe > current['total_stats']:
                        keep_current = False
            
            if not keep_current:
                pokemon_map[clean_name] = {
                    'rowid': rowid,
                    'name': clean_name,
                    'stats': stats,
                    'capabilities': capabilities,
                    'skills': skills,
                    'abilities': abilities,
                    'HP': hp,
                    'Atk': atk,
                    'Def': defense,
                    'SpA': spa,
                    'SpD': spd,
                    'Spe': spe,
                    'score': score,
                    'cap_quality': cap_quality,
                    'skill_quality': skill_quality,
                    'ability_quality': ability_quality,
                    'total_stats': hp + atk + defense + spa + spd + spe
                }
    
    print(f"\nUnique Pokémon after cleaning: {len(pokemon_map)}")
    
    # Create a new clean table
    print("\nCreating clean table...")
    c.execute("DROP TABLE IF EXISTS pokemon_clean")
    c.execute("""
        CREATE TABLE pokemon_clean (
            name TEXT PRIMARY KEY,
            stats TEXT,
            capabilities TEXT,
            skills TEXT,
            abilities TEXT,
            HP INTEGER DEFAULT 0,
            Atk INTEGER DEFAULT 0,
            Def INTEGER DEFAULT 0,
            SpA INTEGER DEFAULT 0,
            SpD INTEGER DEFAULT 0,
            Spe INTEGER DEFAULT 0
        )
    """)
    
    # Insert cleaned data
    inserted = 0
    duplicates_resolved = 0
    
    for clean_name, data in pokemon_map.items():
        # Check if we need to merge any data
        # Try to get stats from JSON if missing
        hp, atk, defense, spa, spd, spe = data['HP'], data['Atk'], data['Def'], data['SpA'], data['SpD'], data['Spe']
        
        # If stats are missing but we have stats JSON, extract from there
        if (hp == 0 or atk == 0 or defense == 0) and data['stats']:
            try:
                stats_dict = json.loads(data['stats'])
                hp = stats_dict.get('HP', hp) or stats_dict.get('hp', hp)
                atk = stats_dict.get('Attack', atk) or stats_dict.get('Atk', atk) or stats_dict.get('attack', atk)
                defense = stats_dict.get('Defense', defense) or stats_dict.get('Def', defense) or stats_dict.get('defense', defense)
                spa = stats_dict.get('Special Attack', spa) or stats_dict.get('SpAtk', spa) or stats_dict.get('SpA', spa)
                spd = stats_dict.get('Special Defense', spd) or stats_dict.get('SpDef', spd) or stats_dict.get('SpD', spd)
                spe = stats_dict.get('Speed', spe) or stats_dict.get('Spe', spe)
            except:
                pass
        
        # Clean up abilities
        abilities = data['abilities']
        if not abilities or abilities in ['[]', '["Unknown"]', '["See PTE Rules"]', 'null']:
            # Try to get from other rows for this Pokémon
            c.execute("SELECT abilities FROM pokemon WHERE name LIKE ? AND abilities NOT IN ('[]', '[\"Unknown\"]', '[\"See PTE Rules\"]', 'null')", 
                     (f"%{clean_name}%",))
            alt_abilities = c.fetchall()
            if alt_abilities:
                for alt in alt_abilities:
                    if alt[0] and alt[0] not in ['[]', '["Unknown"]', '["See PTE Rules"]', 'null']:
                        abilities = alt[0]
                        duplicates_resolved += 1
                        print(f"  Found better abilities for {clean_name}")
                        break
        
        try:
            c.execute("""
                INSERT INTO pokemon_clean 
                (name, stats, capabilities, skills, abilities, HP, Atk, Def, SpA, SpD, Spe)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data['name'], data['stats'], data['capabilities'], 
                data['skills'], abilities, 
                hp, atk, defense, spa, spd, spe
            ))
            inserted += 1
        except Exception as e:
            print(f"Error inserting {clean_name}: {e}")
    
    # Replace old table
    print("\nReplacing old table...")
    c.execute("DROP TABLE pokemon")
    c.execute("ALTER TABLE pokemon_clean RENAME TO pokemon")
    
    # Verify
    c.execute("SELECT COUNT(*) FROM pokemon")
    new_total = c.fetchone()[0]
    
    conn.commit()
    
    print(f"\n✅ CLEANUP COMPLETE!")
    print(f"Before: {len(rows)} rows")
    print(f"After: {new_total} rows")
    print(f"Removed: {len(rows) - new_total} duplicate rows")
    print(f"Resolved {duplicates_resolved} ability merges")
    
    # Show stats about what we kept
    print("\n📊 STATISTICS:")
    c.execute("SELECT COUNT(*) FROM pokemon WHERE HP > 0 AND Atk > 0 AND Def > 0")
    print(f"Pokémon with complete stats: {c.fetchone()[0]}")
    
    c.execute("SELECT COUNT(*) FROM pokemon WHERE abilities NOT IN ('[]', '[\"Unknown\"]', '[\"See PTE Rules\"]', 'null')")
    print(f"Pokémon with abilities: {c.fetchone()[0]}")
    
    c.execute("SELECT COUNT(*) FROM pokemon WHERE capabilities IS NOT NULL AND capabilities != ''")
    print(f"Pokémon with capabilities: {c.fetchone()[0]}")
    
    # Show sample
    print("\n✅ Sample of cleaned Pokémon:")
    c.execute("""
        SELECT name, HP, Atk, Def, SpA, SpD, Spe, 
               CASE WHEN abilities NOT IN ('[]', '[\"Unknown\"]', '[\"See PTE Rules\"]', 'null') THEN '✓' ELSE '✗' END as has_abilities
        FROM pokemon 
        WHERE HP > 0 
        ORDER BY RANDOM() 
        LIMIT 10
    """)
    
    for row in c.fetchall():
        name, hp, atk, defense, spa, spd, spe, has_abilities = row
        print(f"  {name:25} HP:{hp:3} Atk:{atk:3} Def:{defense:3} SpA:{spa:3} SpD:{spd:3} Spe:{spe:3} Abilities:{has_abilities}")
    
    conn.close()
    return new_total

def clean_name_properly(name):
    """PROPERLY clean those fucked up TOC names."""
    if not name or not isinstance(name, str):
        return ""
    
    # Remove ALL trailing dots and spaces
    clean = re.sub(r'[\s\.]+$', '', name)
    
    # Remove leading dots and spaces
    clean = re.sub(r'^[\s\.]+', '', clean)
    
    # Replace multiple spaces/dots with single space
    clean = re.sub(r'[\s\.]+', ' ', clean)
    
    # Remove anything in parentheses that's just dots
    clean = re.sub(r'\([\.\s]+\)', '', clean)
    
    # Special cases
    if clean.startswith('(') and clean.endswith(')'):
        clean = clean[1:-1]
    
    # Remove common garbage
    garbage = ['...', '..', '. .', ' .', '. ']
    for g in garbage:
        clean = clean.replace(g, ' ')
    
    # Final cleanup
    clean = re.sub(r'\s+', ' ', clean).strip()
    
    # Remove trailing page numbers or other numbers
    clean = re.sub(r'\s+\d+$', '', clean)
    
    return clean

def verify_and_fix_stats():
    """Make sure all stats are properly filled."""
    print("\n" + "="*80)
    print("VERIFYING AND FIXING STATS")
    print("="*80)
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # Find Pokémon with stats JSON but missing individual stats
    c.execute("""
        SELECT name, stats, HP, Atk, Def, SpA, SpD, Spe 
        FROM pokemon 
        WHERE (HP = 0 OR Atk = 0 OR Def = 0) 
        AND stats IS NOT NULL AND stats != '' AND stats != '{}'
    """)
    
    rows = c.fetchall()
    print(f"Found {len(rows)} Pokémon with missing stats but stats JSON")
    
    fixed = 0
    for name, stats_json, hp, atk, defense, spa, spd, spe in rows:
        try:
            stats_dict = json.loads(stats_json)
            
            # Extract values with multiple possible keys
            new_hp = (stats_dict.get('HP') or stats_dict.get('hp') or 
                     next((v for k, v in stats_dict.items() if 'hp' in k.lower()), hp))
            new_atk = (stats_dict.get('Attack') or stats_dict.get('Atk') or stats_dict.get('attack') or 
                      next((v for k, v in stats_dict.items() if 'attack' in k.lower() or 'atk' in k.lower()), atk))
            new_def = (stats_dict.get('Defense') or stats_dict.get('Def') or stats_dict.get('defense') or 
                      next((v for k, v in stats_dict.items() if 'defense' in k.lower() or 'def' in k.lower()), defense))
            new_spa = (stats_dict.get('Special Attack') or stats_dict.get('SpAtk') or stats_dict.get('SpA') or 
                      next((v for k, v in stats_dict.items() if 'special attack' in k.lower() or 'spatk' in k.lower()), spa))
            new_spd = (stats_dict.get('Special Defense') or stats_dict.get('SpDef') or stats_dict.get('SpD') or 
                      next((v for k, v in stats_dict.items() if 'special defense' in k.lower() or 'spdef' in k.lower()), spd))
            new_spe = (stats_dict.get('Speed') or stats_dict.get('Spe') or 
                      next((v for k, v in stats_dict.items() if 'speed' in k.lower() or 'spe' in k.lower()), spe))
            
            # Convert to int
            new_hp = int(new_hp) if new_hp else 0
            new_atk = int(new_atk) if new_atk else 0
            new_def = int(new_def) if new_def else 0
            new_spa = int(new_spa) if new_spa else 0
            new_spd = int(new_spd) if new_spd else 0
            new_spe = int(new_spe) if new_spe else 0
            
            # Update if we found better stats
            if new_hp != hp or new_atk != atk or new_def != defense:
                c.execute("""
                    UPDATE pokemon 
                    SET HP=?, Atk=?, Def=?, SpA=?, SpD=?, Spe=?
                    WHERE name=?
                """, (new_hp, new_atk, new_def, new_spa, new_spd, new_spe, name))
                fixed += 1
                print(f"  Fixed {name}: HP:{new_hp} Atk:{new_atk} Def:{new_def}")
                
        except Exception as e:
            print(f"  Error fixing {name}: {e}")
    
    conn.commit()
    print(f"\n✅ Fixed {fixed} Pokémon stats from JSON")
    
    # Also fix any remaining string stats
    print("\nFixing any remaining string stats...")
    c.execute("""
        UPDATE pokemon 
        SET HP = CAST(HP AS INTEGER),
            Atk = CAST(Atk AS INTEGER),
            Def = CAST(Def AS INTEGER),
            SpA = CAST(SpA AS INTEGER),
            SpD = CAST(SpD AS INTEGER),
            Spe = CAST(Spe AS INTEGER)
        WHERE typeof(HP) = 'text' OR typeof(Atk) = 'text' OR typeof(Def) = 'text'
    """)
    
    conn.commit()
    conn.close()

def fix_common_duplicates_manually():
    """Manually fix the worst duplicates."""
    print("\n" + "="*80)
    print("MANUAL FIX FOR COMMON DUPLICATES")
    print("="*80)
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # First, let's see the worst offenders
    c.execute("""
        SELECT name, COUNT(*) as count 
        FROM pokemon 
        GROUP BY name 
        HAVING COUNT(*) > 1
        ORDER BY count DESC
        LIMIT 20
    """)
    
    duplicates = c.fetchall()
    
    if not duplicates:
        print("No duplicates found!")
        conn.close()
        return
    
    print(f"Found {len(duplicates)} duplicated names:")
    for name, count in duplicates:
        print(f"  {name:40} -> {count} copies")
        
        # Show the different versions
        c.execute("SELECT rowid, HP, Atk, Def, abilities FROM pokemon WHERE name = ?", (name,))
        versions = c.fetchall()
        for rowid, hp, atk, defense, abilities in versions:
            print(f"    Row {rowid}: HP:{hp} Atk:{atk} Def:{defense} Abilities:{abilities[:50]}")
    
    # For each duplicate, keep the best one
    deleted_total = 0
    for name, count in duplicates:
        # Get all rows for this name
        c.execute("SELECT rowid, HP, Atk, Def, abilities, capabilities FROM pokemon WHERE name = ?", (name,))
        rows = c.fetchall()
        
        # Score each row
        scored_rows = []
        for rowid, hp, atk, defense, abilities, capabilities in rows:
            score = 0
            if hp and hp > 0: score += 1
            if atk and atk > 0: score += 1
            if defense and defense > 0: score += 1
            if abilities and abilities not in ['[]', '["Unknown"]', '["See PTE Rules"]']:
                score += 2
            if capabilities and capabilities.strip():
                score += 1
            
            scored_rows.append((rowid, score))
        
        # Keep the one with highest score
        scored_rows.sort(key=lambda x: x[1], reverse=True)
        keep_rowid = scored_rows[0][0]
        
        # Delete the rest
        for rowid, score in scored_rows[1:]:
            c.execute("DELETE FROM pokemon WHERE rowid = ?", (rowid,))
            deleted_total += 1
    
    conn.commit()
    print(f"\n✅ Deleted {deleted_total} duplicate rows")
    conn.close()

def check_venipede_situation():
    """Check the Venipede situation specifically."""
    print("\n" + "="*80)
    print("CHECKING VENIPEDE SITUATION")
    print("="*80)
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # Check all variations of Venipede
    c.execute("SELECT name, HP, Atk, Def, abilities FROM pokemon WHERE name LIKE '%Venipede%'")
    venipedes = c.fetchall()
    
    print(f"Found {len(venipedes)} Venipede variations:")
    for name, hp, atk, defense, abilities in venipedes:
        print(f"  '{name}' - HP:{hp} Atk:{atk} Def:{defense} Abilities:{abilities}")
    
    # Check Whirlipede
    c.execute("SELECT name, HP, Atk, Def, abilities FROM pokemon WHERE name LIKE '%Whirlipede%'")
    whirlipedes = c.fetchall()
    
    print(f"\nFound {len(whirlipedes)} Whirlipede variations:")
    for name, hp, atk, defense, abilities in whirlipedes:
        print(f"  '{name}' - HP:{hp} Atk:{atk} Def:{defense} Abilities:{abilities}")
    
    conn.close()

def final_check():
    """Final verification of the database."""
    print("\n" + "="*80)
    print("FINAL DATABASE CHECK")
    print("="*80)
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # Basic counts
    c.execute("SELECT COUNT(*) FROM pokemon")
    total = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM pokemon WHERE HP > 0 AND Atk > 0 AND Def > 0")
    with_stats = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM pokemon WHERE abilities NOT IN ('[]', '[\"Unknown\"]', '[\"See PTE Rules\"]', 'null', '')")
    with_abilities = c.fetchone()[0]
    
    print(f"Total Pokémon: {total}")
    print(f"With complete stats: {with_stats}")
    print(f"With abilities: {with_abilities}")
    print(f"Missing stats: {total - with_stats}")
    print(f"Missing abilities: {total - with_abilities}")
    
    # Check for obvious problems
    print("\n⚠️  Common problems:")
    
    # Pokémon with no stats
    c.execute("SELECT name FROM pokemon WHERE HP = 0 AND Atk = 0 AND Def = 0 LIMIT 10")
    no_stats = c.fetchall()
    if no_stats:
        print(f"  Pokémon with no stats (first 10):")
        for name, in no_stats:
            print(f"    {name}")
    
    # Pokémon with bad abilities
    c.execute("SELECT name FROM pokemon WHERE abilities IN ('[]', '[\"Unknown\"]', '[\"See PTE Rules\"]', 'null', '') LIMIT 10")
    bad_abilities = c.fetchall()
    if bad_abilities:
        print(f"  Pokémon with bad abilities (first 10):")
        for name, in bad_abilities:
            print(f"    {name}")
    
    conn.close()

def main():
    """Run the complete cleanup."""
    print("DATABASE MEGA CLEANUP")
    print("="*80)
    
    # Backup first
    import shutil
    try:
        shutil.copy2('database.db', 'database_backup_before_cleanup.db')
        print("✅ Created backup: database_backup_before_cleanup.db")
    except:
        print("⚠️  Could not create backup")
    
    print("\n1. Fixing database (main cleanup)...")
    fix_database_for_real()
    
    print("\n2. Verifying and fixing stats...")
    verify_and_fix_stats()
    
    print("\n3. Checking Venipede situation...")
    check_venipede_situation()
    
    print("\n4. Final database check...")
    final_check()
    
    print("\n" + "="*80)
    print("CLEANUP COMPLETE!")
    print("="*80)
    print("\nNext steps:")
    print("1. Restart your Flask app")
    print("2. Check http://localhost:5000/pokemon")
    print("3. Search for 'Venipede' to verify it's fixed")
    print("4. If still issues, restore from backup and run again")

if __name__ == "__main__":
    main()