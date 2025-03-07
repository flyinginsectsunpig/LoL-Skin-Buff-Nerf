import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import logging

logging.basicConfig(level=logging.DEBUG)

def get_champions_list():
    try:
        url = "https://wiki.leagueoflegends.com/en-us/Category:LoL_patch_history"
        logging.debug(f"Fetching champions list from: {url}")

        response = requests.get(url, timeout=10)  
        if response.status_code != 200:
            logging.error(f"Failed to fetch champions list, status code: {response.status_code}")
            return ["Aatrox"]  

        soup = BeautifulSoup(response.content, 'html.parser')
        logging.debug(f"Successfully fetched HTML content, length: {len(response.content)}")

        champion_links = soup.select('.mw-category-group li a')
        logging.debug(f"Found {len(champion_links)} potential champion links")

        champions = set()  

        for link in champion_links:
            champion_name = link.text.split('/')[0].strip()
            if champion_name and not champion_name.startswith("Category:"):
                champions.add(champion_name)

        if not champions:
            logging.error("Failed to extract champions from the category page")
            return ["Alistar"]

        return sorted(champions)  
    except Exception as e:
        logging.error(f"Error fetching champions list: {e}")
        return ["Alistar"]

def is_bug_fix_only(changes):
    if not changes:
        return False

    for change in changes:
        change_lower = change.lower()

        if ':' in change and change.split(':')[0].strip().endswith(('Q', 'W', 'E', 'R', 'Passive')):
            continue

        if not any(keyword in change_lower for keyword in bug_fix_keywords):
            return False

    return True

def is_undocumented(changes):
    undocumented_keywords = [
        'undocumented', 'unlisted', 'not documented', 'not listed',
        'no patch notes', 'unreleased'
    ]
    if not changes:
        return False

    for change in changes:
        change_lower = change.lower()

        if ':' in change and change.split(':')[0].strip().endswith(('Q', 'W', 'E', 'R', 'Passive')):
            continue

        if any(keyword in change_lower for keyword in undocumented_keywords):
            return True

    return False

def is_ability_icon_hud(changes):
    hud_keywords = [
        'hud', 'interface', 'user interface', 'ui', 'icon', 'icons',
        'ability icon', 'visual update', 'visual effect', 'visual display',
        'ability art', 'portrait', 'minimap icon'
    ]

    if not changes:
        return False

    for change in changes:
        change_lower = change.lower()

        if ':' in change and change.split(':')[0].strip().endswith(('Q', 'W', 'E', 'R', 'Passive')):
            continue

        if any(keyword in change_lower for keyword in hud_keywords) and ('icon' in change_lower or 'hud' in change_lower or 'ui' in change_lower):
            return True

    return False

def is_tooltip_update(changes):
    tooltip_keywords = [
        'tooltip', 'description', 'text', 'wording', 'description text',
        'ability description', 'tooltip text', 'description updated',
        'tooltip updated', 'text updated', 'wording updated'
    ]

    if not changes:
        return False

    for change in changes:
        change_lower = change.lower()

        if ':' in change and change.split(':')[0].strip().endswith(('Q', 'W', 'E', 'R', 'Passive')):
            continue

        if not any(keyword in change_lower for keyword in tooltip_keywords) or not ('tooltip' in change_lower or 'text' in change_lower or 'description' in change_lower):
            return False

    return True

def is_recommended_items_update(changes):
    item_keywords = [
        'recommended', 'item', 'items', 'recommended items',
        'item build', 'recommended build', 'item recommendation',
        'item set', 'item loadout'
    ]

    if not changes:
        return False

    for change in changes:
        change_lower = change.lower()

        if ':' in change and change.split(':')[0].strip().endswith(('Q', 'W', 'E', 'R', 'Passive')):
            continue

        if any(keyword in change_lower for keyword in item_keywords) and ('recommend' in change_lower or 'item' in change_lower):
            return True

    return False

def is_splash_artwork_update(changes):
    splash_keywords = [
        'splash', 'artwork', 'splash art', 'splash artwork', 'art',
        'artwork updated', 'updated artwork', 'updated splash',
        'visual update', 'splash screen', 'portrait', 'champion portrait',
        'splash image', 'loading screen'
    ]

    if not changes:
        return False

    for change in changes:
        change_lower = change.lower()

        if ':' in change and change.split(':')[0].strip().endswith(('Q', 'W', 'E', 'R', 'Passive')):
            continue

        if not any(keyword in change_lower for keyword in splash_keywords) or not ('splash' in change_lower or 'art' in change_lower or 'portrait' in change_lower or 'loading screen' in change_lower):
            return False

    return True

