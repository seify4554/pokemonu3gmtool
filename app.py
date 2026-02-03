from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import sqlite3
import random
import json
import math
import csv
import io

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # For flash messages

def get_db():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/pokemon', methods=['GET', 'POST'])
def pokemon():
    conn = get_db()
    c = conn.cursor()
    results = []
    search = ''
    
    if request.method == 'POST':
        search = request.form.get('search', '').strip()
        # FIXED QUERY: Only select columns that exist after cleanup
        c.execute("""
            SELECT 
                name,
                HP,
                Atk AS Attack,
                Def AS Defense,
                SpA AS SpAtk,
                SpD AS SpDef,
                Spe AS Speed,
                capabilities,
                skills,
                abilities,
                stats
            FROM pokemon 
            WHERE name LIKE ? 
            ORDER BY name
        """, (f"%{search}%",))
        results = c.fetchall()
    else:
        # Show first 50
        c.execute("""
            SELECT 
                name,
                HP,
                Atk AS Attack,
                Def AS Defense,
                SpA AS SpAtk,
                SpD AS SpDef,
                Spe AS Speed,
                capabilities,
                skills,
                abilities
            FROM pokemon 
            ORDER BY name 
            LIMIT 50
        """)
        results = c.fetchall()
    
    conn.close()
    return render_template('pokemon.html', results=results, search=search)

@app.route('/moves', methods=['GET', 'POST'])
def moves():
    conn = get_db()
    c = conn.cursor()
    results = []
    search = ''
    if request.method == 'POST':
        search = request.form.get('search', '').strip()
        c.execute("SELECT name, ac, damage, effect FROM moves WHERE name LIKE ? ORDER BY name", (f"%{search}%",))
        results = c.fetchall()
    conn.close()
    return render_template('moves.html', results=results, search=search)

@app.route('/exp_calc', methods=['GET', 'POST'])
def exp_calc():
    result = ""
    if request.method == 'POST':
        try:
            exp_needed = int(request.form['exp_needed'])
            base_exp = int(request.form['base_exp'])
            defeated_level = int(request.form['defeated_level'])
            gaining_level = int(request.form['gaining_level'])
            growth_rate = request.form['growth_rate'].lower().strip()
            stored = request.form.get('stored') == 'yes'
            stored_exp_value = int(request.form.get('stored_exp', 0)) if stored else 0

            multipliers = {
                "erratic": [(1, 30, 1.2), (31, 60, 1.0), (61, 100, 0.8)],
                "fast": [(1, 30, 1.1), (31, 60, 1.1), (61, 100, 1.1)],
                "medium fast": [(1, 30, 1.0), (31, 60, 1.0), (61, 100, 1.0)],
                "medium slow": [(1, 30, 0.9), (31, 60, 1.0), (61, 100, 1.1)],
                "slow": [(1, 30, 0.8), (31, 60, 0.9), (61, 100, 1.0)],
            }
            if growth_rate not in multipliers:
                result = "Invalid growth rate. Use: erratic, fast, medium fast, medium slow, slow"
            else:
                multiplier = 0
                for start, end, mult in multipliers[growth_rate]:
                    if start <= gaining_level <= end:
                        multiplier = mult
                        break
                if multiplier == 0:
                    result = "Level out of range for this growth rate"
                else:
                    base_exp_value = (base_exp * defeated_level) / 7
                    exp_gained = base_exp_value * multiplier
                    exp_gained_rounded = round(exp_gained)
                    total_exp = stored_exp_value + exp_gained_rounded
                    result = f"EXP Gained: <strong>{exp_gained_rounded}</strong><br>Total: <strong>{total_exp} / {exp_needed}</strong>"
        except Exception as e:
            result = f"Error: {str(e)} — check your numbers"
    return render_template('exp_calc.html', result=result)

@app.route('/level_up', methods=['GET', 'POST'])
def level_up():
    result = None
    if request.method == 'POST':
        try:
            rolls_count = int(request.form['rolls_count'])
            is_neutral = request.form.get('is_neutral') == 'yes'
            boosted = request.form.get('boosted_stat') if not is_neutral else None
            hindered = request.form.get('hindered_stat') if not is_neutral else None

            stats = ['HP', 'Attack', 'Defense', 'Special Attack', 'Special Defense', 'Speed']
            total = {s: 0 for s in stats}

            for _ in range(rolls_count):
                for stat in stats:
                    roll = random.randint(1, 2)
                    mod = roll
                    if not is_neutral:
                        if stat == boosted: mod += 1
                        if stat == hindered: mod = max(mod - 1, 0)
                    total[stat] += mod

            result = total
        except:
            result = "Invalid input"
    return render_template('level_up.html', result=result)

