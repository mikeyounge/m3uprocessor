# TVHeadend M3U Processor - Implementation Status

Purpose: Living document to track the progress of implementing this project. Each section is to reflect the current status of the project  
Guidelines:

- File Hierarchy to be updated with the status of each directory/module
- Mermaid Graph tracks the business logic workflow that has been coded to this point
- Pseudo code snippets are to represent each function with a summary of actions. Do not provide actual code
- Implementation Table follows progress of implementation, adding more context to the phases
- Todo list is to track what has yet to be done

**Status:** Active | **Last Updated:** 2026-02-05 | **Progress:** 4/24 modules

## File Hierarchy (Live)

📋 File Hierarchy (Live)

```text
opt/m3uapp/
├── config/
│ ├── main/
│ │ ├── paths.json [HARD FAIL]
│ │ └── settings.json [HARD FAIL]
│ ├── m3u/
│ │ ├── m3u_sources.csv [HARD FAIL]
│ │ ├── xml_sources.csv [HARD FAIL]
│ │ ├── tvg_name_list.csv [SOFT FAIL]
│ │ ├── channel_list.csv [SOFT FAIL]
│ │ ├── exclude_channels.txt [SOFT FAIL]
│ │ ├── exclude_groups.txt [SOFT FAIL]
│ │ ├── exclude_patterns.txt [SOFT FAIL]
│ │ └── parse_exclusions.txt [SOFT FAIL]
│ ├── sports/
│ │ ├── sports_config.json [HARD FAIL]
│ │ └── api_key.txt [HARD FAIL]
│ └── epg/
│ └── category_map.json [SOFT FAIL]
├── src/
│ └── core/
│ ├── entities.py [✅ COMPLETE]
│ ├── logger.py [✅ COMPLETE]
│ ├── config_loader.py [✅ COMPLETE]
│ ├── diagnostic_collector.py [PENDING]
│ ├── lineup_manager.py [PENDING]
│ └── sports_lookups.py [PENDING]
│ ├── m3u/ [PHASE 2]
│ └── epg/ [PHASE 3]
├── logs/ [RUNTIME]
├── tvheadend/web/ [OUTPUT]
└── cron.sh [PHASE 4]
```

🔄 Workflow Business Logic

```mermaid
flowchart TD
    A[Orchestrator Called<br/>RunManager(base_dir)] --> B[RunManager.initialize()]
    B --> C[ConfigLoader.load_all()]
    C --> D{{Hard configs<br/>missing?}}
    D -->|Yes| E[ConfigError<br/>Fail Fast]
    D -->|No| F[get_local_datetime<br/>run_id + date_folder]
    F --> G[Create log_root<br/>logs/YYYY-MM-DD/RunID<br/>+ diagnostics/]
    G --> H[setup_logging<br/>JSON structured<br/>run_id prefixed]
    H --> I{config.cleanup?}
    I -->|Yes| J[_cleanup_old_runs<br/>delete > retention_days]
    J --> K[_update_current_symlink<br/>atomic tmp→current]
    I -->|No| K
    K --> L[Return RunContext<br/>run_id, dirs, config, loggers]
    
    L --> M[Business Logic Entry<br/>Using RunContext]
```

🛠️ Pseudocode Pipeline

`src/core/runmanager.py`

