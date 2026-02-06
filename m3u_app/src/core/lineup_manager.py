# src/core/lineup_manager.py
"""
SportsLineupManager - Sequential team lineup assignment algorithm.
Fills lineups with unique teams (no team duplication within lineup).
Creates new lineups when teams repeat from existing lineups.
"""
from dataclasses import dataclass
from typing import Dict, List, Tuple, Set
from .entities import GameRecord


@dataclass
class Lineup:
    """Single lineup state - unique teams only."""
    id: int
    teams: Set[str]
    games: List[str]  # "Team1 vs Team2" for logging


class SportsLineupManager:
    """
    Sequential lineup assignment per league.
    Algorithm: Fill lineups 1→N with unique teams per lineup.
    """
    def __init__(self, league_key: str, service_prefix: str):
        self.league = league_key
        self.service_prefix = service_prefix
        self.lineups: List[Lineup] = []
    
    def assign_lineup(self, game: GameRecord) -> Tuple[str, int, int]:
        """
        Assign game to lineup with unique teams.
        Returns: (service_prefix, channel_assignment, lineup_id)
        
        Algorithm:
        1. Check existing lineups sequentially (1→N)
        2. Find first lineup where both teams are unique
        3. Create new lineup if no match found
        """
        team1, team2 = sorted([game.team1_canonical, game.team2_canonical])
        matchup_str = f"{team1} vs {team2}"
        
        # Sequential scan: lineup 1 → N
        for lineup in self.lineups:
            if team1 not in lineup.teams and team2 not in lineup.teams:
                # Unique teams found - assign sequential channel
                channel_assignment = len(lineup.games) + 1
                lineup.games.append(matchup_str)
                lineup.teams.add(team1)
                lineup.teams.add(team2)
                return self.service_prefix, channel_assignment, lineup.id
        
        # New lineup needed
        new_id = len(self.lineups) + 1
        new_lineup = Lineup(
            id=new_id,
            teams={team1, team2},
            games=[matchup_str]
        )
        self.lineups.append(new_lineup)
        return self.service_prefix, 1, new_id
    
    def get_lineup_summary(self) -> List[Dict]:
        """Debug: Current lineup state."""
        return [
            {
                "lineup_id": lineup.id,
                "team_count": len(lineup.teams),
                "game_count": len(lineup.games),
                "teams": sorted(lineup.teams),
                "games": lineup.games
            }
            for lineup in self.lineups
        ]
