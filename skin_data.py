import requests
from bs4 import BeautifulSoup
import logging
from patch_data import get_champions_list
import re
from datetime import datetime

logging.basicConfig(level=logging.DEBUG)

def parse_date(date_str):
    try:
        if not date_str or not isinstance(date_str, str):
            return "Unknown"

        if date_str.lower() == 'unknown':
            return "Unknown"

        if all(c in "✔⭐⭘‒" for c in date_str):
            return "Unknown"

        year_match = re.search(r'\((\d{4})\)', date_str)
        if year_match:
            year = year_match.group(1)
            return f"Released in {year}"

        wiki_date_match = re.match(r'(\d{1,2})-([A-Za-z]{3})-(\d{4})', date_str)
        if wiki_date_match:
            day, month, year = wiki_date_match.groups()
            day = day.zfill(2)
            return f"{day}-{month}-{year}"

        if re.match(r'^(Prestige|Worlds)\s+', date_str):
            return f"Special Release: {date_str}"

        date_str = re.sub(r'\(.*?\)', '', date_str).strip()

        formats = [
            '%B %d, %Y',
            '%B %d,%Y',
            '%b %d, %Y',
            '%b %d,%Y',
            '%Y-%m-%d',
            '%B %-d, %Y',
            '%B %#d, %Y',
            '%d-%b-%Y',
        ]

        for fmt in formats:
            try:
                parsed_date = datetime.strptime(date_str, fmt)
                return parsed_date.strftime('%d-%b-%Y')
            except ValueError:
                continue

        return f"Non-standard: {date_str}"
    except Exception as e:
        logging.error(f"Error parsing date {date_str}: {e}")
        return "Unknown"

_skins_cache = None
_cache_timestamp = None