```python
from .config_loader import ConfigLoader
from .logger import setup_logging, get_local_datetime, LOCAL_FORMAT, DATE_FOLDER_FORMAT
from dataclasses import dataclass
from typing import Dict
import os, shutil

@dataclass
class RunContext:
    run_id: str; date_folder: str; log_dir: str; diagnostics_dir: str
    config_loader: ConfigLoader; loggers: Dict[str, object]

class RunManager:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.config_loader = ConfigLoader(base_dir)
        self.context = None
    
    def initialize(self) -> RunContext:
        self.config_loader.load_all()
        config = self.config_loader
        run_dt = get_local_datetime(config.settings.timezone)
        run_id, date_folder = run_dt.strftime(LOCAL_FORMAT), run_dt.strftime(DATE_FOLDER_FORMAT)
        run_root = f"{config.paths.log_dir}/{date_folder}/{run_id}"
        diagnostics_dir = f"{run_root}/diagnostics"; os.makedirs(diagnostics_dir, exist_ok=True)
        loggers = setup_logging(run_root, run_id, config.settings.timezone, config.settings.log_level)
        if config.settings.cleanup_on_startup: self._cleanup_old(config.paths.log_dir, config.settings.log_retention_days, loggers["main"])
        self._update_symlink(config.paths.log_dir, run_root, loggers["main"])
        self.context = RunContext(run_id, date_folder, run_root, diagnostics_dir, config, loggers)
        return self.context
    
    def _cleanup_old(self, logdir: str, days: int, logger): 
        cutoff = get_local_datetime().date() - timedelta(days=days)
        for date_folder in os.listdir(logdir):
            date_path = f"{logdir}/{date_folder}"
            if os.path.isdir(date_path) and datetime.strptime(date_folder, DATE_FOLDER_FORMAT).date() < cutoff:
                shutil.rmtree(date_path); logger.info("Cleanup", extra={"folder": date_path})
    
    def _update_symlink(self, logdir: str, target: str, logger):
        current, tmp = f"{logdir}/current", f"{logdir}/current.tmp"
        os.symlink(target, tmp); os.replace(tmp, current); logger.info("Symlink OK", extra={"target": target})

```

`src/core/logger.py`
```python
import json, logging, os, zoneinfo
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Dict, Any

UTC_FORMAT, LOCAL_FORMAT, DATE_FOLDER_FORMAT = "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d_%H-%M-%S", "%Y-%m-%d"

def get_local_datetime(tz: str) -> datetime: return datetime.now(zoneinfo.ZoneInfo(tz))

class JsonFormatter(logging.Formatter):
    def __init__(self, tz: str): self.tz = zoneinfo.ZoneInfo(tz)
    def format(self, rec: logging.LogRecord) -> str:
        local = datetime.fromtimestamp(rec.created, self.tz)
        payload = {"timestamp": local.strftime(UTC_FORMAT), "level": rec.levelname, "module": rec.name, "message": rec.getMessage(), **{k:v for k,v in rec.__dict__.items() if k not in logging.STD_KEYS}}
        return json.dumps(payload, separators=(",", ":"))

def make_handler(logfile: str, tz: str, max_bytes=10e6, backups=5) -> RotatingFileHandler:
    h = RotatingFileHandler(logfile, maxBytes=max_bytes, backupCount=backups, encoding="utf-8")
    h.setFormatter(JsonFormatter(tz)); h.setLevel(logging.DEBUG); return h

def setup_logging(log_dir: str, run_id: str, tz: str="UTC", level="DEBUG") -> Dict[str, logging.Logger]:
    os.makedirs(log_dir, exist_ok=True)
    lvl = getattr(logging, level.upper())
    logging.basicConfig(level=logging.WARNING)
    def build(name: str, suffix: str) -> logging.Logger:
        lg = logging.getLogger(name); lg.setLevel(lvl); lg.propagate = False; lg.handlers.clear()
        lg.addHandler(make_handler(os.path.join(log_dir, f"{run_id}_{suffix}.log"), tz)); return lg
    return {k: build(k, k) for k in ("main", "processor", "sports_api", "xml_filter")}

def get_logger(name: str) -> logging.Logger: return logging.getLogger(name)


```

