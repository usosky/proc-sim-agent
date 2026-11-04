# <Model name>: build plan and log

- Goal: <the decision the model supports>
- Reference: <paper / SI table / datasheet, with page or table number>
- Aspen Plus: <V15> | units: <MET, bar, C> | property method: <...>
- Model folder: <path> (one subfolder per version)
- Out of scope for now: <...>

## KPIs

| KPI | How it is computed (`fw.py check --metric`) | Target or reference | Baseline |
|---|---|---|---|
| <capture> | `capture=1 - flow(GAS-OUT, CO2)/flow(GAS-IN, CO2)` | <>= 0.90> | |

## Stages

| # | Stage | Pass criteria | Status | Version |
|---|---|---|---|---|
| 1 | Components and property method | <...> | planned | |
| 2 | Feeds | <...> | planned | |
| 3 | <first unit> | <...> | planned | |

## Baseline (frozen)

| Parameter | Value | From |
|---|---|---|

## Decisions

- <date> v<x.y>: <decision> - <why>

## Open issues and limitations

- <...>

## Next action

- <...>