def get_all_skins_data():
    global _skins_cache, _cache_timestamp

    special_cases = {
        "Captain Fortune": "Miss Fortune",
        "Gun Goddess Miss Fortune": "Miss Fortune",
        "Pajama Guardian": "Various",
        "Little Demon": "Tristana",
        "Hextech": "Various",
        "Emumu": "Amumu",
        "Surprise Party": "Fiddlesticks",
        "Definitely Not": "Blitzcrank",
        "Traditional": "Various",
        "Championship": "Various",
        "Victorious": "Various",
        "Conqueror": "Various"
    }

    current_time = datetime.now()
    if _skins_cache is not None and _cache_timestamp is not None:
        if (current_time - _cache_timestamp).total_seconds() <= 3600:
            logging.debug("Using cached skins data")
            return _skins_cache

    try:
        champions = get_champions_list()
        champion_skins = {champion: [] for champion in champions}

        url = "https://wiki.leagueoflegends.com/en-us/List_of_champion_skins"
        logging.debug(f"Fetching all skins data from: {url}")

        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            logging.error(f"Failed to fetch skins data, status code: {response.status_code}")
            return {}

        soup = BeautifulSoup(response.content, 'html.parser')
        logging.debug("Successfully fetched HTML content for all skins")

        table = soup.find('table', {'class': ['sortable', 'article-table', 'nopadding']})
        if not table:
            logging.error("Could not find the skins table")
            return {}

        rows = table.find_all('tr')

        header_row = rows[0]
        header_cells = header_row.find_all(['th'])

        name_idx = None
        release_idx = None
        avail_idx = None

        for idx, cell in enumerate(header_cells):
            img_element = cell.find('img')
            if img_element and 'src' in img_element.attrs:
                img_src = img_element['src']
                logging.debug(f"Found image in header cell {idx}: {img_src}")

                if 'Release.png' in img_src:
                    release_idx = idx
                    logging.debug(f"Found Release column at index {idx}")

                elif 'Availability.png' in img_src:
                    avail_idx = idx
                    logging.debug(f"Found Availability column at index {idx}")

            cell_text = cell.get_text(strip=True).lower()
            logging.debug(f"Header cell {idx}: '{cell_text}'")
            if 'skin' in cell_text or 'name' in cell_text:
                name_idx = idx
            elif 'release' in cell_text and release_idx is None:
                release_idx = idx
            elif 'availab' in cell_text and avail_idx is None:
                avail_idx = idx

        if name_idx is None:
            name_idx = 1
        if release_idx is None:
            release_idx = 2
        if avail_idx is None and release_idx == 2:
            avail_idx = 3

        logging.debug(f"Using column {name_idx} for skin names and column {release_idx} for release dates")

        for row in rows[1:]:
            cells = row.find_all(['td', 'th'])
            if len(cells) <= max(name_idx, release_idx):
                continue

            skin_name = cells[name_idx].get_text(strip=True)
            if not skin_name or skin_name.lower() in ['skin', 'name']:
                continue

            release_date = "Unknown"
            if release_idx < len(cells):
                release_cell = cells[release_idx]

                date_links = release_cell.find_all('a')
                for link in date_links:
                    link_text = link.get_text(strip=True)
                    if re.match(r'\d{1,2}-[A-Za-z]{3}-\d{4}', link_text):
                        release_date = link_text
                        logging.debug(f"Found linked release date '{link_text}' for skin {skin_name}")
                        break

                if release_date == "Unknown":
                    date_text = release_cell.get_text(strip=True)
                    if date_text and date_text.lower() != 'unknown' and not all(c in "✔⭐⭘‒" for c in date_text):
                        date_text = re.sub(r'\([^)]*\)', '', date_text).strip()
                        if date_text:
                            release_date = date_text
                            logging.debug(f"Found text release date '{date_text}' for skin {skin_name}")

                if release_date == "Unknown":
                    elements_with_data = release_cell.select('[title], [data-sort-value]')
                    for element in elements_with_data:
                        if 'title' in element.attrs and re.search(r'\d{4}', element['title']):
                            release_date = element['title']
                            logging.debug(f"Found date in title attribute: '{release_date}' for skin {skin_name}")
                            break
                        elif 'data-sort-value' in element.attrs and re.search(r'\d{4}', element['data-sort-value']):
                            release_date = element['data-sort-value']
                            logging.debug(f"Found date in data-sort-value: '{release_date}' for skin {skin_name}")
                            break

                logging.debug(f"Final release date '{release_date}' for skin {skin_name}")

                champion_cell_text = ""
                if len(cells) > 0:
                    champion_cell_text = cells[0].get_text(strip=True)
                    logging.debug(f"Champion cell contains: '{champion_cell_text}' for skin {skin_name}")

                skin_champion = None

                if len(cells) > 0:
                    champion_cell = cells[0].get_text(strip=True)
                    if champion_cell in champions:
                        skin_champion = champion_cell

                champion_nicknames = {
                    "Emumu": "Amumu",
                    "MF": "Miss Fortune",
                    "TF": "Twisted Fate",
                    "ASol": "Aurelion Sol",
                    "Cass": "Cassiopeia",
                    "Mundo": "Dr. Mundo",
                    "Fiddle": "Fiddlesticks",
                    "GP": "Gangplank",
                    "J4": "Jarvan IV",
                    "Kai": "Kai'Sa",
                    "Kass": "Kassadin",
                    "Kat": "Katarina",
                    "Malph": "Malphite",
                    "Yi": "Master Yi",
                    "Morde": "Mordekaiser",
                    "Nunu": "Nunu & Willump",
                    "Raka": "Soraka",
                    "Tahm": "Tahm Kench",
                    "Vlad": "Vladimir",
                    "Xin": "Xin Zhao"
                }

                if not skin_champion:
                    for champion in sorted(champions, key=len, reverse=True):
                        if champion in skin_name or f"{champion}'s" in skin_name:
                            skin_champion = champion
                            break

                    partial_name_mappings = {
                        "urf": "Warwick",
                        "urfwick": "Warwick",
                        "alien": "Heimerdinger",
                        "definitely not": "Blitzcrank",
                        "festive": "Maokai",
                        "beemo": "Teemo",
                        "pug'maw": "Kog'Maw",
                        "baron": "Nashor",
                        "poro": "Braum",
                        "arcade": "Various",
                        "project": "Various",
                        "cosmic": "Various",
                        "dark star": "Various",
                        "pool party": "Various",
                        "guardian": "Various"
                    }

                    if not skin_champion:
                        skin_lower = skin_name.lower()
                        for partial, champ in partial_name_mappings.items():
                            if partial in skin_lower:
                                if champ != "Various":
                                    skin_champion = champ
                                    logging.debug(f"Matched partial name '{partial}' to champion {skin_champion}")
                                    break

                    if not skin_champion:
                        skin_parts = skin_name.split()
                        for part in skin_parts:
                            if part in champion_nicknames:
                                skin_champion = champion_nicknames[part]
                                logging.debug(f"Matched nickname {part} to champion {skin_champion}")
                                break

                    if not skin_champion:
                        for special_skin, champ in special_cases.items():
                            if special_skin in skin_name:
                                if champ != "Various":
                                    skin_champion = champ
                                    logging.debug(f"Matched special case {special_skin} to champion {skin_champion}")
                                    break

                if skin_champion:
                    champion_skins[skin_champion].append({
                        'name': skin_name,
                        'release_date': release_date
                    })
                    logging.debug(f"Added skin {skin_name} (Released: {release_date}) to champion {skin_champion}")

        special_skin_champions = {
            "Hextech": ["Alistar", "Amumu", "Annie", "Cho'Gath", "Galio", "Janna", "Kog'Maw", "Malzahar", "Nocturne", "Poppy", "Rammus", "Renekton", "Sejuani", "Singed", "Sion", "Swain", "Tristana", "Ziggs", "Jarvan IV", "Ezreal"],
            "Championship": ["Ashe", "Kalista", "Kha'Zix", "LeBlanc", "Riven", "Shyvana", "Thresh", "Zed", "Zoe"],
            "Victorious": ["Aatrox", "Blitzcrank", "Elise", "Graves", "Janna", "Jarvan IV", "Lucian", "Maokai", "Morgana", "Orianna", "Sivir"],
            "Conqueror": ["Alistar", "Jax", "Karma", "Nautilus", "Varus"],
            "Traditional": ["Lee Sin", "Karma", "Sejuani", "Trundle"]
        }

        for champion in champions:
            if champion in champion_skins:
                for skin_name, champ in special_cases.items():
                    if skin_name in special_skin_champions and champion not in special_skin_champions[skin_name]:
                        continue

                    if champ == champion or (champ == "Various" and champion in ["Ezreal", "Lux", "Miss Fortune"]):
                        full_skin_name = f"{skin_name} {champion}" if skin_name in ["Hextech", "Championship", "Victorious", "Conqueror", "Traditional"] else skin_name

                        should_add = True
                        for existing_skin in champion_skins[champion]:
                            existing_name = existing_skin['name']
                            if (skin_name in existing_name and champion in existing_name):
                                should_add = False
                                logging.debug(f"Skipping {skin_name} for {champion} as {existing_name} already exists")
                                break
                            if existing_name == skin_name or existing_name == full_skin_name:
                                should_add = False
                                break

                        if should_add:
                            release_date = "Unknown"
                            for i in range(1, len(rows)):
                                row = rows[i]
                                cells = row.find_all(['td', 'th'])
                                if len(cells) <= max(name_idx, release_idx):
                                    continue

                                table_skin_name = cells[name_idx].get_text(strip=True)

                                if table_skin_name == full_skin_name or (skin_name in table_skin_name and champion in table_skin_name):
                                    if release_idx < len(cells):
                                        date_cell = cells[release_idx]
                                        date_text = date_cell.get_text(strip=True)
                                        if date_text and date_text != "Unknown" and not all(c in "✔⭐⭘‒" for c in date_text):
                                            release_date = date_text
                                            logging.debug(f"Found release date '{date_text}' for special skin {full_skin_name}")
                                            break

                            champion_skins[champion].append({
                                'name': full_skin_name,
                                'release_date': parse_date(release_date) if release_date != "Unknown" else "Unknown"
                            })
                            logging.debug(f"Added special case skin {full_skin_name} to champion {champion} with release date {release_date}")

        other_skins = []

        for i in range(1, len(rows)):
            row = rows[i]
            cells = row.find_all(['td', 'th'])
            if len(cells) <= max(name_idx, release_idx):
                continue

            skin_name = cells[name_idx].get_text(strip=True)
            if not skin_name:
                continue

            release_date = "Unknown"
            if release_idx < len(cells):
                release_cell = cells[release_idx]
                date_text = release_cell.get_text(strip=True)
                if date_text and not all(c in "✔⭐⭘‒" for c in date_text):
                    release_date = parse_date(date_text)

            found = False
            for champion, skins in champion_skins.items():
                if any(skin['name'] == skin_name for skin in skins):
                    found = True
                    break

            if not found:
                other_skins.append({
                    'name': skin_name,
                    'release_date': release_date
                })
                logging.debug(f"Added skin {skin_name} to 'Other' category")

        if other_skins:
            champion_skins["Other"] = other_skins

        champion_skins = {k: v for k, v in champion_skins.items() if v}

        for champion in champion_skins:
            try:
                def sort_key(x):
                    date = x['release_date']

                    if champion in CUSTOM_SKIN_MAPPINGS.values() and x['name'] in CUSTOM_SKIN_MAPPINGS.keys():
                        if date != "Unknown" and re.search(r'\d{1,2}-[A-Za-z]{3}-\d{4}', date):
                            match = re.search(r'(\d{1,2})-([A-Za-z]{3})-(\d{4})', date)
                            if match:
                                day, month, year = match.groups()
                                month_map = {
                                    'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
                                    'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
                                }
                                return datetime(int(year), month_map.get(month, 1), int(day))
                        return datetime(2023, 1, 1)

                    if date == "Unknown":
                        return datetime.min

                    if re.search(r'\d{1,2}-[A-Za-z]{3}-\d{4}', date):
                        match = re.search(r'(\d{1,2})-([A-Za-z]{3})-(\d{4})', date)
                        if match:
                            day, month, year = match.groups()
                            month_map = {
                                'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
                                'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
                            }
                            return datetime(int(year), month_map.get(month, 1), int(day))

                    year_match = re.search(r'\b(20\d\d|19\d\d)\b', date)
                    if year_match:
                        try:
                            year = int(year_match.group(1))

                            month_match = re.search(r'\b(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b', date, re.IGNORECASE)
                            month = 1
                            if month_match:
                                month_name = month_match.group(1).lower()
                                months = {
                                    'january': 1, 'jan': 1, 'february': 2, 'feb': 2, 'march': 3, 'mar': 3, 
                                    'april': 4, 'apr': 4, 'may': 5, 'june': 6, 'jun': 6, 'july': 7, 'jul': 7, 
                                    'august': 8, 'aug': 8, 'september': 9, 'sep': 9, 'october': 10, 'oct': 10, 
                                    'november': 11, 'nov': 11, 'december': 12, 'dec': 12
                                }
                                month = months.get(month_name, 1)

                            day = 1
                            day_match = re.search(r'\b(\d{1,2})(st|nd|rd|th)?\b', date)
                            if day_match:
                                day = int(day_match.group(1))

                            return datetime(year, month, day)
                        except (ValueError, OverflowError):
                            logging.warning(f"Couldn't create date object from: {date}")
                            return datetime.min

                    return datetime.min

                champion_skins[champion].sort(key=sort_key, reverse=True)
            except Exception as e:
                logging.error(f"Error sorting skins for {champion}: {e}")

        logging.debug(f"Successfully categorized skins for {len(champion_skins)} champions")

        _skins_cache = champion_skins
        _cache_timestamp = current_time

        return champion_skins

    except Exception as e:
        logging.error(f"Error fetching skin data: {e}")
        return {}

