# Solarbank Load Manager

Experimental Home Assistant add-on for transparent load-based control of two Anker Solix solar banks.

## What It Does

- Reads configured Home Assistant sensor entities for grid import, grid export, SOC, PV power and AC output.
- Calculates house consumption and a safe total output target.
- Uses B14 as the default leading bank and lets B16 supplement the remaining target.
- Offers an optional central distribution mode.
- Applies SOC limits, time-based discharge release, deadband, ramp limiting and a global output limit.
- Shows every decision in the Web UI before writing anything.

## First Start

The add-on starts with `dry_run: true`. Open the Web UI, map your entities, check the live decisions, and only then disable dry run.

## Legal and Electrical Safety

The default global output limit is 800 W. The user is responsible for choosing a limit that is valid for the actual installation.
