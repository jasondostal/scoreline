export interface StripSegments {
  homePixels: number;
  awayPixels: number;
  bufferPixels: number;
  dividerPixels: number;
  totalPixels: number;
  homePct: number;
  bufferPct: number;
  dividerPct: number;
  awayPct: number;
}

/**
 * Calculate LED strip segment sizes from win probability and display settings.
 * Shared between instance card previews and simulator previews.
 */
export function calculateStripSegments(
  start: number,
  end: number,
  winPct: number,
  minTeamPct: number,
  contestedZonePixels: number,
  darkBufferPixels: number,
): StripSegments {
  const totalPixels = end - start + 1;
  const bufferPixels = darkBufferPixels;
  const dividerPixels = contestedZonePixels;

  // Available pixels for team segments (after buffers and divider)
  const teamPixels = Math.max(0, totalPixels - bufferPixels * 2 - dividerPixels);

  // Apply min dignity — neither team gets less than minTeamPct
  const clampedPct = Math.max(minTeamPct, Math.min(1 - minTeamPct, winPct));

  const homePixels = Math.round(teamPixels * clampedPct);
  const awayPixels = teamPixels - homePixels;

  // Convert to percentages for CSS rendering
  const homePct = totalPixels > 0 ? (homePixels / totalPixels) * 100 : 0;
  const bufferPct = totalPixels > 0 ? (bufferPixels / totalPixels) * 100 : 0;
  const dividerPct = totalPixels > 0 ? (dividerPixels / totalPixels) * 100 : 0;
  const awayPct = totalPixels > 0 ? (awayPixels / totalPixels) * 100 : 0;

  return {
    homePixels,
    awayPixels,
    bufferPixels,
    dividerPixels,
    totalPixels,
    homePct,
    bufferPct,
    dividerPct,
    awayPct,
  };
}
