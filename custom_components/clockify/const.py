from datetime import timedelta

DOMAIN = "clockify"
CONF_API_KEY = "api_key"
CONF_WORKSPACE_ID = "workspace_id"
CONF_WORKSPACE_NAME = "workspace_name"
CONF_API_HOST = "api_host"
API_HOSTS = {
    "api.clockify.me": "Global",
    "euc1.clockify.me": "EU (Germany)",
    "use2.clockify.me": "USA",
    "euw2.clockify.me": "UK",
    "apse2.clockify.me": "Australia",
    "developer.clockify.me": "Developer",
}
API_BASE_TEMPLATE = "https://{host}/api/v1"
UPDATE_INTERVAL = timedelta(minutes=30)