def is_animation_update(changes):
    if not changes:
        return False

    for change in changes:
        change_lower = change.lower()

        if ':' in change and change.split(':')[0].strip().endswith(('Q', 'W', 'E', 'R', 'Passive')):
            continue

        if not any(keyword in change_lower for keyword in animation_keywords) or not ('animation' in change_lower or 'visual' in change_lower or 'effect' in change_lower or 'vfx' in change_lower or 'particle' in change_lower):
            return False

    return True

def is_model_texture_update(changes):
    if not changes:
        return False

    for change in changes:
        change_lower = change.lower()

        if ':' in change and change.split(':')[0].strip().endswith(('Q', 'W', 'E', 'R', 'Passive')):
            continue

        if not any(keyword in change_lower for keyword in model_texture_keywords) or not ('model' in change_lower or 'texture' in change_lower or 'visual' in change_lower):
            return False

    return True

def is_game_mode_related(version_text, changes):
    if any(keyword in version_text.lower() for keyword in game_mode_keywords):
        return True

    if changes:
        for change in changes:
            change_lower = change.lower()
            if not any(keyword in change_lower for keyword in game_mode_keywords):
                return False
        return True

    return False

def get_patch_data(champion_name, include_undocumented=True, exclude_art_sustainability=False, exclude_alpha_v1=True):
    try:
        url = f"https://wiki.leagueoflegends.com/en-us/{champion_name}/Patch_history"
        logging.debug(f"Fetching patch data from: {url}")

        # Get patch dates from wiki pages
        patch_dates = get_patch_dates()
        logging.debug(f"Loaded {len(patch_dates)} patch dates from wiki pages")

        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            logging.error(f"Failed to fetch patch data for {champion_name}, status code: {response.status_code}")
            return []

        soup = BeautifulSoup(response.content, 'html.parser')
        logging.debug(f"Successfully fetched HTML content for {champion_name}")

        patch_history = soup.find('div', {'class': 'mw-parser-output'})
        if not patch_history:
            logging.error("Could not find patch history section")
            return []

        patch_notes = []
        seen_changes = set()

        for dl_element in patch_history.find_all('dl'):
            dt_element = dl_element.find('dt')
            if not dt_element:
                continue

            version_text = dt_element.get_text().strip()
            version_link = dt_element.find('a')
            if not version_link:
                continue

            version = version_text

            if any(keyword in version.lower() for keyword in game_mode_keywords):
                logging.debug(f"Skipping game mode patch: {version}")
                continue

            if exclude_art_sustainability and "art & sustainability" in version.lower():
                logging.debug(f"Skipping Art & Sustainability patch: {version}")
                continue

            logging.debug(f"Processing version: {version}")

            changes = []
            next_element = dl_element.find_next_sibling()

            while next_element and next_element.name != 'dl':
                if next_element.name == 'ul':
                    for li in next_element.find_all('li'):
                        text = li.get_text().strip()

                        if not text or text in seen_changes:
                            continue

                        seen_changes.add(text)

                        if '<span class="inline-image' in text or '<span class="ability-icon' in text:
                            changes.append(text)
                            continue

                        if text.strip().startswith('<span class="template_sbc"><b>New Effect:</b></span>') or text.strip().startswith('New Effect:'):
                            changes.append(text)
                            continue

                        if ':' in text:
                            ability_parts = text.split(':', 1)
                            ability_name = ability_parts[0].strip()
                            ability_desc = ability_parts[1].strip()

                            if ability_name in ["Stats", "General"]:
                                changes.append(f"<strong>{ability_name}:</strong>")

                                detail_changes = text.split('.')[:-1]  
                                for detail in detail_changes:
                                    if ':' in detail:
                                        detail = detail.replace(f"{ability_name}:", "").strip()
                                    if detail:
                                        changes.append("• " + detail.strip() + ".")
                                continue

                            if "New Effect:" in ability_desc:
                                ability_desc = re.sub(r'^.*?(New Effect:)', r'\1', ability_desc)

                            ability_desc = ability_desc.replace("New Effect:", "\nNew Effect:")
                            ability_desc = ability_desc.replace("Now triggers", "\nNow triggers")

                            changes.append(f"{ability_name}: {ability_desc}")
                        else:
                            changes.append(text)

                next_element = next_element.find_next_sibling()

            if changes:
                # Try to get date from wiki patch dates first, then fall back to extract_date
                extracted_date = extract_date(version)
                
                # Try different version formats to match with patch_dates
                clean_version = version.split(' - ')[0].strip() if ' - ' in version else version
                wiki_date = None
                
                # Try exact match
                if clean_version in patch_dates:
                    wiki_date = patch_dates[clean_version]
                else:
                    # Try with or without 'v' prefix
                    alt_version = 'v' + clean_version if not clean_version.startswith('v') else clean_version[1:]
                    if alt_version in patch_dates:
                        wiki_date = patch_dates[alt_version]
                
                patch_notes.append({
                    'version': version,
                    'date': wiki_date if wiki_date else extracted_date,
                    'changes': changes
                })

        logging.debug(f"Initially extracted {len(patch_notes)} patches")

        filtered_patches = []
        for patch in patch_notes:
            if is_game_mode_related(patch['version'], patch['changes']):
                logging.debug(f"Filtering out {patch['version']} - Game mode related patch")
                continue

            numerical_changes = []
            has_numerical_value = False

            for change in patch['changes']:
                if (re.search(r'\d+\s*/\s*\d+', change) or  
                    re.search(r'(\d+).*from.*(\d+)', change) or  
                    re.search(r'(\d+).*to.*(\d+)', change) or  
                    re.search(r'(\d+)[%]', change) or  
                    re.search(r'(\d+\.?\d*)[\s]*[+-]', change) or  
                    (re.search(r'\b\d+\.?\d*\b', change) and  
                     any(keyword in change.lower() for keyword in ['damage', 'health', 'mana', 'cooldown', 'range', 'speed', 'armor', 'resist']))):
                    has_numerical_value = True
                    numerical_changes.append(change)
                elif not any(keyword in change.lower() 
                            for keyword in bug_fix_keywords + animation_keywords + model_texture_keywords):
                    numerical_changes.append(change)

            if has_numerical_value:  
                patch['changes'] = numerical_changes
                filtered_patches.append(patch)
                logging.debug(f"Including {patch['version']} - Contains numerical gameplay changes")
            else:
                logging.debug(f"Filtering out {patch['version']} - No numerical gameplay changes")

            if not include_undocumented:
                filtered_patches = [patch for patch in filtered_patches
                                  if not is_undocumented(patch['changes'])]

            if exclude_alpha_v1:
                month_names = ['january', 'february', 'march', 'april', 'may', 'june', 
                              'july', 'august', 'september', 'october', 'november', 'december',
                              'jan', 'feb', 'mar', 'apr', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']

                filtered_patches = [patch for patch in filtered_patches
                                  if not (
                                      'alpha' in patch['version'].lower() or  
                                      re.match(r'v?0\.\d+', patch['version'].lower()) or  
                                      re.match(r'v?1\.\d+', patch['version'].lower()) or  
                                      any(patch['version'].lower().strip().startswith(month) for month in month_names)  
                                  )]

            final_patches = []
            for patch in filtered_patches:
                has_stat_changes = False
                contains_only_cosmetic = True

                for change in patch['changes']:
                    change_lower = change.lower()

                    if (re.search(r'\d+\s*/\s*\d+', change) or 
                        re.search(r'(\d+).*from.*(\d+)', change) or
                        re.search(r'(\d+).*to.*(\d+)', change) or
                        ('increased' in change_lower) or 
                        ('decreased' in change_lower) or
                        ('reduced' in change_lower) or
                        ('added' in change_lower and not 'added to the game' in change_lower) or
                        ('bonus' in change_lower and re.search(r'\d+', change)) or
                        ('cooldown' in change_lower and re.search(r'\d+', change)) or
                        ('damage' in change_lower and re.search(r'\d+', change)) or
                        ('mana' in change_lower and re.search(r'\d+', change))):
                        has_stat_changes = True
                        contains_only_cosmetic = False
                        break

                if has_stat_changes:
                    final_patches.append(patch)
                    continue

                if (is_ability_icon_hud(patch['changes']) or
                    is_tooltip_update(patch['changes']) or
                    is_recommended_items_update(patch['changes']) or
                    is_splash_artwork_update(patch['changes'])):
                    logging.debug(f"Filtering out {patch['version']} - Contains only cosmetic or UI changes")
                    continue

                final_patches.append(patch)

        logging.debug(f"Final patch count after all filtering: {len(final_patches)}")

        def version_key(patch):
            version_str = patch['version'].lower().replace('v', '')
            if ' - ' in version_str:
                version_str = version_str.split(' - ')[0]

            try:
                parts = [int(part) for part in version_str.split('.')]
                while len(parts) < 3:
                    parts.append(0)
                return parts
            except (ValueError, AttributeError):
                return [0, 0, 0]

        return sorted(final_patches, key=version_key, reverse=True)

    except Exception as e:
        logging.error(f"Error processing patch data for {champion_name}: {e}")
        return []

def extract_date(version_text):
    try:
        date_match = re.search(r'\((.*?)\)|Released: (.*)', version_text)
        if date_match:
            date_str = date_match.group(1) or date_match.group(2)
            if date_str:
                return parse_date(date_str)
        return ""  # Return empty string for no match
    except Exception as e:
        logging.error(f"Error extracting date from {version_text}: {e}")
        return ""  # Return empty string on error

def parse_date(date_str):
    try:
        date_str = re.sub(r'\(.*?\)', '', date_str).strip()

        wiki_date_match = re.match(r'(\d{1,2})-([A-Za-z]{3})-(\d{4})', date_str)
        if wiki_date_match:
            day, month, year = wiki_date_match.groups()
            day = day.zfill(2)
            return f"{day}-{month}-{year}"

        formats = [
            '%B %d, %Y',  
            '%B %d,%Y',   
            '%b %d, %Y',  
            '%b %d,%Y',   
            '%B %-d, %Y', 
            '%B %#d, %Y', 
        ]

        for fmt in formats:
            try:
                parsed_date = datetime.strptime(date_str, fmt)
                return parsed_date.strftime('%d-%b-%Y')
            except ValueError:
                continue

        return date_str
    except Exception as e:
        logging.error(f"Error parsing date {date_str}: {e}")
        return date_str

bug_fix_keywords = [
    'bug', 'fix', 'fixed', 'fixes', 'bugfix', 'resolved an issue',
    'fixed a bug', 'fixed an issue', 'corrected', 'no longer',
    'resolved a bug', 'now correctly', 'now properly'
]

animation_keywords = [
    'animation', 'animations', 'animated', 'visual effect',
    'vfx', 'sfx', 'particle', 'particles', 'effect', 'effects',
    'visual update', 'animation update', 'new animation',
    'updated animation', 'visual polish', 'animation polish',
    'run animation', 'walk animation', 'attack animation'
]

model_texture_keywords = [
    'model', 'models', 'texture', 'textures',
    'new model', 'new texture', 'model update',
    'texture update', 'model and texture', 'models and textures',
    'visual update', 'visual upgrade', 'visual overhaul',
    'character model', 'model rework', 'texture rework'
]

game_mode_keywords = [
    'regular modes', 'featured game modes', 'game modes', 'featured modes',
    'aram', 'twisted treeline', 'all random all mid', 'featured game mode',
    'howling abyss', 'normal games', 'ranked games', 'game mode',
    'dominion', 'nexus blitz', 'teamfight tactics', 'featured mode',
    'wild rift', 'urf', 'one for all', 'ultimate spellbook',
    'ascension', 'poro king', 'doom bots', 'showdown', 'hexakill',
    'odyssey', 'star guardian', 'project', 'rgm', 'rgms'
]


def get_patch_dates():
    patch_date_map = {}
    urls = [
        "https://wiki.leagueoflegends.com/en-us/Patch/2025_Annual_Cycle",
        "https://wiki.leagueoflegends.com/en-us/Patch/Season_2024",
        "https://wiki.leagueoflegends.com/en-us/Patch/Season_2023",
        "https://wiki.leagueoflegends.com/en-us/Patch/Season_2022",
        "https://wiki.leagueoflegends.com/en-us/Patch/Season_2021",
        "https://wiki.leagueoflegends.com/en-us/Patch/Season_2020",
        "https://wiki.leagueoflegends.com/en-us/Patch/Season_2019",
        "https://wiki.leagueoflegends.com/en-us/Patch/Season_2018",
        "https://wiki.leagueoflegends.com/en-us/Patch/Season_2017",
        "https://wiki.leagueoflegends.com/en-us/Patch/Season_2016",
        "https://wiki.leagueoflegends.com/en-us/Patch/Season_2015",
        "https://wiki.leagueoflegends.com/en-us/Patch/Season_2014",
        "https://wiki.leagueoflegends.com/en-us/Patch/Season_Three"
    ]
    
    for url in urls:
        try:
            logging.debug(f"Fetching patch dates from: {url}")
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                logging.error(f"Failed to fetch patch dates, status code: {response.status_code}")
                continue
                
            soup = BeautifulSoup(response.content, 'html.parser')
            tables = soup.find_all('table', {'class': ['sortable', 'article-table']})
            
            for table in tables:
                rows = table.find_all('tr')
                for row in rows[1:]:  # Skip header row
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        patch_version = cells[0].get_text(strip=True)
                        patch_date = cells[1].get_text(strip=True)
                        
                        # Clean up version number
                        patch_version = patch_version.replace('V', 'v').replace('v ', 'v')
                        if patch_version.startswith('Version '):
                            patch_version = 'v' + patch_version[8:]
                        
                        # Store in mapping
                        if patch_version and patch_date:
                            patch_date_map[patch_version] = patch_date
                            logging.debug(f"Found date for patch {patch_version}: {patch_date}")
        except Exception as e:
            logging.error(f"Error fetching patch dates from {url}: {e}")
    
    return patch_date_map
