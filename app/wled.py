"""
WLED controller for dynamic game-day lighting.

Handles segment creation, color assignment, and the "battle line" effect.
"""

import asyncio
import httpx
from typing import Optional
from dataclasses import dataclass


# Effect IDs in WLED
EFFECT_CHASE = 28      # Original Chase
EFFECT_CHASE_2 = 37    # Chase 2 - better segment size control via intensity
EFFECT_SOLID = 0
EFFECT_SCANNER = 16    # Scanner - bounces back and forth
EFFECT_BLEND = 115     # "Blends" - not great for contested zone (makes mud)


@dataclass
class WLEDConfig:
    """Configuration for a WLED installation."""
    host: str
    roofline_start: int = 0
    roofline_end: int = 629
    min_team_pct: float = 0.05  # Minimum 5% dignity
    contested_zone_pixels: int = 6   # Jiggling divider bar
    dark_buffer_pixels: int = 4      # Dark space on each side of divider
    transition_ms: int = 500  # Smooth transitions
    chase_intensity: int = 190  # Controls chase segment size (higher = smaller segments)
    chase_speed: int = 185  # Base chase speed
    divider_color: list[int] = None  # [R, G, B] for battle line

    def __post_init__(self):
        if self.divider_color is None:
            self.divider_color = [200, 80, 0]  # Dark orange default