`src/core/config_loader.py`
```python
from pathlib import Path
from typing import Dict, List, Any
from dataclasses import dataclass
import json, csv, os

@dataclass
class ConfigPaths: nginx_dir: str; tvh_xml_dir: str; log_dir: str; diagnostics_dir: str
@dataclass
class ConfigSettings: network_timeout: int; max_retries: int; retry_delay: int; log_retention_days: int; log_level: str; enable_compression: bool; cleanup_on_startup: bool; timezone: str

class ConfigError(Exception): pass

class ConfigLoader:
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.config_dir = self.base_dir / "config"
        self.main_dir = self.config_dir / "main"
        self.m3u_dir = self.config_dir / "m3u"
        self.sports_dir = self.config_dir / "sports"
        self.epg_dir = self.config_dir / "epg"
        # state: paths, settings, m3u_sources:List[Dict], xml_sources:List[Dict], maps:Dicts, lists:List[str], api_key:str
        
    def load_all(self):
        configs = [
            (self.main_dir/"paths.json", self._template_paths, self._load_paths, True),
            (self.main_dir/"settings.json", self._template_settings, self._load_settings, True),
            (self.m3u_dir/"m3u_sources.csv", self._template_csv, self._load_csv_lists, True),
            (self.m3u_dir/"xml_sources.csv", self._template_csv, self._load_csv_lists, True),
            (self.sports_dir/"sports_config.json", self._template_sports_config, self._load_json_dict, True),
            (self.sports_dir/"api_key.txt", self._template_api_key, self._load_str, True),
            (self.m3u_dir/"tvg_name_list.csv", self._template_csv_names, lambda: self._load_name_map(self.tvg_name_map), False),
            (self.m3u_dir/"channel_list.csv", self._template_csv_names, lambda: self._load_name_map(self.channel_map), False),
            (self.epg_dir/"category_map.json", self._template_category_map, self._load_json_dict, False),
        ]
        txt_lists = ["exclude_channels", "exclude_groups", "exclude_patterns", "parse_exclusions"]
        
        for attr, path in [(attr, self.m3u_dir/f"{attr}.txt") for attr in txt_lists]:
            configs.append((path, self._template_empty_txt, lambda a=attr,p=path: self._load_txt_list(a,p), False))
            
        pending_hard = set()
        for path, template, loader, is_hard in configs:
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists(): template(path); pending_hard.add(str(path)) if is_hard else None
            loader()
        if pending_hard: raise ConfigError(f"Missing hard configs: {pending_hard}")
    
    def _load_csv_lists(self): self.m3u_sources, self.xml_sources = list(csv.DictReader(open(self.m3u_dir/"m3u_sources.csv"))), list(csv.DictReader(open(self.m3u_dir/"xml_sources.csv")))
    def _load_name_map(self, target: Dict): for row in csv.DictReader(open(self.m3u_dir/"tvg_name_list.csv")): target[row["search_str"]] = (row["new_display_name"], row["ch_no"])
    def _load_txt_list(self, attr: str, path: Path): setattr(self, attr, [l.strip() for l in open(path) if l.strip()])
    def _load_json_dict(self): self.sports_config = json.load(open(self.sports_dir/"sports_config.json"))
    
    def _template_paths(self, p): self._write(p, {"nginx_dir":"/opt/m3uapp/tvheadend/web", "tvh_xml_dir":"/opt/appdata/tvheadend/data", "log_dir":"/opt/m3uapp/logs", "diagnostics_dir":"/opt/m3uapp/logs/diagnostics"})
    def _template_csv(self, p): self._write(p, "url,output_name,description\n")
    def _write(self, p: Path, data): with open(p.with_suffix('.tmp'), 'w') as f: json.dump(data, f, indent=2) if isinstance(data,dict) else f.write(data); os.rename(p.with_suffix('.tmp'), p)
```

📊 Implementation Status

| Phase              | Module          | Status     | Notes                                    |
|--------------------|-----------------|------------|------------------------------------------|
| Phase 0: Bootstrap | setup.py        | ✅ Complete | 12 config files, exact outline structure |
| Phase 1: Core      | configloader.py | ⚠️ Drafted | Needs exact hard/soft fail logic         |
|                    | entities.py     | ❌ Pending  | NEXT - 8 dataclasses                     |

🎯 Next Single Step
src/core/entities.py - 8 dataclasses EXACT from outline:

1. ChannelRecord - Per M3U, mutable, cleared after each provider
2. GameRecord - Global, persists til sports.xml
3. EndpointRecord - API grouping
4. APIRecord - Raw API response
5. TeamInfo(frozen) - Canonical team lookup
6. LeagueConfig(frozen) - League settings
7. SportsLookups(frozen) - Master lookup index
8. ConfigPaths, ConfigSettings - From configloader draft