"""App declaration for netbox_golden_config."""

from importlib import metadata

from django.db.models.signals import post_migrate
from netbox.plugins import PluginConfig
from extras.plugins import get_plugin_config # NetBox specific import for settings

# __version__ = metadata.version(__name__) # metadata may not work the same way, set manually or via package build
__version__ = "1.0.0" # Example version

class GoldenConfig(PluginConfig):
    """App configuration for the netbox_golden_config app."""

    name = "netbox_golden_config"
    verbose_name = "Golden Configuration"
    version = __version__
    author = "Network to Code, LLC (Adapted for NetBox)"
    author_email = "opensource@networktocode.com"
    description = "NetBox Plugin that embraces NetDevOps and automates configuration backups, performs configuration compliance, generates intended configurations, and has config remediation and deployment features. Includes native Git integration and gives users the flexibility to mix and match the supported features."
    base_url = "golden-config"
    # docs_view_name = "plugins:netbox_golden_config:docs" # Adapt if docs are hosted differently
    required_settings = [] # Define mandatory settings if any
    default_settings = {
        "enable_backup": True,
        "enable_compliance": True,
        "enable_intended": True,
        "enable_sotagg": True, # Note: GraphQL/SOTAgg functionality needs review for NetBox
        "enable_postprocessing": False,
        "enable_plan": True,
        "enable_deploy": True,
        "default_deploy_status": "Not Approved", # Ensure this Status exists in NetBox
        "postprocessing_callables": [],
        "postprocessing_subscribed": [],
        "per_feature_bar_width": 0.3,
        "per_feature_width": 13,
        "per_feature_height": 4,
        "get_custom_compliance": None,
        # This is an experimental and undocumented setting that will change in the future!!
        # Use at your own risk!!!!!
        # "_manual_dynamic_group_mgmt": False, # Dynamic Groups replaced
        "jinja_env": {
            "undefined": "jinja2.StrictUndefined",
            "trim_blocks": True,
            "lstrip_blocks": False,
        },
        # NetBox uses PLUGINS_CONFIG directly, Constance is Nautobot specific
        "default_framework": {"all": "napalm"},
        "get_config_framework": {},
        "merge_config_framework": {},
        "replace_config_framework": {},
    }
    # Caching config needs review for NetBox equivalent if desired
    # caching_config = {
    #     "*": None
    # }

    def ready(self):
        """Register custom signals."""
        from .models import ConfigCompliance # pylint: disable=import-outside-toplevel
        from .signals import ( # pylint: disable=import-outside-toplevel
            config_compliance_platform_cleanup,
            post_migrate_create_job_button, # Job Buttons need adaptation for NetBox UI
            post_migrate_create_statuses,
        )

        # Use standard Django post_migrate signal
        post_migrate.connect(post_migrate_create_statuses, sender=self)
        post_migrate.connect(post_migrate_create_job_button, sender=self) # Needs review for NetBox Job Buttons
        post_migrate.connect(config_compliance_platform_cleanup, sender=ConfigCompliance)

        super().ready()

# Instantiate the plugin config
config = GoldenConfig