class WLEDController:
    """Controls WLED segments for game visualization."""

    def __init__(self, config: WLEDConfig):
        self.config = config
        self.client = httpx.AsyncClient(timeout=5.0)
        self.base_url = f"http://{config.host}"

    async def close(self):
        await self.client.aclose()

    async def get_state(self) -> dict:
        """Get current WLED state."""
        try:
            resp = await self.client.get(f"{self.base_url}/json/state")
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"WLED state error: {e}")
            return {}

    async def get_current_preset(self) -> Optional[int]:
        """Get currently active preset ID, or None if no preset active."""
        state = await self.get_state()
        ps = state.get("ps", -1)
        return ps if ps >= 0 else None

    async def set_state(self, state: dict) -> bool:
        """Push state update to WLED."""
        try:
            resp = await self.client.post(
                f"{self.base_url}/json/state",
                json=state
            )
            resp.raise_for_status()
            return True
        except Exception as e:
            print(f"WLED set_state error: {e}")
            return False

    def calculate_segments(
        self,
        home_win_pct: float,
        home_colors: list[list[int]],
        away_colors: list[list[int]],
    ) -> list[dict]:
        """
        Calculate segment configuration based on win probability.

        Args:
            home_win_pct: Home team win probability (0.0 to 1.0)
            home_colors: [[R,G,B], [R,G,B]] for home team
            away_colors: [[R,G,B], [R,G,B]] for away team

        Returns:
            List of segment configurations for WLED
        """
        start = self.config.roofline_start
        end = self.config.roofline_end
        total_pixels = end - start
        contested = self.config.contested_zone_pixels
        dark_buffer = self.config.dark_buffer_pixels
        min_pct = self.config.min_team_pct

        # Total battle zone = dark buffer + jiggle + dark buffer
        battle_zone = contested + (dark_buffer * 2)

        # Apply minimum dignity rule
        clamped_pct = max(min_pct, min(1.0 - min_pct, home_win_pct))

        # Calculate pixel boundaries
        # Home team gets pixels from the left, away from the right
        home_pixels = int((total_pixels - battle_zone) * clamped_pct)
        away_pixels = total_pixels - battle_zone - home_pixels

        # Segment boundaries: home | dark | jiggle | dark | away
        home_end = start + home_pixels
        dark_left_start = home_end
        dark_left_end = dark_left_start + dark_buffer
        jiggle_start = dark_left_end
        jiggle_end = jiggle_start + contested
        dark_right_start = jiggle_end
        dark_right_end = dark_right_start + dark_buffer
        away_start = dark_right_end

        # Both teams chase INWARD toward the battle line
        home_reversed = False  # Left-to-right (toward center)
        away_reversed = True   # Right-to-left (toward center)

        # Calculate chase speed based on momentum
        # Closer to 50/50 = faster (tense), blowout = slower (dominant)
        tension = 1.0 - abs(home_win_pct - 0.5) * 2  # 0=blowout, 1=even
        base_speed = self.config.chase_speed
        speed = int(base_speed + (tension * 15))  # Subtle speed variation

        segments = []
        next_id = 0

        # Segment for pixels BEFORE our range (black out)
        if start > 0:
            segments.append({
                "id": next_id,
                "start": 0,
                "stop": start,
                "grp": 1,
                "spc": 0,
                "on": True,
                "bri": 255,
                "col": [[0, 0, 0], [0, 0, 0], [0, 0, 0]],  # Black
                "fx": EFFECT_SOLID,
                "sel": False,
            })
            next_id += 1

        # Home team segment
        if home_pixels > 0:
            segments.append({
                "id": next_id,
                "start": start,
                "stop": home_end,
                "grp": 1,
                "spc": 0,
                "on": True,
                "bri": 255,
                "col": [home_colors[0], home_colors[1], [0, 0, 0]],
                "fx": EFFECT_CHASE_2,
                "sx": speed,
                "ix": self.config.chase_intensity,
                "rev": home_reversed,
                "sel": False,
            })
            next_id += 1

        # Left dark buffer
        if dark_buffer > 0:
            segments.append({
                "id": next_id,
                "start": dark_left_start,
                "stop": dark_left_end,
                "grp": 1,
                "spc": 0,
                "on": True,
                "bri": 255,
                "col": [[0, 0, 0], [0, 0, 0], [0, 0, 0]],
                "fx": EFFECT_SOLID,
                "sel": False,
            })
            next_id += 1

        # Jiggle divider (battle line)
        if contested > 0:
            segments.append({
                "id": next_id,
                "start": jiggle_start,
                "stop": jiggle_end,
                "grp": 1,
                "spc": 0,
                "on": True,
                "bri": 255,
                "col": [self.config.divider_color, [0, 0, 0], [0, 0, 0]],
                "fx": EFFECT_SCANNER,
                "sx": 180,
                "ix": 200,
                "rev": False,
                "sel": False,
            })
            next_id += 1

        # Right dark buffer
        if dark_buffer > 0:
            segments.append({
                "id": next_id,
                "start": dark_right_start,
                "stop": dark_right_end,
                "grp": 1,
                "spc": 0,
                "on": True,
                "bri": 255,
                "col": [[0, 0, 0], [0, 0, 0], [0, 0, 0]],
                "fx": EFFECT_SOLID,
                "sel": False,
            })
            next_id += 1

        # Away team segment
        if away_pixels > 0:
            segments.append({
                "id": next_id,
                "start": away_start,
                "stop": end,
                "grp": 1,
                "spc": 0,
                "on": True,
                "bri": 255,
                "col": [away_colors[0], away_colors[1], [0, 0, 0]],
                "fx": EFFECT_CHASE_2,
                "sx": speed,
                "ix": self.config.chase_intensity,
                "rev": away_reversed,
                "sel": False,
            })
            next_id += 1

        # Segment for pixels AFTER our range (black out)
        # Use a high number - WLED will clamp to actual strip length
        segments.append({
            "id": next_id,
            "start": end,
            "stop": 9999,
            "grp": 1,
            "spc": 0,
            "on": True,
            "bri": 255,
            "col": [[0, 0, 0], [0, 0, 0], [0, 0, 0]],
            "fx": EFFECT_SOLID,
            "sel": False,
        })

        return segments

    async def set_game_mode(
        self,
        home_win_pct: float,
        home_colors: list[list[int]],
        away_colors: list[list[int]],
    ) -> bool:
        """
        Set WLED to game mode with dynamic segments.

        Args:
            home_win_pct: Home team win probability (0.0 to 1.0)
            home_colors: [[R,G,B], [R,G,B]] for home team
            away_colors: [[R,G,B], [R,G,B]] for away team

        Returns:
            True if successful
        """
        segments = self.calculate_segments(
            home_win_pct, home_colors, away_colors
        )

        state = {
            "on": True,
            "bri": 255,
            "transition": self.config.transition_ms // 100,  # WLED uses 100ms units
            "seg": segments,
        }

        return await self.set_state(state)

    async def set_solid_team_colors(
        self,
        colors: list[list[int]],
        brightness: int = 255
    ) -> bool:
        """Set roofline to solid team colors (pre-game or post-game win)."""
        state = {
            "on": True,
            "bri": brightness,
            "seg": [{
                "id": 0,
                "start": self.config.roofline_start,
                "stop": self.config.roofline_end,
                "grp": 1,
                "spc": 0,
                "on": True,
                "bri": 255,
                "col": [colors[0], colors[1], [0, 0, 0]],
                "fx": EFFECT_CHASE,
                "sx": 128,
                "ix": 128,
                "rev": False,
            }]
        }
        return await self.set_state(state)

    async def turn_off(self) -> bool:
        """Turn off WLED."""
        return await self.set_state({"on": False})

    async def restore_preset(self, preset_id: int) -> bool:
        """Restore a saved preset."""
        return await self.set_state({"ps": preset_id})

    async def flash_colors(
        self,
        colors: list[list[int]],
        count: int = 3,
        flash_duration_ms: int = 500,
    ) -> bool:
        """
        Flash colors on/off multiple times.

        Args:
            colors: [[R,G,B], [R,G,B]] team colors to flash
            count: Number of flashes
            flash_duration_ms: Duration of each on/off cycle

        Returns:
            True if successful
        """
        # Single segment covering the whole strip
        segment = {
            "id": 0,
            "start": self.config.roofline_start,
            "stop": self.config.roofline_end,
            "grp": 1,
            "spc": 0,
            "on": True,
            "bri": 255,
            "col": [colors[0], colors[1], [0, 0, 0]],
            "fx": EFFECT_SOLID,
        }

        delay = flash_duration_ms / 1000.0

        for _ in range(count):
            # Flash on
            await self.set_state({
                "on": True,
                "bri": 255,
                "transition": 0,  # Instant
                "seg": [segment],
            })
            await asyncio.sleep(delay)

            # Flash off
            await self.set_state({"on": False, "transition": 0})
            await asyncio.sleep(delay)

        return True

    async def fade_off(self, duration_s: float = 3.0) -> bool:
        """
        Gracefully fade to black over duration.

        Args:
            duration_s: Fade duration in seconds

        Returns:
            True if successful
        """
        # WLED transition is in 100ms units
        transition = int(duration_s * 10)

        # Set brightness to 0 with long transition
        await self.set_state({
            "on": True,
            "bri": 0,
            "transition": transition,
        })

        # Wait for transition to complete, then turn off
        await asyncio.sleep(duration_s + 0.5)
        return await self.set_state({"on": False})