def get_champion_skins(champion_name):
    try:
        all_skins = get_all_skins_data()
        return all_skins.get(champion_name, [])
    except Exception as e:
        logging.error(f"Error getting skins for {champion_name}: {e}")
        return []

CUSTOM_SKIN_MAPPINGS = {
    "Beezcrank": "Blitzcrank",
    "King Beegar": "Veigar",
    "Bee'Koz": "Vel'Koz",
    "Kittalee": "Nidalee",
    "Bewitching Batnivia": "Anivia",
    "Zap'Maw": "Kog'Maw",
    "Heimerstinger": "Heimerdinger",
    "Orbeeanna": "Orianna",
    "Admiral Glasc": "Renata Glasc",
    "Space Groove Blitz & Crank": "Blitzcrank",
    "Bee'Maw": "Kog'Maw",
    "Beezahar": "Malzahar",
    "Yuubee": "Yuumi",
    "The Thousand-Pierced Bear": "Volibear",
    "Meowrick": "Yorick",
    "Birdio": "Galio",
    "Renektoy": "Renekton",
    "Meowkai": "Maokai",
    "Snowmerdinger": "Heimerdinger",
    "Nutcracko": "Shaco",
    "Brolaf": "Olaf",
    "Lollipoppy": "Poppy",
    "Giant Enemy Crabgot": "Urgot",
    "Mr. Mundoverse": "Dr. Mundo"
}

