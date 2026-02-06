# src/core/entities.py
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime

@dataclass
class ChannelRecord:
    """Per-M3U mutable - cleared between providers."""
    rawtags: List[Dict[str, str]] = field(default_factory=list)
    attributes: Dict[str, str] = field(default_factory=dict)  # tvg-id, tvg-name, etc.
    displayname: str = ""
    urls: List[str] = field(default_factory=list)

@dataclass 
class GameRecord:
    """Persists across providers until sports.xml."""
    league: str
    serviceprefix: str
    matchupkey: str  # "Buffalo Bills Pittsburgh Steelers" (alpha sorted)
    team1canonical: str  # Alphabetical team 1
    team2canonical: str  # Alphabetical team 2
    apiendpoint: str
    lineupid: int = 0
    channelassignment: int = 0  
    apitime: Optional[datetime] = None
    gameduration: Optional[Dict[str, int]] = None  # From LeagueConfig

@dataclass
class EndpointRecord:
    """Groups GameRecords by API endpoint."""
    endpoint: str
    games: Dict[str, GameRecord] = field(default_factory=dict)  # matchupkey -> GameRecord

@dataclass
class APIRecord:
    endpoint: str
    leaguename: str  
    apikey: str
    games: List[Dict]  # Raw API response
    lookupleague: Optional[str] = None


@dataclass(frozen=True)
class TeamInfo:
    canonical: str
    league: str
    synonyms: List[str] = field(default_factory=list)

@dataclass(frozen=True)
class LeagueConfig:
    serviceprefix: str
    hints: List[str]
    apisports: Optional[Dict] = None  # enabled, endpoint, leaguename
    gameduration: Optional[Dict[str, int]] = None  # hours, minutes
    teams: Dict[str, TeamInfo] = field(default_factory=dict)  # canonical -> TeamInfo

@dataclass(frozen=True)
class SportsLookups:
    """Immutable lookup tables."""
    leagues: Dict[str, LeagueConfig]  # "NFL" -> LeagueConfig
    allhints: Dict[str, str]  # flattened hints -> league
    teamindex: Dict[str, TeamInfo]  # flattened canonical+synonyms -> TeamInfo