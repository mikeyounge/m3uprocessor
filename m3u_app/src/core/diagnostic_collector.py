# src/core/diagnostic_collector.py
"""
Diagnostic collector for unmapped games, teams, and categories.
Writes JSON diagnostics to run folder at end of pipeline.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict
import json


@dataclass
class DiagnosticCollector:
    """Collects diagnostic data for debugging pipeline failures."""
    base_dir: Path
    run_id: str
    
    unmapped_games: List[Dict] = field(default_factory=list)
    missing_teams: List[Dict] = field(default_factory=list)
    unmapped_categories: Dict[str, int] = field(default_factory=dict)
    
    def add_unmapped_game(self, 
                         league: str, 
                         team1_raw: str, 
                         team2_raw: str, 
                         reason: str, 
                         provider: str = "") -> None:
        """Log M3U sports detection failure."""
        self.unmapped_games.append({
            "league": league,
            "raw_display_name": f"{team1_raw} vs {team2_raw}",
            "teams": [team1_raw, team2_raw],
            "provider": provider,
            "reason": reason
        })
    
    def add_missing_team(self, 
                        league: str, 
                        teams: List[str], 
                        reason: str) -> None:
        """Log API team lookup failure."""
        self.missing_teams.append({
            "league": league,
            "teams": teams,
            "reason": reason
        })
    
    def add_unmapped_category(self, category: str) -> None:
        """Log XML category mapping failure."""
        self.unmapped_categories[category] = self.unmapped_categories.get(category, 0) + 1
    
    def dump_all(self) -> None:
        """Write all diagnostics to JSON files in run folder."""
        diagnostics_dir = self.base_dir / self.run_id / "diagnostics"
        diagnostics_dir.mkdir(parents=True, exist_ok=True)
        
        diagnostics = [
            ("unmapped_games.json", self.unmapped_games),
            ("missing_teams.json", self.missing_teams),
            ("unmapped_categories.json", self.unmapped_categories)
        ]
        
        for filename, data in diagnostics:
            filepath = diagnostics_dir / filename
            # Ensure datetime serializable
            filepath.write_text(
                json.dumps(data, indent=2, default=str),
                encoding="utf-8"
            )
