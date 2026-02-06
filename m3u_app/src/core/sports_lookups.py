# src/core/sports_lookups.py
"""
Immutable lookup tables for O(1) team/hint matching.
Built once from sports_config.json for M3U ChannelProcessor.
"""
from typing import Dict, List, Optional
from .entities import (
    TeamInfo, LeagueConfig, SportsLookups
)


def build_sports_lookups(sports_config: Dict[str, Dict]) -> SportsLookups:
    """
    Factory: sports_config.json → immutable SportsLookups.
    
    Flattens nested config into 3 O(1) indexes:
    - leagues: "NFL" → LeagueConfig  
    - all_hints: "nfl","football" → "NFL"
    - team_index: "steelers","pittsburgh" → TeamInfo(canonical="Pittsburgh Steelers")
    """
    leagues: Dict[str, LeagueConfig] = {}
    all_hints: Dict[str, str] = {}
    team_index: Dict[str, TeamInfo] = {}
    
    for league_key, league_data in sports_config.items():
        # Build league teams dict
        teams: Dict[str, TeamInfo] = {}
        for canonical, synonyms_data in league_data["teams"].items():
            synonyms = synonyms_data if isinstance(synonyms_data, list) else [synonyms_data]
            team_info = TeamInfo(canonical, league_key, synonyms)
            teams[canonical] = team_info
            
            # Global canonical index (lowercase → TeamInfo)
            team_index[canonical.lower()] = team_info
            
            # Global synonym index (lowercase → TeamInfo)
            for synonym in synonyms:
                team_index[synonym.lower()] = team_info
        
        # Build LeagueConfig
        league_config = LeagueConfig(
            serviceprefix=league_data["service_prefix"],
            hints=league_data["hints"],
            apisports=league_data.get("api_sports"),
            gameduration=league_data["game_duration"],
            teams=teams
        )
        leagues[league_key] = league_config
        
        # Global hint index (lowercase hint → league_key)
        for hint in league_data["hints"]:
            all_hints[hint.lower()] = league_key
    
    return SportsLookups(
        leagues=leagues,
        allhints=all_hints,
        teamindex=team_index
    )


def find_synonym_in_dict(
    raw_team: str, 
    team_dict: Dict[str, TeamInfo]
) -> Optional[TeamInfo]:
    """
    Exact match → canonical → synonym scan → None.
    
    Args:
        raw_team: "steelers" (from M3U display_name)
        team_dict: LeagueConfig.teams or SportsLookups.team_index
        
    Returns:
        TeamInfo(canonical="Pittsburgh Steelers", league="NFL", ...)
    """
    raw_lower = raw_team.lower().strip()
    
    # 1. Exact canonical match
    if raw_lower in team_dict:
        return team_dict[raw_lower]
    
    # 2. Synonym scan (simple 'in' check per outline)
    for team_info in team_dict.values():
        if raw_lower in [s.lower() for s in team_info.synonyms]:
            return team_info
    
    return None
