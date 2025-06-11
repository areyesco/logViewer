# Log Viewer

CLI tool to analyze distributed logs grouped by store and controller.

## Setup

```bash
pip install -r requirements.txt
```

## Usage

```bash
python log_analyzer.py --path ./logs \
    --components mongo,rabbitmq \
    --controllers CC,EE \
    --pattern "Exception|Timeout" \
    --highlight-config log_patterns.yaml
```

All arguments are optional. By default it reads `./logs` and uses `log_patterns.yaml`.

## `log_patterns.yaml`

The highlight configuration is organized by component. Each component entry may define:

- `filePattern`: regex used to match log files for that component.
- `lineFormat`: regex with named capture groups describing the log line format.
- `show`: ordered list of capture group names that will be displayed.
- `patterns`: list of highlight rules applied to each built message.
  - `regex`: regular expression written using YAML literal blocks so it doesn't require quoting.
  - `highlightLine`: when `true` the entire line is colored.
  - `color`: color name (English or Spanish) or hexadecimal value.
  - `groups`: optional mapping of group names or indexes to colors.

### Example

```yaml
Mongo:
  filePattern: mongo.*\.log
  lineFormat: >
    \{"t":\{"\$date":"(?P<timestamp>[^\"]+)"\},"s":"(?P<level>[^"]+)",
    "msg":"(?P<message>.*?)".*\}
  show:
    - timestamp
    - level
    - message
  patterns:
    - regex: |
        New state node: (?P<nodo>.*?) - (?P<contador>[0-9]{1,10})
      highlightLine: false
      groups:
        nodo: amarillo
        contador: verde
```

Named capture groups (e.g. `nodo`, `contador`) allow coloring specific portions of a match.
