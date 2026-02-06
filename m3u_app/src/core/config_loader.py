# src/core/config_loader.py

"""
ConfigLoader - Two-phase config handling for clean dot-notation access.
load_all()
Phase 1: Creates exact directory structure + templates.
Phase 2: Hard-fail criticals, soft-fail optionals.
"""

import os
import json
import csv
from pathlib import Path
from typing import Any, Dict, List
from dataclasses import dataclass

@dataclass
class ConfigPaths:
    nginx_dir: str
    tvh_xml_dir: str
    log_dir: str
    diagnostics_dir: str

@dataclass
class ConfigSettings:
    network_timeout: int
    max_retries: int
    retry_delay: int
    log_retention_days: int
    log_level: str
    enable_compression: bool
    cleanup_on_startup: bool
    timezone: str



class ConfigError(Exception):
    """Raised on hard-fail config validation failure."""

class ConfigLoader:
    
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.config_dir = self.base_dir / "config"
        # EXACT directory structure from outline
        self.main_dir = self.config_dir / "main"
        self.m3u_dir = self.config_dir / "m3u"
        self.sports_dir = self.config_dir / "sports"
        self.epg_dir = self.config_dir / "epg"
        
        # Config state - None until loaded
        self.paths: ConfigPaths = None
        self.settings: ConfigSettings = None
        self.m3u_sources: List[Dict[str, str]] = []
        self.xml_sources: List[Dict[str, str]] = []
        self.tvg_name_map: Dict[str, tuple[str, str]] = {}
        self.channel_map: Dict[str, tuple[str, str]] = {}
        self.exclude_channels: List[str] = []
        self.exclude_groups: List[str] = []
        self.exclude_patterns: List[str] = []
        self.parse_exclusions: List[str] = []
        self.sports_config: Dict[str, Any] = {}
        self.category_map: Dict[str, str] = {}
        self.api_key: str = ""

        self._hard_fail_pending: set[str] = set()

    


    def load_all(self) -> None:
        """Single-pass: Create ALL configs first, then fail if hard configs were missing."""
        self._hard_fail_pending = set()
        HARD = True
        SOFT = False
        TXT_LISTS = {
            "exclude_channels": self.m3u_dir / "exclude_channels.txt",
            "exclude_groups": self.m3u_dir / "exclude_groups.txt",
            "exclude_patterns": self.m3u_dir / "exclude_patterns.txt",
            "parse_exclusions": self.m3u_dir / "parse_exclusions.txt",
        }

        # Phase 1: Process ALL configs - create if missing
        all_configs = [
            # Hard-fail configs (track if created)
            (self.main_dir / "paths.json", self._template_paths, self._load_paths, HARD),
            (self.main_dir / "settings.json", self._template_settings, self._load_settings, HARD),
            (self.m3u_dir / "m3u_sources.csv", self._template_csv, self._load_m3u_sources, HARD),
            (self.m3u_dir / "xml_sources.csv", self._template_csv, self._load_xml_sources, HARD),
            (self.sports_dir / "sports_config.json", self._template_sports_config, self._load_sports_config, HARD),
            (self.sports_dir / "api_key.txt", self._template_api_key, self._load_api_key, HARD),
            # Soft-fail configs
            (self.m3u_dir / "tvg_name_list.csv", self._template_csv_names, self._load_tvg_names, SOFT),
            (self.m3u_dir / "channel_list.csv", self._template_csv_names, self._load_channel_names, SOFT),  
            (self.epg_dir / "category_map.json", self._template_category_map, self._load_category_map, SOFT),
        ]

        for attr, path in TXT_LISTS.items():
                all_configs.append(
                    (path, self._template_empty_txt,
                    lambda a=attr, p=path: self._load_named_txt_list(a, p),
                    SOFT)
                )
        
        for path, templater, loader, is_hard in all_configs:
            path.parent.mkdir(parents=True, exist_ok=True)
            was_missing = not path.exists()
            
            if was_missing:
                templater(path)  # ✅ Uses CORRECT templater (passes self+path)
                if is_hard:
                    self._hard_fail_pending.add(str(path))
            
            try:
                loader()
            except (json.JSONDecodeError, csv.Error, EOFError):
                templater(path)
                loader()
            except KeyError as e:
                raise ConfigError(f"Invalid schema in {path}: missing {e}")

        
        # Phase 2: Fail if any hard configs were missing
        if self._hard_fail_pending:
            missing_list = "\n  - ".join(self._hard_fail_pending)
            raise ConfigError(
                f"Hard-fail configs were missing and auto-created:\n  - {missing_list}\n"
                "Edit these files before restarting."
            )


    # Loaders (unchanged)
    def _load_paths(self) -> None:
        with open(self.main_dir / "paths.json") as f:
            data = json.load(f)
            self.paths = ConfigPaths(**data)

    def _load_settings(self) -> None:
        with open(self.main_dir / "settings.json") as f:
            data = json.load(f)
            self.settings = ConfigSettings(**data)

    def _load_m3u_sources(self) -> None:
        with open(self.m3u_dir / "m3u_sources.csv", newline='') as f:
            reader = csv.DictReader(f)
            self.m3u_sources = list(reader)

    def _load_xml_sources(self) -> None:
        with open(self.m3u_dir / "xml_sources.csv", newline='') as f:
            reader = csv.DictReader(f)
            self.xml_sources = list(reader)

    def _load_sports_config(self) -> None:
        with open(self.sports_dir / "sports_config.json") as f:
            self.sports_config = json.load(f)

    def _load_api_key(self) -> None:
        with open(self.sports_dir / "api_key.txt") as f:
            self.api_key = f.read().strip()

    def _load_name_map(
        self,
        path: Path,
        target: dict[str, tuple[str, str]]
    ) -> None:
        with open(path, newline='') as f:
            reader = csv.DictReader(f)
            required = {"search_str", "new_display_name", "ch_no"}
            if not required.issubset(reader.fieldnames or []):
                raise ConfigError(f"{path} invalid CSV header")
            for row in reader:
                target[row["search_str"]] = (
                    row["new_display_name"],
                    row["ch_no"]
                )

    def _load_tvg_names(self) -> None:
        self._load_name_map(
            self.m3u_dir / "tvg_name_list.csv",
            self.tvg_name_map
        )

    def _load_channel_names(self) -> None:
        self._load_name_map(
            self.m3u_dir / "channel_list.csv",
            self.channel_map
        )
    # def _load_txt_list(self, path: Path) -> list[str]:
    #     with open(path) as f:
    #         return [line.strip() for line in f if line.strip()]

    def _load_named_txt_list(self, attr: str, path: Path) -> None:
        with open(path) as f:
            txt_list = [line.strip() for line in f if line.strip()]
        setattr(self, attr, txt_list)


    def _load_category_map(self) -> None:
        with open(self.epg_dir / "category_map.json") as f:
            self.category_map = json.load(f)

    # Template writers (consolidated + exact from outline)
    def _write_template(self, path: Path, template: Any) -> None:
        tmp_path = path.with_suffix('.tmp')
        if isinstance(template, dict):
            with open(tmp_path, 'w') as f:
                json.dump(template, f, indent=2)
        else:
            with open(tmp_path, 'w') as f:
                f.write(template)
        os.rename(tmp_path, path)

    def _template_paths(self, path: Path) -> None:
        self._write_template(path, {
            "nginx_dir": "/opt/m3uapp/tvheadend/web",
            "tvh_xml_dir": "/opt/appdata/tvheadend/data",
            "log_dir": "/opt/m3uapp/logs",
            "diagnostics_dir": "/opt/m3uapp/logs/diagnostics"
        })

    def _template_settings(self, path: Path) -> None:
        self._write_template(path, {
            "network_timeout": 30, "max_retries": 3, "retry_delay": 10,
            "log_retention_days": 14, "log_level": "DEBUG",
            "enable_compression": True, "cleanup_on_startup": True,
            "timezone": "America/Boise"
        })

    def _template_csv(self, path: Path) -> None:
        self._write_template(path, "url,output_name,description\n")

    def _template_csv_names(self, path: Path) -> None:
        self._write_template(path, "search_str,new_display_name,ch_no\n")

    def _template_empty_txt(self, path: Path) -> None:
        self._write_template(path, "")

    def _template_sports_config(self, path: Path) -> None:
        self._write_template(path, {
            "NFL": {
                "service_prefix": "NFL", "hints": ["NFL", "FOOTBALL"],
                "api_sports": {"enabled": True, "endpoint": "american-football", "league_name": "NFL"},
                "game_duration": {"hours": 4, "minutes": 0},
                "teams": {"Pittsburgh Steelers": {"canonical": "Pittsburgh Steelers", "league": "NFL", "synonyms": ["Steelers", "Pittsburgh"]}}
            }
        })

    def _template_api_key(self, path: Path) -> None:
        self._write_template(path, "YOUR_API_SPORTS_IO_KEY_HERE\n\n# Get free key: https://api-sports.io/")

    def _template_category_map(self, path: Path) -> None:
        self._write_template(path, {"3x3 basketball": "Team sports", "Action Sports": "Sports"})