def find_potential_champion_matches(skin_name):
    try:
        if skin_name in CUSTOM_SKIN_MAPPINGS:
            return [(CUSTOM_SKIN_MAPPINGS[skin_name], 100)]

        champions = get_champions_list()
        matches = []

        skin_lower = skin_name.lower()

        common_prefixes = ["hextech ", "project: ", "arcade ", "pool party ", "battle ", "cosmic ", 
                         "dark star ", "blood moon ", "spirit blossom ", "project ", "elderwood ",
                         "snowdown ", "lunar wraith ", "championship ", "victorious ", "conqueror ",
                         "bee", "beez", "pug'", "meow", "snow", "nutcrack", "bro", "lolli"]

        clean_skin_name = skin_lower
        for prefix in common_prefixes:
            if clean_skin_name.startswith(prefix):
                clean_skin_name = clean_skin_name[len(prefix):]
                break

        nickname_map = {
            "cass": "cassiopeia",
            "ali": "alistar",
            "asol": "aurelion sol",
            "mf": "miss fortune",
            "tf": "twisted fate",
            "j4": "jarvan iv",
            "mundo": "dr. mundo",
            "ww": "warwick",
            "nunu": "nunu & willump",

            "beez": "blitzcrank",
            "bee": "vel'koz",
            "kitta": "nidalee",
            "batnivia": "anivia",
            "maw": "kog'maw",
            "stinger": "heimerdinger",
            "merdinger": "heimerdinger",
            "anna": "orianna",
            "glasc": "renata glasc",
            "yuubee": "yuumi",
            "bear": "volibear",
            "meowrick": "yorick",
            "birdio": "galio",
            "toy": "renekton",
            "meowkai": "maokai",
            "cracko": "shaco",
            "olaf": "olaf",
            "poppy": "poppy",
            "crabgot": "urgot",
            "mundoverse": "dr. mundo"
        }

        for champion in champions:
            champion_lower = champion.lower()
            score = 0

            if champion_lower in clean_skin_name:
                if re.search(r'\b' + re.escape(champion_lower) + r'\b', clean_skin_name):
                    score += 10
                else:
                    score += 5

            champion_words = champion_lower.split()
            for word in champion_words:
                if len(word) > 2 and word in clean_skin_name:
                    score += 3

            if champion_lower.replace("'", "").replace(" ", "") in clean_skin_name.replace(" ", ""):
                score += 2

            for nickname, champ in nickname_map.items():
                if nickname in skin_lower and champ == champion_lower:
                    score += 5

            if any(pattern in skin_lower for pattern in [f"{champion_lower.replace(' ', '')}", 
                                                      f"{champion_lower[:4]}"]):
                score += 3

            if score > 0:
                matches.append((champion, score))

        return sorted(matches, key=lambda x: x[1], reverse=True)
    except Exception as e:
        logging.error(f"Error finding champion matches for skin {skin_name}: {e}")
        return []