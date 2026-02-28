#!/usr/bin/env python3
"""
Generate league YAML files from ESPN's teams API.
Converts ESPN hex colors to saturated RGB for LED punch.
"""

import httpx
import yaml
import colorsys
import sys
from pathlib import Path

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports"

LEAGUES = {
    # Pro leagues
    "nfl": {"sport": "football", "slug": "nfl", "name": "NFL"},
    "nba": {"sport": "basketball", "slug": "nba", "name": "NBA"},
    "mlb": {"sport": "baseball", "slug": "mlb", "name": "MLB"},
    "nhl": {"sport": "hockey", "slug": "nhl", "name": "NHL"},
    "mls": {"sport": "soccer", "slug": "usa.1", "name": "MLS"},
    "wnba": {"sport": "basketball", "slug": "wnba", "name": "WNBA"},
    # College
    "cfb": {"sport": "football", "slug": "college-football", "name": "College Football (FBS)"},
    "mcbb": {"sport": "basketball", "slug": "mens-college-basketball", "name": "Men's College Basketball"},
    "wcbb": {"sport": "basketball", "slug": "womens-college-basketball", "name": "Women's College Basketball"},
    # European soccer
    "epl": {"sport": "soccer", "slug": "eng.1", "name": "English Premier League"},
    "laliga": {"sport": "soccer", "slug": "esp.1", "name": "La Liga"},
    "bundesliga": {"sport": "soccer", "slug": "ger.1", "name": "Bundesliga"},
    "seriea": {"sport": "soccer", "slug": "ita.1", "name": "Serie A"},
    "ligue1": {"sport": "soccer", "slug": "fra.1", "name": "Ligue 1"},
    "ucl": {"sport": "soccer", "slug": "uefa.champions", "name": "UEFA Champions League"},
    "ligamx": {"sport": "soccer", "slug": "mex.1", "name": "Liga MX"},
}


def hex_to_rgb(hex_color: str) -> list[int]:
    """Convert hex color string to [R, G, B]."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        return [128, 128, 128]
    return [int(hex_color[i:i+2], 16) for i in (0, 2, 4)]


def saturate_for_leds(rgb: list[int]) -> list[int]:
    """
    Calibrated LED color boost. Derived from comparing ESPN hex values against
    hand-tuned NFL colors tested on actual LED strips.

    Key findings from calibration:
    - ESPN dark primaries (V < 0.3) need to become their pure hue at full brightness
    - Already-bright, saturated colors need minimal or no adjustment
    - Brightness floor of ~0.6 ensures visibility on strips
    - Saturation pushed toward 1.0 for LED punch
    - Desaturated metallics (silvers, grays) kept as-is — they read well on LEDs
    """
    r, g, b = [c / 255.0 for c in rgb]
    h, s, v = colorsys.rgb_to_hsv(r, g, b)

    # Skip near-black or true grays (metallics/silvers) — they read fine on LEDs
    if v < 0.05:
        return rgb
    if s < 0.15:
        # Metallic/gray: just ensure brightness
        v = max(v, 0.55)
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        return [int(r * 255), int(g * 255), int(b * 255)]

    # Dark saturated colors (ESPN navys, forest greens): crank to pure hue
    if v < 0.35 and s > 0.5:
        s = 1.0
        v = max(v * 2.5, 0.65)  # Big brightness boost
    else:
        # Normal colors: moderate push toward full saturation + brightness floor
        s = min(1.0, s * 1.15)
        v = max(v, 0.6)

    v = min(1.0, v)
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return [int(r * 255), int(g * 255), int(b * 255)]


def is_too_dark(rgb: list[int]) -> bool:
    """Check if a color is too dark to be visible on LEDs."""
    return all(c < 30 for c in rgb)


def fetch_teams(sport: str, slug: str) -> list[dict]:
    """Fetch all teams for a league from ESPN API."""
    url = f"{ESPN_BASE}/{sport}/{slug}/teams?limit=500"
    print(f"  Fetching {url}")
    resp = httpx.get(url, timeout=15.0)
    resp.raise_for_status()
    data = resp.json()

    teams = []
    for entry in data.get("sports", [{}])[0].get("leagues", [{}])[0].get("teams", []):
        team = entry.get("team", {})
        if not team.get("isActive", True):
            continue

        abbr = team.get("abbreviation", "")
        if not abbr:
            continue

        color1_hex = team.get("color", "808080")
        color2_hex = team.get("alternateColor", "404040")

        color1 = saturate_for_leds(hex_to_rgb(color1_hex))
        color2 = saturate_for_leds(hex_to_rgb(color2_hex))

        # If alternate is too dark (common: black alternate), make it a lighter shade of primary
        if is_too_dark(color2):
            r, g, b = [c / 255.0 for c in color1]
            h, s, v = colorsys.rgb_to_hsv(r, g, b)
            # Shift hue slightly, reduce saturation, keep bright
            s2 = max(0.3, s * 0.6)
            v2 = min(1.0, v * 1.2)
            r2, g2, b2 = colorsys.hsv_to_rgb(h, s2, v2)
            color2 = [int(r2 * 255), int(g2 * 255), int(b2 * 255)]

        teams.append({
            "abbr": abbr,
            "name": team.get("displayName", abbr),
            "display": team.get("shortDisplayName", team.get("name", abbr)),
            "colors": [color1, color2],
        })

    return teams


def generate_yaml(league_id: str, league_info: dict, teams: list[dict]) -> str:
    """Generate YAML content for a league file."""
    lines = [
        f"# {league_info['name']} Team Colors for Game Lights",
        f"# Auto-generated from ESPN API — {len(teams)} teams",
        f"# Colors are [R, G, B] — saturated for LED punch",
        "",
        f"name: {league_info['name']}",
        f"sport: {league_info['sport']}",
    ]

    # For leagues where the ESPN slug differs from our league ID
    if league_info["slug"] != league_id:
        lines.append(f"espn_league: {league_info['slug']}")

    lines.append("")
    lines.append("teams:")

    for team in sorted(teams, key=lambda t: t["abbr"]):
        lines.append(f"  {team['abbr']}:")
        lines.append(f"    name: {team['name']}")
        lines.append(f"    display: {team['display']}")
        c1, c2 = team["colors"]
        lines.append(f"    colors: [{c1}, {c2}]")
        lines.append("")

    return "\n".join(lines)


def main():
    output_dir = Path(__file__).parent.parent / "config" / "leagues"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Allow filtering by league ID(s) from command line
    targets = sys.argv[1:] if len(sys.argv) > 1 else list(LEAGUES.keys())

    total_teams = 0
    for league_id in targets:
        if league_id not in LEAGUES:
            print(f"Unknown league: {league_id}")
            continue

        info = LEAGUES[league_id]
        print(f"\n{'='*60}")
        print(f"Generating {info['name']} ({league_id})")
        print(f"{'='*60}")

        try:
            teams = fetch_teams(info["sport"], info["slug"])
            print(f"  Found {len(teams)} teams")

            yaml_content = generate_yaml(league_id, info, teams)
            out_path = output_dir / f"{league_id}.yaml"
            out_path.write_text(yaml_content)
            print(f"  Wrote {out_path}")
            total_teams += len(teams)

        except Exception as e:
            print(f"  ERROR: {e}")

    print(f"\n{'='*60}")
    print(f"Done! {len(targets)} leagues, {total_teams} teams total")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
