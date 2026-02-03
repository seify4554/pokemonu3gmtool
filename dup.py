import sqlite3
import sys

def kill_duplicates():
    """Murder those duplicate Pokémon entries."""
    print("=" * 60)
    print("POKÉMON DUPLICATE EXECUTIONER")
    print("Time to clean this mess up...")
    print("=" * 60)
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # Check for duplicates
    c.execute("""
        SELECT name, COUNT(*) as count
        FROM pokemon
        GROUP BY name
        HAVING COUNT(*) > 1
        ORDER BY count DESC
    """)
    
    duplicates = c.fetchall()
    
    if not duplicates:
        print("No duplicates found. Your database is clean!")
        conn.close()
        return
    
    print(f"\nFound {len(duplicates)} Pokémon with duplicates:")
    print("-" * 40)
    
    for name, count in duplicates[:20]:  # Show first 20
        print(f"{name}: {count} copies")
    
    if len(duplicates) > 20:
        print(f"... and {len(duplicates) - 20} more")
    
    print("\n" + "=" * 60)
    print("KILLING DUPLICATES...")
    print("=" * 60)
    
    # Method 1: Keep the one with the most complete data
    # Delete all but the row with the highest sum of stats
    c.execute("""
        DELETE FROM pokemon 
        WHERE rowid NOT IN (
            SELECT rowid FROM (
                SELECT rowid,
                       (COALESCE(HP, 0) + COALESCE(Atk, 0) + COALESCE(Def, 0) + 
                        COALESCE(SpA, 0) + COALESCE(SpD, 0) + COALESCE(Spe, 0)) as stat_total
                FROM pokemon
                WHERE name = ?
                ORDER BY stat_total DESC, rowid
                LIMIT 1
            )
        ) AND name = ?
    """, (duplicates[0][0], duplicates[0][0]))  # Just for one Pokémon for testing
    
    # Actually, let's do it for ALL duplicates
    print("\nProcessing duplicates...")
    deleted_count = 0
    
    for name, count in duplicates:
        # Find which duplicate to keep (the one with most stats filled)
        c.execute("""
            SELECT rowid, 
                   COALESCE(HP, -1) as hp,
                   COALESCE(Atk, -1) as atk,
                   COALESCE(Def, -1) as def,
                   COALESCE(SpA, -1) as spa,
                   COALESCE(SpD, -1) as spd,
                   COALESCE(Spe, -1) as spe
            FROM pokemon 
            WHERE name = ?
        """, (name,))
        
        entries = c.fetchall()
        
        # Score each entry (more stats = better)
        scored = []
        for row in entries:
            rowid, hp, atk, defense, spa, spd, spe = row
            score = 0
            if hp >= 0: score += 1
            if atk >= 0: score += 1
            if defense >= 0: score += 1
            if spa >= 0: score += 1
            if spd >= 0: score += 1
            if spe >= 0: score += 1
            
            # Bonus for having abilities or capabilities
            c2 = conn.cursor()
            c2.execute("SELECT abilities, capabilities FROM pokemon WHERE rowid = ?", (rowid,))
            ab_data = c2.fetchone()
            if ab_data:
                abilities, capabilities = ab_data
                if abilities and abilities != '[]' and abilities != '["Unknown"]':
                    score += 2
                if capabilities and capabilities.strip():
                    score += 1
            
            scored.append((rowid, score))
        
        # Keep the one with highest score, if tie, keep lowest rowid
        scored.sort(key=lambda x: (-x[1], x[0]))
        keep_rowid = scored[0][0]
        
        # Delete the rest
        c.execute("""
            DELETE FROM pokemon 
            WHERE name = ? AND rowid != ?
        """, (name, keep_rowid))
        
        deleted = c.rowcount
        deleted_count += deleted
        
        if deleted > 0:
            print(f"  {name}: Kept 1, deleted {deleted} duplicates")
    
    conn.commit()
    
    # Verify cleanup
    c.execute("""
        SELECT name, COUNT(*) as count
        FROM pokemon
        GROUP BY name
        HAVING COUNT(*) > 1
    """)
    
    remaining_dups = c.fetchall()
    
    print("\n" + "=" * 60)
    if not remaining_dups:
        print("✅ SUCCESS: All duplicates eliminated!")
        print(f"Total duplicates deleted: {deleted_count}")
    else:
        print("⚠️  WARNING: Some duplicates remain:")
        for name, count in remaining_dups:
            print(f"  {name}: {count} copies")
    
    # Show final counts
    c.execute("SELECT COUNT(*) FROM pokemon")
    total = c.fetchone()[0]
    
    c.execute("SELECT COUNT(DISTINCT name) FROM pokemon")
    unique = c.fetchone()[0]
    
    print(f"\nFinal stats:")
    print(f"Total rows: {total}")
    print(f"Unique Pokémon: {unique}")
    
    if total == unique:
        print("✅ Database is clean!")
    else:
        print(f"⚠️  Still have {total - unique} extra rows")
    
    conn.close()