@app.route('/severity', methods=['GET', 'POST'])
def severity():
    result = None
    if request.method == 'POST':
        sev = random.randint(1, 10)
        if sev == 1: num, lev, extra = 1, "equal to your weakest", ""
        elif sev == 2: num, lev, extra = 1, "+1 above your weakest", ""
        elif sev == 3: num, lev, extra = 2, "+2 above your weakest", ""
        elif sev == 4: num, lev, extra = 2, "midpoint between weakest and strongest", ""
        elif sev == 5: num, lev, extra = 3, "equal to your strongest", ""
        elif sev == 6: num, lev, extra = 3, "+1 above your strongest", ""
        elif sev == 7: num, lev, extra = 4, "+2 above your strongest", ""
        elif sev == 8: num, lev, extra = 5, "+3 above your strongest", ""
        elif sev == 9: num, lev, extra = 6, "+4 above your strongest", "1 evolved"
        else: num, lev, extra = 6, "+5 above your strongest", f"{random.randint(1,2)} evolved (optimized movesets)"
        result = f"<strong>Severity {sev}</strong><br>{num} Pokémon<br>Level: {lev}<br>{extra}"
    return render_template('severity.html', result=result)


@app.route('/encounters', methods=['GET', 'POST'])
def encounters():
    conn = get_db()
    c = conn.cursor()
    message = ""
    tables = []
    
    try:
        tables_raw = c.execute("SELECT table_name FROM encounters").fetchall()
        tables = [t['table_name'] for t in tables_raw]
    except:
        c.execute('''CREATE TABLE IF NOT EXISTS encounters
                     (table_name TEXT PRIMARY KEY, data TEXT)''')
        conn.commit()
        tables = []
    
    # Get Pokémon names for the form
    pokemons_raw = c.execute("SELECT name, stats FROM pokemon ORDER BY name").fetchall()
    pokemons = {}
    for p in pokemons_raw:
        try:
            name = p['name'].replace('.', '').strip()
            stats_str = p['stats']
            if stats_str:
                try:
                    stats = json.loads(stats_str)
                except json.JSONDecodeError:
                    stats = {}
            else:
                stats = {}
            pokemons[name] = stats
        except Exception as e:
            print(f"Error processing {p['name']}: {e}")
            pokemons[p['name'].replace('.', '').strip()] = {}
    
    results = []
    selected_table = None
    mode = request.args.get('mode', 'manual')
    
    if request.method == 'POST':
        action = request.form.get('action')
        table_name = request.form.get('table_name')
        mode = request.form.get('mode', 'manual')
        
        if action == 'create':
            # Create table logic
            table_name = request.form.get('table_name')
            min_lv = int(request.form.get('min_lv', 5))
            max_lv = int(request.form.get('max_lv', 15))
            
            data = {
                'level_range': [min_lv, max_lv],
                'common': json.loads(request.form.get('common', '[]')),
                'uncommon': json.loads(request.form.get('uncommon', '[]')),
                'rare': json.loads(request.form.get('rare', '[]')),
                'vrare': json.loads(request.form.get('vrare', '[]'))
            }
            
            c.execute("INSERT OR REPLACE INTO encounters (table_name, data) VALUES (?, ?)",
                     (table_name, json.dumps(data)))
            conn.commit()
            tables.append(table_name)
            message = f"Table '{table_name}' saved!"
            
        elif action == 'delete':
            # Delete table logic
            table_name = request.form.get('table_name')
            if table_name:
                c.execute("DELETE FROM encounters WHERE table_name=?", (table_name,))
                conn.commit()
                if table_name in tables:
                    tables.remove(table_name)
                message = f"Table '{table_name}' deleted!"
            
        elif action == 'roll':
            # Clear previous results when rolling
            results = []
            
            num_rolls = int(request.form.get('num_rolls', 1))
            row = c.execute("SELECT data FROM encounters WHERE table_name=?", (table_name,)).fetchone()
            
            if row:
                try:
                    data = json.loads(row['data'])
                except json.JSONDecodeError:
                    message = f"Error loading table '{table_name}' data!"
                    conn.close()
                    return render_template('encounters.html', tables=tables, message=message, results=results, pokemons=list(pokemons.keys()), mode=mode)
                
                # WEIGHTED SEVERITY SYSTEM
                severity_weights = [
                    (1, 0.30),   # 30% chance
                    (2, 0.20),   # 20% chance
                    (3, 0.15),   # 15% chance
                    (4, 0.10),   # 10% chance
                    (5, 0.07),   # 7% chance
                    (6, 0.06),   # 6% chance
                    (7, 0.05),   # 5% chance
                    (8, 0.03),   # 3% chance
                    (9, 0.02),   # 2% chance
                    (10, 0.02)   # 2% chance
                ]
                
                for roll_num in range(num_rolls):
                    if mode == 'manual':
                        # Manual mode - single Pokémon rolls
                        r = random.random()
                        if r < 0.6:
                            pool = data.get('common', [])
                        elif r < 0.9:
                            pool = data.get('uncommon', [])
                        elif r < 0.99:
                            pool = data.get('rare', [])
                        else:
                            pool = data.get('vrare', [])
                        
                        if not pool:
                            continue
                        
                        poke_name = random.choice(pool)
                        
                        # Shiny check
                        shiny = random.random() < 0.002
                        
                        lvl = random.randint(*data['level_range'])
                        nature = random.choice(["Adamant","Modest","Timid","Jolly","Bold","Calm","Impish","Lax","Relaxed","Sassy","Gentle","Hasty","Naive","Naughty","Rash","Brave","Quiet","Mild","Lonely","Hardy","Docile","Quirky","Serious","Bashful"])
                        gender = "♂" if random.random() < 0.5 else "♀"
                        
                        # Stats calculation
                        base_stats = pokemons.get(poke_name, {})
                        level_stats = {k: random.randint(1, 3) * lvl // 5 for k in base_stats}
                        nature_bonus = {k: math.floor((base_stats.get(k, 0) + level_stats.get(k,0)) * 0.1) for k in base_stats}
                        final_stats = {k: base_stats.get(k,0) + level_stats.get(k,0) + nature_bonus.get(k,0) for k in base_stats}
                        
                        # HP formula
                        hp_base = base_stats.get('HP',0)
                        hp_levelup = level_stats.get('HP',0)
                        hp_bonus = nature_bonus.get('HP',0)
                        hp_total = lvl + (hp_base + hp_levelup + hp_bonus) * 3
                        
                        # Build result string
                        shiny_prefix = "✨ " if shiny else ""
                        
                        stat_lines = [f"{k}: {base_stats.get(k,0)} / {level_stats.get(k,0)} ({'+' if nature_bonus[k]>=0 else ''}{nature_bonus[k]}) / {final_stats[k]}" for k in final_stats if k != 'HP']
                        stat_lines.insert(0, f"Hit Points: {hp_total} HP: {hp_base} / {hp_levelup} ({'+' if hp_bonus>=0 else ''}{hp_bonus}) / {hp_total}")
                        
                        results.append(f"{shiny_prefix}{poke_name} Lv.{lvl} — {nature} — {gender}<br>" + "<br>".join(stat_lines))
                    
                    else:  # mode == 'auto'
                        # Auto mode: need team levels for severity calculation
                        team_levels = []
                        for i in range(1, 7):
                            level_str = request.form.get(f'team_level_{i}')
                            if level_str and level_str.strip():
                                try:
                                    team_levels.append(int(level_str))
                                except ValueError:
                                    continue
                        
                        if not team_levels:
                            message = "Please enter at least one team member level for auto mode!"
                            conn.close()
                            return render_template('encounters.html', tables=tables, message=message, results=results, pokemons=list(pokemons.keys()), mode=mode)
                        
                        # Roll weighted severity
                        severities, weights = zip(*severity_weights)
                        sev = random.choices(severities, weights=weights, k=1)[0]
                        
                        weakest = min(team_levels)
                        strongest = max(team_levels)
                        
                        # CORRECTED: Determine number of Pokémon and level based on severity
                        if sev == 1:
                            num_pokemon, base_level = 1, weakest
                            level_desc = f"equal to weakest ({weakest})"
                        elif sev == 2:
                            num_pokemon, base_level = 1, weakest + 1
                            level_desc = f"+1 above weakest ({weakest} → {weakest+1})"
                        elif sev == 3:
                            num_pokemon, base_level = 2, weakest + 2
                            level_desc = f"+2 above weakest ({weakest} → {weakest+2})"
                        elif sev == 4:
                            num_pokemon, base_level = 2, (weakest + strongest) // 2
                            level_desc = f"midpoint between {weakest} and {strongest} ({weakest+strongest})/2 = {(weakest+strongest)//2}"
                        elif sev == 5:
                            num_pokemon, base_level = 3, strongest
                            level_desc = f"equal to strongest ({strongest})"
                        elif sev == 6:
                            num_pokemon, base_level = 3, strongest + 1
                            level_desc = f"+1 above strongest ({strongest} → {strongest+1})"
                        elif sev == 7:
                            num_pokemon, base_level = 4, strongest + 2
                            level_desc = f"+2 above strongest ({strongest} → {strongest+2})"
                        elif sev == 8:
                            num_pokemon, base_level = 5, strongest + 3
                            level_desc = f"+3 above strongest ({strongest} → {strongest+3})"
                        elif sev == 9:
                            num_pokemon, base_level = 6, strongest + 4
                            level_desc = f"+4 above strongest ({strongest} → {strongest+4})"
                        else:  # sev == 10
                            num_pokemon, base_level = 6, strongest + 5
                            level_desc = f"+5 above strongest ({strongest} → {strongest+5})"
                        
                        # Ensure level doesn't go below 1
                        base_level = max(1, base_level)
                        
                        # Add evolution info for higher severities
                        extra_info = ""
                        if sev == 9:
                            extra_info = " (1 Pokémon will be evolved)"
                        elif sev == 10:
                            extra_info = f" ({random.randint(1,2)} Pokémon will be evolved)"
                        
                        # Add header for this encounter - only once per roll
                        header_added = False
                        encounter_results = []
                        
                        # Generate multiple Pokémon for this encounter
                        for pokemon_num in range(num_pokemon):
                            # Decide if this Pokémon should be evolved (for severity 9/10)
                            is_evolved = False
                            if sev == 9 and pokemon_num == 0:  # First Pokémon evolved
                                is_evolved = True
                            elif sev == 10 and pokemon_num < random.randint(1, 2):  # 1-2 Pokémon evolved
                                is_evolved = True
                            
                            # Shiny check (1/500)
                            shiny = random.random() < 0.002
                            
                            # Roll for Pokémon from table
                            r = random.random()
                            if r < 0.6:
                                pool = data.get('common', [])
                            elif r < 0.9:
                                pool = data.get('uncommon', [])
                            elif r < 0.99:
                                pool = data.get('rare', [])
                            else:
                                pool = data.get('vrare', [])
                            
                            if not pool:
                                continue
                            
                            poke_name = random.choice(pool)
                            
                            # If evolved, try to find evolved form (simplified logic)
                            if is_evolved:
                                evolved_forms = {
                                    "Charmander": "Charmeleon", "Charmeleon": "Charizard",
                                    "Squirtle": "Wartortle", "Wartortle": "Blastoise",
                                    "Bulbasaur": "Ivysaur", "Ivysaur": "Venusaur",
                                    "Caterpie": "Metapod", "Metapod": "Butterfree",
                                    "Weedle": "Kakuna", "Kakuna": "Beedrill",
                                    "Pidgey": "Pidgeotto", "Pidgeotto": "Pidgeot",
                                    "Rattata": "Raticate", "Spearow": "Fearow",
                                    "Ekans": "Arbok", "Pikachu": "Raichu",
                                    "Sandshrew": "Sandslash", "Nidoran♀": "Nidorina",
                                    "Nidoran♂": "Nidorino", "Clefairy": "Clefable",
                                    "Vulpix": "Ninetales", "Jigglypuff": "Wigglytuff",
                                    "Zubat": "Golbat", "Oddish": "Gloom",
                                    "Paras": "Parasect", "Venonat": "Venomoth",
                                    "Diglett": "Dugtrio", "Meowth": "Persian",
                                    "Psyduck": "Golduck", "Mankey": "Primeape",
                                    "Growlithe": "Arcanine", "Poliwag": "Poliwhirl",
                                    "Abra": "Kadabra", "Machop": "Machoke",
                                    "Bellsprout": "Weepinbell", "Tentacool": "Tentacruel",
                                    "Geodude": "Graveler", "Ponyta": "Rapidash",
                                    "Slowpoke": "Slowbro", "Magnemite": "Magneton",
                                    "Doduo": "Dodrio", "Seel": "Dewgong",
                                    "Grimer": "Muk", "Shellder": "Cloyster",
                                    "Gastly": "Haunter", "Onix": "Steelix",
                                    "Drowzee": "Hypno", "Krabby": "Kingler",
                                    "Voltorb": "Electrode", "Exeggcute": "Exeggutor",
                                    "Cubone": "Marowak", "Koffing": "Weezing",
                                    "Rhyhorn": "Rhydon", "Horsea": "Seadra",
                                    "Goldeen": "Seaking", "Staryu": "Starmie",
                                    "Magikarp": "Gyarados", "Eevee": ["Vaporeon", "Jolteon", "Flareon"]
                                }
                                
                                if poke_name in evolved_forms:
                                    evolved_name = evolved_forms[poke_name]
                                    if isinstance(evolved_name, list):
                                        evolved_name = random.choice(evolved_name)
                                    if evolved_name in pokemons:
                                        poke_name = evolved_name
                            
                            lvl = base_level
                            
                            # Rest of the generation logic...
                            nature = random.choice(["Adamant","Modest","Timid","Jolly","Bold","Calm","Impish","Lax","Relaxed","Sassy","Gentle","Hasty","Naive","Naughty","Rash","Brave","Quiet","Mild","Lonely","Hardy","Docile","Quirky","Serious","Bashful"])
                            gender = "♂" if random.random() < 0.5 else "♀"
                            
                            # Stats calculation
                            base_stats = pokemons.get(poke_name, {})
                            level_stats = {k: random.randint(1, 3) * lvl // 5 for k in base_stats}
                            nature_bonus = {k: math.floor((base_stats.get(k, 0) + level_stats.get(k,0)) * 0.1) for k in base_stats}
                            final_stats = {k: base_stats.get(k,0) + level_stats.get(k,0) + nature_bonus.get(k,0) for k in base_stats}
                            
                            # HP formula
                            hp_base = base_stats.get('HP',0)
                            hp_levelup = level_stats.get('HP',0)
                            hp_bonus = nature_bonus.get('HP',0)
                            hp_total = lvl + (hp_base + hp_levelup + hp_bonus) * 3
                            
                            # Build result string
                            shiny_prefix = "✨ " if shiny else ""
                            evolved_prefix = "⚡ " if is_evolved else ""
                            
                            stat_lines = [f"{k}: {base_stats.get(k,0)} / {level_stats.get(k,0)} ({'+' if nature_bonus[k]>=0 else ''}{nature_bonus[k]}) / {final_stats[k]}" for k in final_stats if k != 'HP']
                            stat_lines.insert(0, f"Hit Points: {hp_total} HP: {hp_base} / {hp_levelup} ({'+' if hp_bonus>=0 else ''}{hp_bonus}) / {hp_total}")
                            
                            encounter_results.append(f"{evolved_prefix}{shiny_prefix}{poke_name} Lv.{lvl} — {nature} — {gender}<br>" + "<br>".join(stat_lines))
                        
                        # Add header and all Pokémon results to main results
                        results.append(f"<div class='alert alert-info'><strong>Encounter {roll_num+1} (Severity {sev}): {num_pokemon} Pokémon</strong><br>Level: {base_level} — {level_desc}{extra_info}</div>")
                        results.extend(encounter_results)
    
    conn.close()
    return render_template('encounters.html', tables=tables, message=message, results=results, pokemons=list(pokemons.keys()), mode=mode)

@app.route('/edit_move/<name>', methods=['GET', 'POST'])
def edit_move(name):
    conn = get_db()
    c = conn.cursor()
    
    if request.method == 'POST':
        ac = request.form.get('ac')
        damage = request.form.get('damage')
        effect = request.form.get('effect')
        
        # Convert empty AC to None (for DB)
        ac = int(ac) if ac and ac.strip().isdigit() else None
        
        c.execute("""
            UPDATE moves 
            SET ac = ?, damage = ?, effect = ? 
            WHERE name = ?
        """, (ac, damage, effect, name))
        conn.commit()
        conn.close()
        
        flash(f"Move '{name}' updated successfully!", "success")
        return redirect(url_for('moves'))
    
    # GET: show edit form
    c.execute("SELECT * FROM moves WHERE name = ?", (name,))
    move = c.fetchone()
    conn.close()
    
    if not move:
        flash("Move not found", "error")
        return redirect(url_for('moves'))
    
    return render_template('edit_move.html', move=move)

@app.route('/edit_pokemon/<name>', methods=['GET', 'POST'])
def edit_pokemon(name):
    conn = get_db()
    c = conn.cursor()
    
    if request.method == 'POST':
        hp = int(request.form.get('hp', 0))
        atk = int(request.form.get('atk', 0))
        defense = int(request.form.get('defense', 0))
        spa = int(request.form.get('spa', 0))
        spd = int(request.form.get('spd', 0))
        spe = int(request.form.get('spe', 0))
        capabilities = request.form.get('capabilities', '')
        skills = request.form.get('skills', '')
        abilities = request.form.get('abilities', '')
        
        # Update stats JSON
        stats_json = json.dumps({
            "HP": hp,
            "Attack": atk,
            "Defense": defense,
            "Special Attack": spa,
            "Special Defense": spd,
            "Speed": spe
        })
        
        c.execute("""
            UPDATE pokemon 
            SET HP=?, Atk=?, Def=?, SpA=?, SpD=?, Spe=?, 
                capabilities=?, skills=?, abilities=?, stats=?
            WHERE name=?
        """, (hp, atk, defense, spa, spd, spe, 
              capabilities, skills, abilities, stats_json, name))
        conn.commit()
        conn.close()
        
        flash(f"Pokémon '{name}' updated successfully!", "success")
        return redirect(url_for('pokemon'))
    
    # GET: Show edit form
    c.execute("SELECT * FROM pokemon WHERE name = ?", (name,))
    pokemon = c.fetchone()
    conn.close()
    
    if not pokemon:
        flash("Pokémon not found", "error")
        return redirect(url_for('pokemon'))
    
    return render_template('edit_pokemon.html', pokemon=pokemon)

@app.route('/insert_pokemon', methods=['GET', 'POST'])
def insert_pokemon():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        hp = int(request.form.get('hp', 0))
        atk = int(request.form.get('atk', 0))
        defense = int(request.form.get('defense', 0))
        spa = int(request.form.get('spa', 0))
        spd = int(request.form.get('spd', 0))
        spe = int(request.form.get('spe', 0))
        capabilities = request.form.get('capabilities', '')
        skills = request.form.get('skills', '')
        abilities = request.form.get('abilities', '')
        
        if not name:
            flash("Pokémon name is required", "error")
            return render_template('insert_pokemon.html')
        
        # Create stats JSON
        stats_json = json.dumps({
            "HP": hp,
            "Attack": atk,
            "Defense": defense,
            "Special Attack": spa,
            "Special Defense": spd,
            "Speed": spe
        })
        
        conn = get_db()
        c = conn.cursor()
        
        try:
            c.execute("""
                INSERT INTO pokemon 
                (name, HP, Atk, Def, SpA, SpD, Spe, 
                 capabilities, skills, abilities, stats)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, hp, atk, defense, spa, spd, spe, 
                  capabilities, skills, abilities, stats_json))
            conn.commit()
            flash(f"Pokémon '{name}' added successfully!", "success")
            return redirect(url_for('pokemon'))
        except sqlite3.IntegrityError:
            flash(f"Pokémon '{name}' already exists!", "error")
        finally:
            conn.close()
    
    return render_template('insert_pokemon.html')

@app.route('/import_pokemon_csv', methods=['POST'])
def import_pokemon_csv():
    if 'csv_file' not in request.files:
        flash('No file uploaded', 'error')
        return redirect(url_for('pokemon'))
    
    file = request.files['csv_file']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('pokemon'))
    
    if not file.filename.endswith('.csv'):
        flash('Please upload a CSV file', 'error')
        return redirect(url_for('pokemon'))
    
    try:
        # Read CSV
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_input = csv.reader(stream)
        
        conn = get_db()
        c = conn.cursor()
        
        imported = 0
        for row in csv_input:
            if len(row) < 6:  # Skip header or malformed rows
                continue
            
            name, hp, atk, defense, spa, spd, spe = row[0], row[1], row[2], row[3], row[4], row[5], row[6]
            
            # Skip header row if it contains column names
            if name.lower() == 'name':
                continue
            
            # Create stats JSON
            stats_json = json.dumps({
                "HP": int(hp),
                "Attack": int(atk),
                "Defense": int(defense),
                "Special Attack": int(spa),
                "Special Defense": int(spd),
                "Speed": int(spe)
            })
            
            # Insert or update
            c.execute("""
                INSERT OR REPLACE INTO pokemon 
                (name, HP, Atk, Def, SpA, SpD, Spe, stats)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, hp, atk, defense, spa, spd, spe, stats_json))
            imported += 1
        
        conn.commit()
        conn.close()
        
        flash(f"Successfully imported {imported} Pokémon!", "success")
        
    except Exception as e:
        flash(f"Error importing CSV: {str(e)}", "error")
    
    return redirect(url_for('pokemon'))

# ==================== POKÉMON GENERATOR ====================
@app.route('/pokemon_generator', methods=['GET', 'POST'])
def pokemon_generator():
    conn = get_db()
    c = conn.cursor()
    
    # Get all Pokémon names
    c.execute("SELECT name FROM pokemon ORDER BY name")
    pokemon_names = [row['name'] for row in c.fetchall()]
    
    # Get all natures
    natures = ["Adamant","Modest","Timid","Jolly","Bold","Calm","Impish","Lax","Relaxed",
              "Sassy","Gentle","Hasty","Naive","Naughty","Rash","Brave","Quiet","Mild",
              "Lonely","Hardy","Docile","Quirky","Serious","Bashful"]
    
    result = None
    if request.method == 'POST':
        poke_name = request.form.get('pokemon_name')
        level = int(request.form.get('level', 5))
        nature = request.form.get('nature', 'random')
        gender_select = request.form.get('gender', 'random')
        
        # Get base stats
        c.execute("SELECT stats FROM pokemon WHERE name = ?", (poke_name,))
        row = c.fetchone()
        
        if not row:
            flash("Pokémon not found!", "error")
            conn.close()
            return render_template('pokemon_generator.html', pokemon_names=pokemon_names, natures=natures)
        
        # Parse stats
        stats_str = row['stats']
        if stats_str:
            try:
                base_stats = json.loads(stats_str)
            except json.JSONDecodeError:
                base_stats = {}
        else:
            base_stats = {}
        
        # Determine nature
        if nature == 'random':
            chosen_nature = random.choice(natures)
        else:
            chosen_nature = nature
        
        # Determine gender
        if gender_select == 'random':
            gender = "♂" if random.random() < 0.5 else "♀"
        else:
            gender = gender_select
        
        # Shiny check (1/500)
        shiny = random.random() < 0.002
        
        # Calculate stats
        level_stats = {k: random.randint(1, 3) * level // 5 for k in base_stats}
        nature_bonus = {k: math.floor((base_stats.get(k, 0) + level_stats.get(k,0)) * 0.1) for k in base_stats}
        final_stats = {k: base_stats.get(k,0) + level_stats.get(k,0) + nature_bonus.get(k,0) for k in base_stats}
        
        # HP formula
        hp_base = base_stats.get('HP',0)
        hp_levelup = level_stats.get('HP',0)
        hp_bonus = nature_bonus.get('HP',0)
        hp_total = level + (hp_base + hp_levelup + hp_bonus) * 3
        
        # Build result
        shiny_prefix = "✨ " if shiny else ""
        result = {
            'name': poke_name,
            'level': level,
            'nature': chosen_nature,
            'gender': gender,
            'shiny': shiny,
            'shiny_prefix': shiny_prefix,
            'hp_total': hp_total,
            'base_stats': base_stats,
            'level_stats': level_stats,
            'nature_bonus': nature_bonus,
            'final_stats': final_stats
        }
    
    conn.close()
    return render_template('pokemon_generator.html', pokemon_names=pokemon_names, natures=natures, result=result)

@app.route('/generate_random_pokemon')
def generate_random_pokemon():
    conn = get_db()
    c = conn.cursor()
    
    # Get random Pokémon
    c.execute("SELECT name FROM pokemon ORDER BY RANDOM() LIMIT 1")
    pokemon = c.fetchone()
    
    if not pokemon:
        conn.close()
        return redirect(url_for('pokemon_generator'))
    
    conn.close()
    return redirect(url_for('pokemon_generator') + f"?pokemon={pokemon['name']}")

# ==================== TRAINER SHEETS ====================
@app.route('/trainer_sheets', methods=['GET', 'POST'])
def trainer_sheets():
    conn = get_db()
    c = conn.cursor()
    
    # Create tables if they don't exist
    c.execute('''CREATE TABLE IF NOT EXISTS trainers
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT NOT NULL,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS trainer_inventory
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  trainer_id INTEGER,
                  item_name TEXT,
                  quantity INTEGER DEFAULT 1,
                  FOREIGN KEY (trainer_id) REFERENCES trainers (id))''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS trainer_pokemon
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  trainer_id INTEGER,
                  pokemon_name TEXT,
                  nickname TEXT,
                  level INTEGER DEFAULT 5,
                  nature TEXT,
                  gender TEXT,
                  is_shiny BOOLEAN DEFAULT 0,
                  is_active BOOLEAN DEFAULT 1,
                  FOREIGN KEY (trainer_id) REFERENCES trainers (id))''')
    
    conn.commit()
    
    # Get all trainers
    c.execute("SELECT * FROM trainers ORDER BY created_at DESC")
    trainers = c.fetchall()
    
    selected_trainer = None
    inventory = []
    active_pokemon = []
    pc_pokemon = []
    
    # Handle GET request (select trainer) - also check POST for trainer_id
    trainer_id = request.args.get('trainer_id') or (request.form.get('trainer_id') if request.method == 'POST' else None)
    if trainer_id:
        c.execute("SELECT * FROM trainers WHERE id = ?", (trainer_id,))
        selected_trainer = c.fetchone()
    
    
    # Handle POST requests
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'create_trainer':
            trainer_name = request.form.get('trainer_name', '').strip()
            if trainer_name:
                c.execute("INSERT INTO trainers (name) VALUES (?)", (trainer_name,))
                conn.commit()
                trainer_id = c.lastrowid
                flash(f"Trainer '{trainer_name}' created!", "success")
                return redirect(url_for('trainer_sheets') + f"?trainer_id={trainer_id}")
        
        elif action == 'add_item' and selected_trainer:
            item_name = request.form.get('item_name', '').strip()
            quantity = int(request.form.get('quantity', 1))
            
            if item_name:
                # Check if item already exists
                c.execute("SELECT * FROM trainer_inventory WHERE trainer_id = ? AND item_name = ?", 
                         (selected_trainer['id'], item_name))
                existing = c.fetchone()
                
                if existing:
                    c.execute("UPDATE trainer_inventory SET quantity = quantity + ? WHERE id = ?", 
                             (quantity, existing['id']))
                else:
                    c.execute("INSERT INTO trainer_inventory (trainer_id, item_name, quantity) VALUES (?, ?, ?)",
                             (selected_trainer['id'], item_name, quantity))
                conn.commit()
                flash(f"Added {quantity}x {item_name} to inventory!", "success")
                return redirect(url_for('trainer_sheets') + f"?trainer_id={selected_trainer['id']}")
        
        elif action == 'add_pokemon' and selected_trainer:
            pokemon_name = request.form.get('pokemon_name', '').strip()
            nickname = request.form.get('nickname', '').strip()
            level = int(request.form.get('level', 5))
            nature = request.form.get('nature', 'Hardy')
            gender = request.form.get('gender', '♂')
            is_shiny = request.form.get('is_shiny') == 'yes'
            is_active = request.form.get('is_active') == 'active'
            
            if pokemon_name:
                c.execute("""INSERT INTO trainer_pokemon 
                          (trainer_id, pokemon_name, nickname, level, nature, gender, is_shiny, is_active)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                         (selected_trainer['id'], pokemon_name, nickname, level, nature, gender, is_shiny, is_active))
                conn.commit()
                flash(f"Added {pokemon_name} to trainer!", "success")
                return redirect(url_for('trainer_sheets') + f"?trainer_id={selected_trainer['id']}")
        
        elif action == 'move_to_pc' and selected_trainer:
            pokemon_id = request.form.get('pokemon_id')
            if pokemon_id:
                c.execute("UPDATE trainer_pokemon SET is_active = 0 WHERE id = ?", (pokemon_id,))
                conn.commit()
                flash("Pokémon moved to PC!", "success")
                return redirect(url_for('trainer_sheets') + f"?trainer_id={selected_trainer['id']}")
        
        elif action == 'move_to_party' and selected_trainer:
            pokemon_id = request.form.get('pokemon_id')
            if pokemon_id:
                # Check if party is full (max 6)
                c.execute("SELECT COUNT(*) FROM trainer_pokemon WHERE trainer_id = ? AND is_active = 1", 
                         (selected_trainer['id'],))
                count = c.fetchone()[0]
                
                if count < 6:
                    c.execute("UPDATE trainer_pokemon SET is_active = 1 WHERE id = ?", (pokemon_id,))
                    conn.commit()
                    flash("Pokémon moved to party!", "success")
                else:
                    flash("Party is full (max 6 Pokémon)!", "error")
                return redirect(url_for('trainer_sheets') + f"?trainer_id={selected_trainer['id']}")
    
    # Get trainer data if a trainer is selected
    if selected_trainer:
        # Get inventory
        c.execute("SELECT * FROM trainer_inventory WHERE trainer_id = ? ORDER BY item_name", (selected_trainer['id'],))
        inventory = c.fetchall()
        
        # Get Pokémon
        c.execute("SELECT * FROM trainer_pokemon WHERE trainer_id = ? ORDER BY is_active DESC, pokemon_name", (selected_trainer['id'],))
        all_pokemon = c.fetchall()
        
        # Separate active and PC
        for pkmn in all_pokemon:
            if pkmn['is_active']:
                active_pokemon.append(pkmn)
            else:
                pc_pokemon.append(pkmn)
    
    conn.close()
    
    # Get Pokémon names for dropdown
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT name FROM pokemon ORDER BY name")
    pokemon_names = [row['name'] for row in c.fetchall()]
    conn.close()
    
    natures = ["Adamant","Modest","Timid","Jolly","Bold","Calm","Impish","Lax","Relaxed",
              "Sassy","Gentle","Hasty","Naive","Naughty","Rash","Brave","Quiet","Mild",
              "Lonely","Hardy","Docile","Quirky","Serious","Bashful"]
    
    return render_template('trainer_sheets.html', 
                          trainers=trainers,
                          selected_trainer=selected_trainer,
                          inventory=inventory,
                          active_pokemon=active_pokemon,
                          pc_pokemon=pc_pokemon,
                          pokemon_names=pokemon_names,
                          natures=natures)

@app.route('/delete_trainer/<int:trainer_id>')
def delete_trainer(trainer_id):
    conn = get_db()
    c = conn.cursor()
    
    # Delete trainer and all related data
    c.execute("DELETE FROM trainer_inventory WHERE trainer_id = ?", (trainer_id,))
    c.execute("DELETE FROM trainer_pokemon WHERE trainer_id = ?", (trainer_id,))
    c.execute("DELETE FROM trainers WHERE id = ?", (trainer_id,))
    
    conn.commit()
    conn.close()
    
    flash("Trainer deleted!", "success")
    return redirect(url_for('trainer_sheets'))

@app.route('/delete_pokemon/<int:pokemon_id>')
def delete_pokemon(pokemon_id):
    conn = get_db()
    c = conn.cursor()
    
    # Get trainer ID for redirect
    c.execute("SELECT trainer_id FROM trainer_pokemon WHERE id = ?", (pokemon_id,))
    result = c.fetchone()
    
    if result:
        trainer_id = result['trainer_id']
        c.execute("DELETE FROM trainer_pokemon WHERE id = ?", (pokemon_id,))
        conn.commit()
        flash("Pokémon deleted!", "success")
        conn.close()
        return redirect(url_for('trainer_sheets') + f"?trainer_id={trainer_id}")
    
    conn.close()
    return redirect(url_for('trainer_sheets'))

@app.route('/update_inventory/<int:item_id>', methods=['POST'])
def update_inventory(item_id):
    new_quantity = int(request.form.get('quantity', 1))
    
    conn = get_db()
    c = conn.cursor()
    
    # Get trainer ID for redirect
    c.execute("SELECT trainer_id FROM trainer_inventory WHERE id = ?", (item_id,))
    result = c.fetchone()
    
    if result:
        trainer_id = result['trainer_id']
        
        if new_quantity <= 0:
            c.execute("DELETE FROM trainer_inventory WHERE id = ?", (item_id,))
        else:
            c.execute("UPDATE trainer_inventory SET quantity = ? WHERE id = ?", (new_quantity, item_id))
        
        conn.commit()
        flash("Inventory updated!", "success")
        conn.close()
        return redirect(url_for('trainer_sheets') + f"?trainer_id={trainer_id}")
    
    conn.close()
    return redirect(url_for('trainer_sheets'))  
  
@app.route('/insert_move', methods=['GET', 'POST'])
def insert_move():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        ac = request.form.get('ac', '').strip()
        damage = request.form.get('damage', '').strip()
        effect = request.form.get('effect', '').strip()
        
        if not name:
            flash("Move name is required", "error")
            return render_template('insert_move.html')
        
        # Convert empty AC to None
        ac_value = int(ac) if ac and ac.isdigit() else None
        
        conn = get_db()
        c = conn.cursor()
        
        try:
            c.execute("INSERT INTO moves (name, ac, damage, effect) VALUES (?, ?, ?, ?)",
                     (name, ac_value, damage, effect))
            conn.commit()
            flash(f"Move '{name}' added successfully!", "success")
            return redirect(url_for('moves'))
        except sqlite3.IntegrityError:
            flash(f"Move '{name}' already exists!", "error")
        except Exception as e:
            flash(f"Error adding move: {str(e)}", "error")
        finally:
            conn.close()
    
    return render_template('insert_move.html')


    # Add this route for saving encounters
@app.route('/save_encounter', methods=['POST'])
def save_encounter():
    conn = get_db()
    c = conn.cursor()
    
    # Create table for saved encounters if it doesn't exist
    c.execute('''CREATE TABLE IF NOT EXISTS saved_encounters
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  encounter_text TEXT,
                  saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    encounter_text = request.form.get('encounter_text')
    
    if encounter_text:
        c.execute("INSERT INTO saved_encounters (encounter_text) VALUES (?)", (encounter_text,))
        conn.commit()
        flash("Encounter saved successfully!", "success")
    
    conn.close()
    return redirect(url_for('encounters'))

@app.route('/delete_saved_encounter/<int:encounter_id>')
def delete_saved_encounter(encounter_id):
    conn = get_db()
    c = conn.cursor()
    
    c.execute("DELETE FROM saved_encounters WHERE id = ?", (encounter_id,))
    conn.commit()
    
    flash("Saved encounter deleted!", "success")
    conn.close()
    return redirect(url_for('view_saved_encounters'))

@app.route('/saved_encounters')
def view_saved_encounters():
    conn = get_db()
    c = conn.cursor()
    
    # Create table if it doesn't exist
    c.execute('''CREATE TABLE IF NOT EXISTS saved_encounters
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  encounter_text TEXT,
                  saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute("SELECT * FROM saved_encounters ORDER BY saved_at DESC")
    saved_encounters = c.fetchall()
    
    conn.close()
    return render_template('saved_encounters.html', saved_encounters=saved_encounters)
    

if __name__ == '__main__':
    app.run(debug=True)