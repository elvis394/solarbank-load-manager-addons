# Solarbank Load Manager Add-ons

Home Assistant add-on repository for the Solarbank Load Manager.

The add-on controls configured Anker Solix Solarbank setpoints through Home Assistant entities. It starts in dry-run mode, shows every decision in the UI, and only writes setpoints after dry-run is disabled explicitly.

## Installation

1. Open Home Assistant.
2. Go to Settings -> Add-ons -> Add-on Store.
3. Open the three-dot menu and choose Repositories.
4. Add this repository URL.
5. Install Solarbank Load Manager.
6. Start the add-on and open the Web UI.
7. Configure all entities and verify the dry-run decisions before enabling writes.

## Safety

The default global output limit is 800 W. Adjust it only when your installation is legally and technically allowed to do so. The add-on never intentionally writes a bank target below 0 W, above the bank maximum, or above the configured global limit.

## Repository Status

Version `0.1.0` is experimental.