def nuke_and_rebuild():
    """COMPLETE NUKING - If duplicates are really fucked up."""
    print("\n" + "=" * 60)
    print("⚠️  NUCLEAR OPTION: Complete Database Rebuild")
    print("=" * 60)
    print("This will:")
    print("1. Create a new clean table")
    print("2. Copy only unique Pokémon")
    print("3. Keep the best version of each")
    print("4. Delete the old messed up table")
    print("\nARE YOU SURE? (Type 'NUKE' to continue)")
    
    if input("> ").strip().upper() != "NUKE":
        print("Cancelled.")
        return
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # Create backup table
    c.execute("CREATE TABLE IF NOT EXISTS pokemon_backup AS SELECT * FROM pokemon WHERE 1=0")
    c.execute("DELETE FROM pokemon_backup")
    
    # Get all unique Pokémon with their best entry
    c.execute("""
        INSERT INTO pokemon_backup
        SELECT DISTINCT *
        FROM (
            SELECT p1.*
            FROM pokemon p1
            LEFT JOIN pokemon p2 ON (
                p1.name = p2.name AND 
                (
                    (COALESCE(p2.HP, -1) > COALESCE(p1.HP, -1)) OR
                    (COALESCE(p2.HP, -1) = COALESCE(p1.HP, -1) AND COALESCE(p2.Atk, -1) > COALESCE(p1.Atk, -1))
                )
            )
            WHERE p2.name IS NULL
        )
        ORDER BY name
    """)
    
    # Count
    c.execute("SELECT COUNT(*) FROM pokemon_backup")
    backup_count = c.fetchone()[0]
    
    # Drop old table and rename
    c.execute("DROP TABLE pokemon")
    c.execute("ALTER TABLE pokemon_backup RENAME TO pokemon")
    
    conn.commit()
    conn.close()
    
    print(f"\n✅ NUKE COMPLETE: Rebuilt with {backup_count} unique Pokémon")

if __name__ == "__main__":
    print("Choose an option:")
    print("1. Kill duplicates (smart cleanup)")
    print("2. Nuclear option (complete rebuild)")
    print("3. Just show duplicates without deleting")
    
    choice = input("> ").strip()
    
    if choice == "1":
        kill_duplicates()
    elif choice == "2":
        nuke_and_rebuild()
    elif choice == "3":
        # Just show duplicates
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        
        c.execute("""
            SELECT name, COUNT(*) as count,
                   GROUP_CONCAT(rowid) as ids,
                   GROUP_CONCAT(COALESCE(HP, 'NULL')) as hps
            FROM pokemon
            GROUP BY name
            HAVING COUNT(*) > 1
            ORDER BY count DESC
        """)
        
        dups = c.fetchall()
        
        if dups:
            print(f"\nFound {len(dups)} duplicates:")
            print("-" * 60)
            for name, count, ids, hps in dups[:50]:
                print(f"{name}: {count} copies")
                print(f"  Row IDs: {ids}")
                print(f"  HP values: {hps}")
                print()
        else:
            print("No duplicates found!")
        
        conn.close()
    else:
        print("Invalid choice")