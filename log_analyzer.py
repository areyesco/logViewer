#!/usr/bin/env python3
"""Log Analyzer CLI.

This tool reads logs from multiple components and controllers, merges them
chronologically and applies optional filtering and highlighting.
"""

import argparse
import os
import re
import heapq
from datetime import datetime
from typing import Dict, List, Optional, Iterable, Tuple

import yaml
from rich.console import Console
from rich.text import Text

# Mapping of spanish color names to english for rich
COLOR_NAMES = {
    "rojo": "red",
    "verde": "green",
    "amarillo": "yellow",
    "azul": "blue",
    "magenta": "magenta",
    "cian": "cyan",
    "blanco": "white",
}

console = Console()

def load_config(path: str) -> Dict[str, dict]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def resolve_color(name: str) -> str:
    if not name:
        return "white"
    name = name.lower()
    return COLOR_NAMES.get(name, name)

def parse_timestamp(value: str) -> datetime:
    """Parse a timestamp from various formats."""
    value = value.replace("Z", "+00:00")
    fmts = [
        "%Y-%m-%d %H:%M:%S.%f%z",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%d/%b/%Y:%H:%M:%S %z",
    ]
    for fmt in fmts:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return datetime.fromisoformat(value)

def iter_log_files(base_path: str) -> Iterable[Tuple[str, str, str]]:
    """Yield (store, controller, filepath)"""
    for store in os.listdir(base_path):
        store_path = os.path.join(base_path, store)
        if not os.path.isdir(store_path):
            continue
        for controller in os.listdir(store_path):
            ctrl_path = os.path.join(store_path, controller)
            if not os.path.isdir(ctrl_path):
                continue
            for root, _dirs, files in os.walk(ctrl_path):
                for name in files:
                    yield store, controller, os.path.join(root, name)

def match_component(file_name: str, config: Dict[str, dict], components: Optional[List[str]]) -> Optional[str]:
    for comp, cfg in config.items():
        if components and comp.lower() not in components:
            continue
        if re.match(cfg.get("filePattern", ""), file_name):
            return comp
    return None

def parse_line(line: str, cfg: dict) -> Optional[Dict[str, str]]:
    pattern = re.compile(cfg.get("lineFormat", ""))
    m = pattern.match(line)
    if not m:
        return None
    data = m.groupdict()
    data["timestamp"] = parse_timestamp(data["timestamp"])
    return data

def apply_highlight(text: str, patterns: List[dict]) -> Text:
    rich_text = Text(text)
    for pat in patterns:
        regex = re.compile(pat["regex"])
        color = resolve_color(pat.get("color", ""))
        for match in regex.finditer(text):
            if pat.get("highlightLine"):
                rich_text.stylize(color)
            groups = pat.get("groups") or {}
            if groups:
                for grp, grp_color in groups.items():
                    # allow group to be referenced by index or name
                    try:
                        idx = int(grp)
                    except ValueError:
                        idx = grp
                    try:
                        start, end = match.span(idx)
                    except (IndexError, KeyError):
                        continue
                    rich_text.stylize(resolve_color(grp_color), start, end)
            elif not pat.get("highlightLine"):
                start, end = match.span()
                rich_text.stylize(color, start, end)
    return rich_text

def build_message(data: Dict[str, str], show_fields: List[str]) -> str:
    return " ".join(str(data.get(f, "")) for f in show_fields)

def gather_entries(base_path: str, cfg: Dict[str, dict], components: Optional[List[str]], controllers: Optional[List[str]]) -> List[dict]:
    entries = []
    for store, controller, filepath in iter_log_files(base_path):
        if controllers and controller not in controllers:
            continue
        comp = match_component(os.path.basename(filepath), cfg, components)
        if not comp:
            continue
        comp_cfg = cfg[comp]
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                parsed = parse_line(line.rstrip(), comp_cfg)
                if not parsed:
                    continue
                entry = {
                    "timestamp": parsed["timestamp"],
                    "store": store,
                    "controller": controller,
                    "component": comp,
                    "message": build_message(parsed, comp_cfg.get("show", [])),
                    "raw": line.rstrip(),
                }
                entries.append(entry)
    return entries

def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze distributed logs")
    parser.add_argument("--path", default="./logs", help="Path to logs root")
    parser.add_argument("--components", help="Comma-separated component list")
    parser.add_argument("--controllers", help="Comma-separated controller list")
    parser.add_argument("--pattern", help="Filter regex pattern")
    parser.add_argument("--highlight-config", default="log_patterns.yaml", help="Pattern config file")
    args = parser.parse_args()

    components = [c.strip().lower() for c in args.components.split(",")] if args.components else None
    controllers = [c.strip() for c in args.controllers.split(",")] if args.controllers else None
    pattern_filter = re.compile(args.pattern) if args.pattern else None

    cfg = load_config(args.highlight_config)
    entries = gather_entries(args.path, cfg, components, controllers)
    entries.sort(key=lambda x: x["timestamp"])

    for entry in entries:
        if pattern_filter and not pattern_filter.search(entry["raw"]):
            continue
        comp_cfg = cfg[entry["component"]]
        line = apply_highlight(entry["message"], comp_cfg.get("patterns", []))
        header = Text(
            f"{entry['timestamp']} {entry['store']}/{entry['controller']} {entry['component']}: ",
            style="bold",
        )
        console.print(header.append(line))

if __name__ == "__main__":
    main()
