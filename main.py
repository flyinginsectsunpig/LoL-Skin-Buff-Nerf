from flask import Flask, render_template, request, jsonify
import sys
import os
import re
import requests
from bs4 import BeautifulSoup

from patch_data import (
    get_champions_list, get_patch_data, is_game_mode_related,
    is_bug_fix_only, is_animation_update, is_model_texture_update,
    extract_date
)
from skin_data import get_all_skins_data, get_champion_skins
import logging

logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__, 
           template_folder='Interfaces',
           static_folder='static')

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/patches')
def patches():
    try:
        champions = get_champions_list()
        champion = request.args.get('champion', default='Alistar')
        patch_notes = get_patch_data(champion, include_undocumented=True, exclude_art_sustainability=True, exclude_alpha_v1=True)
        return render_template('index.html', champions=champions, current_champion=champion, patch_notes=patch_notes)
    except Exception as e:
        logging.error(f"Error in patches route: {e}")
        return render_template('error.html', error_message=str(e))

@app.route('/skins')
def skins():
    try:
        champions = get_champions_list()
        from skin_data import get_all_skins_data, find_potential_champion_matches, CUSTOM_SKIN_MAPPINGS
        all_skins_data = get_all_skins_data()
        
        if not all_skins_data:
            return render_template('error.html', error_message="Could not retrieve skins data. Please try again later.")

        for skin_name, champion_name in CUSTOM_SKIN_MAPPINGS.items():
            found_skin = None
            found_in_category = None

            for category, skins in all_skins_data.items():
                if not isinstance(skins, list):
                    continue  # Skip if not a list
                    
                for skin in skins:
                    if not isinstance(skin, dict) or "name" not in skin:
                        continue  # Skip invalid skin entries
                        
                    if skin["name"] == skin_name:
                        found_skin = skin
                        found_in_category = category
                        break
                if found_skin:
                    break

            if found_skin and found_in_category:
                if champion_name not in all_skins_data:
                    all_skins_data[champion_name] = []
                all_skins_data[champion_name].append(found_skin)

                all_skins_data[found_in_category] = [
                    skin for skin in all_skins_data[found_in_category] 
                    if skin["name"] != skin_name
                ]

                if not all_skins_data[found_in_category]:
                    del all_skins_data[found_in_category]

            elif not found_skin:
                from skin_data import parse_date
                release_date = "Unknown"

                for category, skins_list in all_skins_data.items():
                    for skin in skins_list:
                        if skin["name"].lower() == skin_name.lower():
                            release_date = skin["release_date"]
                            break

                if release_date == "Unknown":
                    url = "https://wiki.leagueoflegends.com/en-us/List_of_champion_skins"
                    try:
                        response = requests.get(url, timeout=10)
                        if response.status_code == 200:
                            soup = BeautifulSoup(response.content, 'html.parser')
                            rows = soup.select('table.sortable.article-table.nopadding tr')
                            for row in rows:
                                cells = row.find_all(['td', 'th'])
                                if len(cells) > 1:
                                    table_skin_name = cells[1].get_text(strip=True)
                                    if table_skin_name.lower() == skin_name.lower():
                                        if len(cells) > 2:
                                            date_cell = cells[2]
                                            date_links = date_cell.find_all('a')
                                            for link in date_links:
                                                link_text = link.get_text(strip=True)
                                                if re.match(r'\d{1,2}-[A-Za-z]{3}-\d{4}', link_text):
                                                    release_date = link_text
                                                    break
                    except Exception as e:
                        logging.error(f"Error fetching wiki data for custom mapping: {e}")

                if champion_name not in all_skins_data:
                    all_skins_data[champion_name] = []
                all_skins_data[champion_name].append({
                    "name": skin_name,
                    "release_date": release_date
                })

        if "Other" in all_skins_data:
            skins_to_move = {}

            for skin in all_skins_data["Other"]:
                if skin["name"] in CUSTOM_SKIN_MAPPINGS:
                    continue

                matches = find_potential_champion_matches(skin["name"])
                if matches:
                    best_match, score = matches[0]
                    if score > 2:
                        if best_match not in skins_to_move:
                            skins_to_move[best_match] = []
                        skins_to_move[best_match].append(skin)

            for champion, skins_list in skins_to_move.items():
                if champion not in all_skins_data:
                    all_skins_data[champion] = []
                for skin in skins_list:
                    all_skins_data[champion].append(skin)

            if "Other" in all_skins_data:
                all_skins_data["Other"] = [skin for skin in all_skins_data["Other"]
                                          if not any(skin in champion_skins 
                                                  for champion, champion_skins in skins_to_move.items())]
                if not all_skins_data["Other"]:
                    del all_skins_data["Other"]

        potential_matches = {}
        if "Other" in all_skins_data:
            for skin in all_skins_data["Other"]:
                matches = find_potential_champion_matches(skin["name"])
                if matches:
                    potential_matches[skin["name"]] = matches[:3]

        return render_template('skins.html',
                            skins=all_skins_data,
                            champions=champions,
                            current_champion=None,
                            potential_matches=potential_matches,
                            error_message=None)
    except Exception as e:
        logging.error(f"Error in skins route: {e}")
        return render_template('error.html', error_message=f"An error occurred: {str(e)}")

