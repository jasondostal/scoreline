"""Test 2: WLED segment calculation boundary conditions.

Pure math — no HTTP, no mocks. Tests pixel boundaries, gaps, and edge cases.
"""

from wled import WLEDConfig, WLEDController

HOME = [[0, 100, 0], [0, 50, 0]]  # Green
AWAY = [[100, 0, 0], [50, 0, 0]]  # Red


def _get_segments(pct, start=0, end=300, contested=6, dark_buffer=4, min_pct=0.05):
    config = WLEDConfig(
        host="test",
        roofline_start=start,
        roofline_end=end,
        contested_zone_pixels=contested,
        dark_buffer_pixels=dark_buffer,
        min_team_pct=min_pct,
    )
    ctrl = WLEDController(config)
    return ctrl.calculate_segments(pct, HOME, AWAY)


def _named_segments(segments):
    """Return dict of name -> segment for active segments (not cleanup/blackout)."""
    return {s["n"]: s for s in segments if "n" in s and s.get("stop", 0) > 0}


class TestSegmentBoundaries:
    """Verify no pixel gaps or overlaps."""

    def test_segments_cover_full_range(self):
        """All pixels from start to end are covered (no gaps)."""
        segs = _get_segments(0.5, start=0, end=300)
        named = _named_segments(segs)

        # Extract boundaries for the 5 main segments
        home = named["HOME"]
        buffer_l = named["BUFFER-L"]
        divider = named["DIVIDER"]
        buffer_r = named["BUFFER-R"]
        away = named["AWAY"]
        blackout_r = named["BLACKOUT-R"]

        # Segments should chain without gaps
        assert home["start"] == 0
        assert home["stop"] == buffer_l["start"]
        assert buffer_l["stop"] == divider["start"]
        assert divider["stop"] == buffer_r["start"]
        assert buffer_r["stop"] == away["start"]
        assert away["stop"] == 300
        assert blackout_r["start"] == 300

    def test_segments_cover_with_offset_start(self):
        """When start > 0, there's a BLACKOUT-L segment."""
        segs = _get_segments(0.5, start=50, end=300)
        named = _named_segments(segs)

        assert "BLACKOUT-L" in named
        assert named["BLACKOUT-L"]["start"] == 0
        assert named["BLACKOUT-L"]["stop"] == 50
        assert named["HOME"]["start"] == 50

    def test_50_50_symmetric(self):
        """At 50%, home and away should be roughly equal."""
        segs = _get_segments(0.5, start=0, end=300, contested=6, dark_buffer=4)
        named = _named_segments(segs)

        home_pixels = named["HOME"]["stop"] - named["HOME"]["start"]
        away_pixels = named["AWAY"]["stop"] - named["AWAY"]["start"]

        # With 300 pixels and 14 battle zone, each team gets ~143
        # Allow ±1 for integer rounding
        assert abs(home_pixels - away_pixels) <= 1

    def test_no_negative_segments(self):
        """No segment should have stop < start."""
        for pct in [0.0, 0.05, 0.25, 0.5, 0.75, 0.95, 1.0]:
            segs = _get_segments(pct)
            for s in segs:
                if s.get("stop", 0) > 0:  # Skip cleanup segments
                    assert s["stop"] >= s.get("start", 0), f"Negative segment at {pct}: {s}"


class TestMinDignity:
    """Verify minimum team percentage clamping."""

    def test_home_at_zero_gets_min_dignity(self):
        """0% home win should be clamped to min_team_pct."""
        segs = _get_segments(0.0, min_pct=0.05)
        named = _named_segments(segs)

        home_pixels = named["HOME"]["stop"] - named["HOME"]["start"]
        total_playable = 300 - 6 - (4 * 2)  # total - contested - buffers
        min_pixels = int(total_playable * 0.05)

        assert home_pixels == min_pixels

    def test_home_at_hundred_gets_clamped(self):
        """100% home win should leave away with min_team_pct."""
        segs = _get_segments(1.0, min_pct=0.05)
        named = _named_segments(segs)

        away_pixels = named["AWAY"]["stop"] - named["AWAY"]["start"]
        total_playable = 300 - 6 - (4 * 2)
        min_pixels = total_playable - int(total_playable * (1.0 - 0.05))

        assert away_pixels >= min_pixels


class TestEdgeCases:
    """Edge cases for strip configurations."""

    def test_tiny_strip(self):
        """Very small strip (30 pixels) should still produce valid segments."""
        segs = _get_segments(0.5, start=0, end=30, contested=2, dark_buffer=1)
        named = _named_segments(segs)

        # Should still have all 5 game segments
        assert "HOME" in named
        assert "AWAY" in named
        assert "DIVIDER" in named

    def test_cleanup_segments_present(self):
        """Should include cleanup segments (stop=0) to clear old WLED state."""
        segs = _get_segments(0.5)
        cleanup = [s for s in segs if s.get("stop") == 0 and "n" not in s]
        assert len(cleanup) > 0

    def test_chase_speed_varies_with_tension(self):
        """Chase speed should be faster at 50/50 (tense) than at blowout."""
        segs_even = _get_segments(0.5)
        segs_blowout = _get_segments(0.95)

        home_even = next(s for s in segs_even if s.get("n") == "HOME")
        home_blowout = next(s for s in segs_blowout if s.get("n") == "HOME")

        # Even game should have higher speed (more tension)
        assert home_even["sx"] > home_blowout["sx"]
