# Changelog

## 0.1.5 experimental

- Increase stale sensor timeout to 15 minutes and make it configurable in the rule parameters.
- Allow disabling stale checks by setting the timeout to 0 seconds.

## 0.1.4 experimental

- Add searchable entity mapping fields with typed suggestions and free entity ID input.

## 0.1.3 experimental

- Fix Ingress frontend asset, API and WebSocket paths so CSS and JavaScript load correctly inside Home Assistant.

## 0.1.2 experimental

- Update Python dependencies for Home Assistant base images using Python 3.14.
- Add a valid default Docker base image to silence the build argument warning.

## 0.1.1 experimental

- Fix Docker build on current Home Assistant base images by installing temporary build tools for Python packages with native extensions.
- Mark the add-on service run script executable during the image build.

## 0.1.0 experimental

- Initial add-on structure.
- FastAPI backend with Home Assistant API client.
- Rule engine with house consumption, target calculation, SOC strategy, B14 leader mode, central mode, deadband, ramp limiting and global limit enforcement.
- Ingress Web UI for setup, rule parameters, live status, decision log and manual override.
- Unit tests and GitHub Actions workflow.
