# Changelog

## 0.4.1

- Rename the integration to Clockify-HA to distinguish it from the official Clockify product.
- Display duration sensors in hours instead of seconds.

## 0.4.0

- Add Clockify start/stop timer services.
- Add billable and non-billable duration sensors for today and this week.

## 0.3.0

- Add integration sensors for the active and latest entries, with stable IDs for migrating existing automations.
- Read the latest entry using the selected project helper when available.
- Set polling fallback to thirty minutes so webhook operation uses fewer Clockify API requests.
- Retry failed webhook registration hourly while polling remains available.

## 0.2.0

- Add Nabu Casa Cloud webhooks for timer starts, stops, and time-entry updates, retaining periodic polling as fallback.
- Increase the polling interval to ten minutes to reduce Clockify API rate-limit errors.

## 0.1.0

- Initial HACS custom integration with API-key setup, regional Clockify server selection, workspace selection, active timer, and today's tracked time sensors.