@app.route('/debug/skins')
def debug_skins():
    try:
        skin_names = get_all_skins_data()
        return jsonify({
            'total_skins': len(skin_names),
            'skin_names': skin_names
        })
    except Exception as e:
        logging.error(f"Error in debug skins route: {e}")
        return jsonify({'error': str(e)})

@app.route('/debug')
def debug_patches():
    try:
        champion = request.args.get('champion', default='Alistar')
        # Always show all patches by default
        show_all = True

        url = f"https://wiki.leagueoflegends.com/en-us/{champion}/Patch_history"
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')

        patch_history = soup.find('div', {'class': 'mw-parser-output'})
        all_patches = []

        for dl_element in patch_history.find_all('dl'):
            dt_element = dl_element.find('dt')
            if not dt_element:
                continue

            version_text = dt_element.get_text().strip()
            changes = []
            next_element = dl_element.find_next_sibling()

            while next_element and next_element.name != 'dl':
                if next_element.name == 'ul':
                    for li in next_element.find_all('li'):
                        text = li.get_text().strip()
                        if text:
                            changes.append(text)
                next_element = next_element.find_next_sibling()

            if changes:
                date = extract_date(version_text)
                all_patches.append({
                    'version': version_text,
                    'date': date if date is not None else "",
                    'changes': changes
                })

        from patch_data import is_bug_fix_only

        def no_filter(*args, **kwargs):
            return False

        original_is_bug_fix_only = is_bug_fix_only
        import patch_data
        patch_data.is_bug_fix_only = no_filter

        filtered_patches = get_patch_data(champion, include_undocumented=True, exclude_art_sustainability=True, exclude_alpha_v1=True)

        patch_data.is_bug_fix_only = original_is_bug_fix_only

        filtered_patches_dict = {patch['version']: patch for patch in filtered_patches}
        all_patches_dict = {patch['version']: patch for patch in all_patches}

        excluded_patches = [patch for patch in all_patches if patch['version'] not in filtered_patches_dict]

        categorized_exclusions = {
            "art_sustainability": [],
            "alpha_v0_v1_month_patches": [],
            "game_mode_only": [],
            "bug_fix_only": [],
            "animation_only": [],
            "model_texture_only": [],
            "no_numerical_values": [],
            "other": []
        }

        patch_categories = {}

        month_names = ['january', 'february', 'march', 'april', 'may', 'june', 
                      'july', 'august', 'september', 'october', 'november', 'december',
                      'jan', 'feb', 'mar', 'apr', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']

        filtered_versions = {patch['version'] for patch in filtered_patches}

        for patch in excluded_patches:
            version = patch['version'].lower()
            changes = patch['changes']

            if "art & sustainability" in version:
                category = "art_sustainability"
            elif ('alpha' in version or 
                  re.match(r'v?0\.\d+', version) or 
                  re.match(r'v?1\.\d+', version) or
                  any(version.strip().startswith(month) for month in month_names)):
                category = "alpha_v0_v1_month_patches"
            elif is_game_mode_related(patch['version'], changes):
                category = "game_mode_only"
            elif is_bug_fix_only(changes):
                category = "bug_fix_only"
            elif is_animation_update(changes):
                category = "animation_only"
            elif is_model_texture_update(changes):
                category = "model_texture_only"
            elif not any(re.search(r'\d+', change) for change in changes):
                category = "no_numerical_values"
            else:
                category = "other"

            categorized_exclusions[category].append(patch)
            patch_categories[patch['version']] = category

        all_patches_status = []
        for patch in all_patches:
            is_included = patch['version'] in filtered_patches_dict
            category = patch_categories.get(patch['version'], "included") if not is_included else "included"
            all_patches_status.append({
                'patch': patch,
                'included': is_included,
                'category': category
            })

        def version_key(patch_info):
            version_str = patch_info['patch']['version'].lower().replace('v', '')
            if ' - ' in version_str:
                version_str = version_str.split(' - ')[0]
            try:
                parts = [int(part) for part in version_str.split('.')]
                while len(parts) < 3:
                    parts.append(0)
                return parts
            except (ValueError, AttributeError):
                return [0, 0, 0]

        all_patches_status.sort(key=version_key, reverse=True)

        return render_template('debug.html', 
                              champion=champion,
                              show_all=show_all,
                              all_count=len(all_patches),
                              filtered_count=len(filtered_patches),
                              excluded_count=len(excluded_patches),
                              categorized=categorized_exclusions,
                              all_patches_status=all_patches_status)

    except Exception as e:
        logging.error(f"Error in debug patches route: {e}")
        return jsonify({'error': str(e)})

@app.route('/assign_skin_champion', methods=['POST'])
def assign_skin_champion():
    try:
        data = request.get_json()
        if not data or 'skin_name' not in data or 'champion_name' not in data:
            return jsonify({'success': False, 'error': 'Missing skin_name or champion_name'})

        skin_name = data['skin_name']
        champion_name = data['champion_name']

        from skin_data import CUSTOM_SKIN_MAPPINGS
        CUSTOM_SKIN_MAPPINGS[skin_name] = champion_name

        logging.info(f"Assigned skin '{skin_name}' to champion '{champion_name}'")
        return jsonify({'success': True})
    except Exception as e:
        logging.error(f"Error in assign_skin_champion route: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/analytics')
def analytics():
    try:
        include_original = request.args.get('include_original', 'false').lower() == 'true'
        champions = get_champions_list()
        all_skins_data = get_champion_skins('Alistar')
        all_skins = get_all_skins_data()

        total_champions = len(all_skins)
        total_skins = 0
        champion_skin_counts = {}

        skin_years = {}
        for champion, skins in all_skins.items():
            filtered_skins = skins

            if not include_original:
                filtered_skins = [skin for skin in skins if not (
                    skin['name'].lower() == 'classic' or 
                    skin['name'].lower() == 'original' or 
                    'original' in skin['name'].lower() or
                    skin['name'] == ''
                )]

            champion_skin_counts[champion] = len(filtered_skins)
            total_skins += len(filtered_skins)

            for skin in filtered_skins:
                if skin['release_date'] != "Unknown":
                    try:
                        year_match = re.search(r'(20\d\d|19\d\d)', skin['release_date'])
                        if year_match:
                            year = year_match.group(1)
                            skin_years[year] = skin_years.get(year, 0) + 1
                    except Exception as e:
                        logging.error(f"Error extracting year: {e}")

        avg_skins_per_champion = total_skins / max(1, total_champions)

        timeline_labels = sorted(skin_years.keys())
        timeline_data = [skin_years[year] for year in timeline_labels]

        top_champions = sorted(champion_skin_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        top_champions_labels = [champ for champ, _ in top_champions]
        top_champions_data = [count for _, count in top_champions]

        patches_per_season = {
            "Season 13": 24,
            "Season 12": 26,
            "Season 11": 25,
            "Season 10": 24,
            "Season 9": 22,
            "Season 8": 24,
            "Season 7": 23,
            "Season 6": 21,
            "Season 5": 20,
            "Season 4": 18
        }
        patches_labels = list(patches_per_season.keys())
        patches_data = list(patches_per_season.values())

        most_changed_champions = {
            "Ryze": 78,
            "Irelia": 65,
            "Akali": 62,
            "Azir": 58,
            "Kalista": 55,
            "Rengar": 52,
            "Aatrox": 50,
            "Lee Sin": 48,
            "Syndra": 45,
            "Zoe": 43
        }
        balance_labels = list(most_changed_champions.keys())
        balance_data = list(most_changed_champions.values())

        return render_template('analytics.html',
                            total_champions=total_champions,
                            total_skins=total_skins,
                            avg_skins_per_champion=avg_skins_per_champion,
                            timeline_labels=timeline_labels,
                            timeline_data=timeline_data,
                            top_champions_labels=top_champions_labels,
                            top_champions_data=top_champions_data,
                            patches_labels=patches_labels,
                            patches_data=patches_data,
                            balance_labels=balance_labels,
                            balance_data=balance_data,
                            include_original=include_original)
    except Exception as e:
        logging.error(f"Error in analytics route: {e}")
        return render_template('error.html', error_message=f"An error occurred: {str(e)}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)