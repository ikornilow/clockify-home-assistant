# Clockify-HA

An unofficial community integration for Home Assistant. Not affiliated with, endorsed by, or sponsored by Clockify.

A HACS custom integration that reads Clockify time tracking data and exposes it as Home Assistant sensors.

## Features

- Active timer description and start/project attributes
- Today's tracked time for the configured Clockify user and workspace
- Billable and non-billable time tracked today and this week
- Start/stop Clockify timers and create completed entries with the `clockify.start_timer`, `clockify.stop_timer`, and `clockify.create_time_entry` actions
- UI setup using a Clockify API key and workspace picker
- Refresh every thirty minutes as a fallback; API key calls use Clockify's documented REST API

Timer starts use `input_text.default_clockify_project` unless `project_id` is passed; the previous entry description is reused unless `description` is passed.

## Webhooks

When Home Assistant Cloud (Nabu Casa) is connected, the integration registers Clockify callbacks for timer start, timer stop, and time-entry updates. These events request an immediate coordinator refresh; thirty-minute polling remains as a fallback. Clockify counts these as three workspace webhooks (the Free plan's full webhook allowance). If those slots are already occupied or registration fails, polling continues without webhooks and registration retries hourly. Removing the integration deletes its Clockify subscriptions.

## Installation

### HACS custom repository

To install through HACS:
1. Add this repository in HACS as an **Integration** custom repository.
2. Install **Clockify-HA** and restart Home Assistant.
3. Open **Settings → Devices & services → Add integration → Clockify-HA**.
4. Create an API key in Clockify profile settings, enter it, and select a workspace.

### Manual

Copy `custom_components/clockify` into your Home Assistant `config/custom_components/` directory, restart Home Assistant, and add the Clockify-HA integration from Devices & services.

## Entities

- **Active timer**: active description, or `Not tracking`; attributes include `is_tracking`, `started_at`, project, and workspace.
- **Time tracked today**: total duration in hours for the current local calendar day.
- **Time tracked today (billable/non-billable)**: durations split by Clockify's entry `billable` flag.
- **Time tracked this week**: total duration in hours from Monday through now.
- **Time tracked this week (billable/non-billable)**: durations split by Clockify's entry `billable` flag.
- **Time-Entry in progress** and **Last Time-Entry**: compatibility data for existing automations.

`clockify.start_timer` accepts optional `project_id`, `description`, and `workspace_id`; `clockify.stop_timer` accepts optional `workspace_id`. `clockify.create_time_entry` accepts `project_id`, `start`, `end`, optional `description`, `tag_ids`, and `workspace_id`. Each action refreshes the sensors after Clockify confirms the change.

The integration refreshes four Clockify endpoints every thirty minutes (8 requests/hour). Clockify's free plan limit is 30 API-key requests per hour, including other integrations and automations using the same key.

## API key security

The API key is stored in Home Assistant's config entry and sent in the `X-Api-Key` header to the selected official Clockify API host. Choose the server region used by your workspace. Use a dedicated Clockify API key and revoke it in Clockify if it is no longer needed.

## Contributing

Commit messages must follow Conventional Commits, for example `feat(sensor): add weekly total` or `fix: handle empty response`. Messages beginning with `WIP` (case-insensitive, followed by a space, colon, or end of message) are allowed and do not trigger a version bump.

On pushes to `main`, GitHub Actions checks commits since the latest version tag and applies the highest required SemVer bump: `feat` → minor, `fix`/`perf`/`revert` → patch, and `!` or `BREAKING CHANGE:` → major. Other commit types do not change the version. The workflow updates `manifest.json` and `CHANGELOG.md`, then commits and tags the release. It needs write access to `main`; if `main` is protected by a repository ruleset, add the GitHub Actions app as a bypass actor for this release workflow.

The repository is initialized on `main` and has the initial `v0.4.1` tag. To enable the local commit hook in a clone, run `git config core.hooksPath .githooks`.

## AI assistance

AI tools assisted with portions of this integration's development. The maintainer is responsible for reviewing and maintaining the published code. AI assistance does not imply endorsement by Clockify or Home Assistant.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
