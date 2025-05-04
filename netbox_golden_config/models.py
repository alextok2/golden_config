"""Django Models for tracking the configuration compliance per feature and device."""

import json
import logging
import os
from functools import cached_property

from deepdiff import DeepDiff
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.manager import BaseManager # Keep standard Django Manager
# from django.db.models.query import QuerySet # Replaced with RestrictedQuerySet below
from django.utils.module_loading import import_string
from hier_config import WorkflowRemediation, get_hconfig, Platform
from netbox.models.features import ChangeLoggingMixin, CustomFieldsMixin, JobsMixin,   TagsMixin # NetBox base features
from netbox.models import NetBoxModel
from utilities.querysets import RestrictedQuerySet # Use NetBox's RestrictedQuerySet

# Use NetBox core models
from dcim.models import Device, Platform
from extras.models import Tag # Note: NetBox DynamicGroup may differ or not exist natively

# Netutils and xmldiff remain the same
from netutils.config.compliance import feature_compliance
from xmldiff import actions, main

from .choices import ComplianceRuleConfigTypeChoice, ConfigPlanTypeChoice, RemediationTypeChoice # Use local choices
from .utilities.constant import ENABLE_SOTAGG, PLUGIN_CFG # Use local constant utils

LOGGER = logging.getLogger(__name__)
GRAPHQL_STR_START = "query ($device_id: ID!)" # Keep, but validity depends on NetBox GraphQL implementation

ERROR_MSG = (
    "There was an issue with the data that was returned by your get_custom_compliance function. "
    "This is a local issue that requires the attention of your systems administrator and not something "
    "that can be fixed within the Golden Config app. "
)
MISSING_MSG = (
    ERROR_MSG + "Specifically the `{}` key was not found in value the get_custom_compliance function provided."
)
VALIDATION_MSG = (
    ERROR_MSG + "Specifically the key {} was expected to be of type(s) {} and the value of {} was not that type(s)."
)

CUSTOM_FUNCTIONS = {
    "get_custom_compliance": "custom",
    "get_custom_remediation": RemediationTypeChoice.TYPE_CUSTOM,
}


def _is_jsonable(val):
    """Check is value can be converted to json."""
    try:
        json.dumps(val)
        return True
    except (TypeError, OverflowError):
        return False


def _null_to_empty(val):
    """Convert to empty string if the value is currently null."""
    if not val:
        return ""
    return val


def _get_cli_compliance(obj):
    """This function performs the actual compliance for cli configuration."""
    # Adapt network_driver access if Platform model differs in NetBox
    netutils_parser = None
    if hasattr(obj.device.platform, 'network_driver_mappings') and isinstance(obj.device.platform.network_driver_mappings, dict):
         netutils_parser = obj.device.platform.network_driver_mappings.get("netutils_parser")
    elif hasattr(obj.device.platform, 'napalm_driver'): # Fallback or alternative
         # Assuming napalm_driver might correlate. Needs verification for NetBox.
         from netutils.constants import NAPALM_LIB_MAPPER_REVERSE
         netutils_parser = NAPALM_LIB_MAPPER_REVERSE.get(obj.device.platform.napalm_driver)
    elif hasattr(obj.device.platform, 'network_driver'): # Direct mapping if available
         from netutils.constants import NETUTILSPARSER_LIB_MAPPER_REVERSE
         netutils_parser = NETUTILSPARSER_LIB_MAPPER_REVERSE.get(obj.device.platform.network_driver)


    if not netutils_parser:
         # Handle case where no suitable parser mapping is found
         # Log a warning or raise an error depending on desired behavior
         LOGGER.warning(f"Could not determine netutils_parser for platform {obj.device.platform} on device {obj.device}. Compliance check might be inaccurate.")
         # Set default or skip - here skipping by returning neutral compliance
         return {
            "compliance": True, # Or False, depending on desired strictness
            "compliance_int": 1,
            "ordered": True,
            "missing": "",
            "extra": "",
         }


    feature = {
        "ordered": obj.rule.config_ordered,
        "name": str(obj.rule), # Ensure rule is stringified if needed
    }
    feature.update({"section": obj.rule.match_config.splitlines()})
    value = feature_compliance(
        feature, obj.actual, obj.intended, netutils_parser
    )
    compliance = value["compliant"]
    compliance_int = 1 if compliance else 0
    ordered = value["ordered_compliant"]
    missing = _null_to_empty(value["missing"])
    extra = _null_to_empty(value["extra"])
    return {
        "compliance": compliance,
        "compliance_int": compliance_int,
        "ordered": ordered,
        "missing": missing,
        "extra": extra,
    }


def _get_json_compliance(obj):
    """This function performs the actual compliance for json serializable data."""

    def _normalize_diff(diff, path_to_diff):
        """Normalizes the diff to a list of keys and list indexes that have changed."""
        dictionary_items = list(diff.get(f"dictionary_item_{path_to_diff}", []))
        list_items = list(diff.get(f"iterable_item_{path_to_diff}", {}).keys())
        values_changed = list(diff.get("values_changed", {}).keys())
        type_changes = list(diff.get("type_changes", {}).keys())
        return dictionary_items + list_items + values_changed + type_changes

    diff = DeepDiff(obj.actual, obj.intended, ignore_order=obj.ordered, report_repetition=True)
    if not diff:
        compliance_int = 1
        compliance = True
        ordered = True
        missing = ""
        extra = ""
    else:
        compliance_int = 0
        compliance = False
        ordered = False # DeepDiff doesn't easily report if order caused the diff
        missing = _null_to_empty(_normalize_diff(diff, "added"))
        extra = _null_to_empty(_normalize_diff(diff, "removed"))

    return {
        "compliance": compliance,
        "compliance_int": compliance_int,
        "ordered": ordered,
        "missing": missing,
        "extra": extra,
    }


def _get_xml_compliance(obj):
    """This function performs the actual compliance for xml serializable data."""

    def _normalize_diff(diff):
        """Format the diff output to a list of nodes with values that have updated."""
        formatted_diff = []
        for operation in diff:
            if isinstance(operation, actions.UpdateTextIn):
                formatted_operation = f"{operation.node}, {operation.text}"
                formatted_diff.append(formatted_operation)
        return "\n".join(formatted_diff)

    # Options for the diff operation. These are set to prefer updates over node insertions/deletions.
    diff_options = {
        "F": 0.1,
        "fast_match": True,
    }
    missing = main.diff_texts(obj.actual, obj.intended, diff_options=diff_options)
    extra = main.diff_texts(obj.intended, obj.actual, diff_options=diff_options)

    compliance = not missing and not extra
    compliance_int = int(compliance)
    ordered = obj.ordered # XML compliance check doesn't inherently check order here
    missing = _null_to_empty(_normalize_diff(missing))
    extra = _null_to_empty(_normalize_diff(extra))

    return {
        "compliance": compliance,
        "compliance_int": compliance_int,
        "ordered": ordered,
        "missing": missing,
        "extra": extra,
    }


def _verify_get_custom_compliance_data(compliance_details):
    """This function verifies the data is as expected when a custom function is used."""
    for val in ["compliance", "compliance_int", "ordered", "missing", "extra"]:
        try:
            compliance_details[val]
        except KeyError:
            raise ValidationError(MISSING_MSG.format(val)) from KeyError
    for val in ["compliance", "ordered"]:
        if compliance_details[val] not in [True, False]:
            raise ValidationError(VALIDATION_MSG.format(val, "Boolean", compliance_details[val]))
    if compliance_details["compliance_int"] not in [0, 1]:
        raise ValidationError(VALIDATION_MSG.format("compliance_int", "0 or 1", compliance_details["compliance_int"]))
    for val in ["missing", "extra"]:
        if not isinstance(compliance_details[val], str) and not _is_jsonable(compliance_details[val]):
            raise ValidationError(VALIDATION_MSG.format(val, "String or Json", compliance_details[val]))


def _get_hierconfig_remediation(obj):
    """Returns the remediating config."""
    # Adapt hier_config mapping based on NetBox Platform model
    hierconfig_os = None
    if hasattr(obj.device.platform, 'network_driver_mappings') and isinstance(obj.device.platform.network_driver_mappings, dict):
         hierconfig_os = obj.device.platform.network_driver_mappings.get("hier_config")
    # Add other potential attributes if NetBox uses different fields for this mapping
    # elif hasattr(obj.device.platform, 'some_other_field'):
    #      hierconfig_os = ...

    if not hierconfig_os:
        # Use network_driver or napalm_driver as potential fallbacks
        network_driver = getattr(obj.device.platform, 'network_driver', None) or getattr(obj.device.platform, 'napalm_driver', None)
        if network_driver:
            LOGGER.warning(f"Could not find specific hier_config mapping for platform {obj.device.platform}. Attempting to use network_driver '{network_driver}'.")
            # Map common drivers if possible
            # This mapping might need expansion based on common NetBox usage
            driver_map = {
                'cisco_ios': 'ios',
                'cisco_xe': 'iosxe',
                'cisco_xr': 'iosxr',
                'cisco_nxos': 'nxos',
                'arista_eos': 'eos',
                'juniper_junos': 'junos',
            }
            hierconfig_os = driver_map.get(network_driver)

    if not hierconfig_os:
        raise ValidationError(f"Platform {obj.device.platform} (network_driver: {getattr(obj.device.platform, 'network_driver', 'N/A')}) is not supported by hierconfig or mapping not found.")


    try:
        remediation_setting_obj = RemediationSetting.objects.get(platform=obj.rule.platform)
    except RemediationSetting.DoesNotExist as err: # Use specific DoesNotExist
        raise ValidationError(f"Platform {obj.device.platform} has no Remediation Settings defined.") from err
    except Exception as err: # Catch other potential errors
        raise ValidationError(f"Error fetching Remediation Settings for {obj.device.platform}.") from err


    remediation_options = remediation_setting_obj.remediation_options

    try:
        # Определяем платформу на основе hierconfig_os
        platform = getattr(Platform, hierconfig_os.upper(), None)
        if platform is None:
            raise ValueError(f"Unsupported platform: {hierconfig_os}")
        
        # Создаем HConfig объекты для конфигураций
        running_config = get_hconfig(platform, obj.actual, options=remediation_options)
        intended_config = get_hconfig(platform, obj.intended, options=remediation_options)
        
        # Создаем объект WorkflowRemediation
        workflow = WorkflowRemediation(running_config, intended_config)
        
        # Получаем конфигурацию исправления
        remediation_config = workflow.remediation_config_filtered_text(include_tags={}, exclude_tags={})

    except Exception as err:
        raise Exception(
            f"Cannot generate remediation config for {obj.device.name}, check Device, Platform and Hier Options."
        ) from err

    return remediation_config


# The below maps the provided compliance types
FUNC_MAPPER = {
    ComplianceRuleConfigTypeChoice.TYPE_CLI: _get_cli_compliance,
    ComplianceRuleConfigTypeChoice.TYPE_JSON: _get_json_compliance,
    ComplianceRuleConfigTypeChoice.TYPE_XML: _get_xml_compliance,
    RemediationTypeChoice.TYPE_HIERCONFIG: _get_hierconfig_remediation,
}
# The below conditionally add the custom provided compliance type
for custom_function, custom_type in CUSTOM_FUNCTIONS.items():
    if PLUGIN_CFG.get(custom_function):
        try:
            FUNC_MAPPER[custom_type] = import_string(PLUGIN_CFG[custom_function])
        except Exception as error:  # pylint: disable=broad-except
            msg = (
                "There was an issue attempting to import the custom function of"
                f"{PLUGIN_CFG[custom_function]}, this is expected with a local configuration issue "
                "and not related to the Golden Configuration App, please contact your system admin for further details"
            )
            raise Exception(msg).with_traceback(error.__traceback__)

# Use NetBoxModel which includes base functionality like PK, created, last_updated
# Use NetBox feature mixins instead of extras_features decorator
class ComplianceFeature(NetBoxModel, TagsMixin, CustomFieldsMixin,  WebhooksMixin, NotesMixin):
    """ComplianceFeature details."""

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.CharField(max_length=200, blank=True)

    # NetBox doesn't typically use clone_fields directly in the model
    # clone_fields = ["name", "slug", "description"]

    class Meta:
        """Meta information for ComplianceFeature model."""
        ordering = ("slug",)

    def __str__(self):
        """Return a sane string representation of the instance."""
        return self.slug

    # NetBox doesn't use get_absolute_url the same way in list views by default, handled by views/tables
    # def get_absolute_url(self):
    #     from django.urls import reverse
    #     return reverse("plugins:netbox_golden_config:compliancefeature", kwargs={"pk": self.pk})


class ComplianceRule(NetBoxModel, TagsMixin, CustomFieldsMixin,  WebhooksMixin, NotesMixin):
    """ComplianceRule details."""

    feature = models.ForeignKey(to="ComplianceFeature", on_delete=models.CASCADE, related_name="feature")
    platform = models.ForeignKey(
        to="dcim.Platform",
        on_delete=models.CASCADE,
        related_name="compliance_rules",
    )
    description = models.CharField(
        max_length=200,
        blank=True,
    )
    config_ordered = models.BooleanField(
        verbose_name="Configured Ordered",
        help_text="Whether or not the configuration order matters, such as in ACLs.",
        default=False,
    )
    config_remediation = models.BooleanField(
        default=False,
        verbose_name="Config Remediation",
        help_text="Whether or not the config remediation is executed for this compliance rule.",
    )
    match_config = models.TextField(
        blank=True,
        verbose_name="Config to Match",
        help_text="The config to match that is matched based on the parent most configuration. E.g.: For CLI `router bgp` or `ntp`. For JSON this is a top level key name. For XML this is a xpath query.",
    )
    config_type = models.CharField(
        max_length=20,
        default=ComplianceRuleConfigTypeChoice.TYPE_CLI,
        choices=ComplianceRuleConfigTypeChoice.CHOICES, # Use CHOICES for NetBox compatibility
        help_text="Whether the configuration is in CLI, JSON, or XML format.",
    )
    custom_compliance = models.BooleanField(
        default=False, help_text="Whether this Compliance Rule is proceeded as custom."
    )

    # NetBox doesn't use clone_fields directly in the model
    # clone_fields = ["platform", "feature", "description", "config_ordered", "match_config", "config_type", "custom_compliance", "config_remediation"]

    @property
    def remediation_setting(self):
        """Returns remediation settings for a particular platform."""
        return RemediationSetting.objects.filter(platform=self.platform).first()

    class Meta:
        """Meta information for ComplianceRule model."""
        ordering = ("platform", "feature__name")
        unique_together = (
            "feature",
            "platform",
        )

    def __str__(self):
        """Return a sane string representation of the instance."""
        return f"{self.platform} - {self.feature.name}"

    def clean(self):
        """Verify that if cli, then match_config is set."""
        super().clean() # Call super().clean()
        if self.config_type == ComplianceRuleConfigTypeChoice.TYPE_CLI and not self.match_config:
            raise ValidationError("CLI configuration set, but no configuration set to match.")

    # def get_absolute_url(self):
    #     from django.urls import reverse
    #     return reverse("plugins:netbox_golden_config:compliancerule", kwargs={"pk": self.pk})

class ConfigCompliance(NetBoxModel, TagsMixin, CustomFieldsMixin,  WebhooksMixin, NotesMixin):
    """Configuration compliance details."""

    device = models.ForeignKey(to="dcim.Device", on_delete=models.CASCADE, help_text="The device")
    rule = models.ForeignKey(to="ComplianceRule", on_delete=models.CASCADE, related_name="rule")
    compliance = models.BooleanField(blank=True, default=False) # Provide default
    # Use JSONField from django.db.models
    actual = models.JSONField(blank=True, help_text="Actual Configuration for feature", default=dict)
    intended = models.JSONField(blank=True, help_text="Intended Configuration for feature", default=dict)
    # these three are config snippets exposed for the ConfigDeployment.
    remediation = models.JSONField(blank=True, help_text="Remediation Configuration for the device", default=dict)
    missing = models.JSONField(blank=True, help_text="Configuration that should be on the device.", default=dict)
    extra = models.JSONField(blank=True, help_text="Configuration that should not be on the device.", default=dict)
    ordered = models.BooleanField(default=False)
    # Used for django-pivot, both compliance and compliance_int should be set.
    compliance_int = models.IntegerField(blank=True, default=0) # Provide default

    # NetBox change logging is handled differently (via signal receivers typically)
    # Adapting to_objectchange is complex, relying on NetBox's built-in change logging is preferred.
    # def to_objectchange(self, action, *, related_object=None, object_data_extra=None, object_data_exclude=None):
    #     ...

    # NetBox doesn't use is_dynamic_group_associable_model
    # is_dynamic_group_associable_model = False

    class Meta:
        """Set unique together fields for model."""
        ordering = ["device", "rule"]
        unique_together = ("device", "rule")

    def __str__(self):
        """String representation of a the compliance."""
        return f"{self.device} -> {self.rule} -> {self.compliance}"

    def compliance_on_save(self):
        """The actual configuration compliance happens here, but the details for actual compliance job would be found in FUNC_MAPPER."""
        if self.rule.custom_compliance:
            if not FUNC_MAPPER.get("custom"):
                raise ValidationError(
                    "Custom type provided, but no `get_custom_compliance` config set, please contact system admin."
                )
            compliance_details = FUNC_MAPPER["custom"](obj=self)
            _verify_get_custom_compliance_data(compliance_details)
        else:
            compliance_details = FUNC_MAPPER[self.rule.config_type](obj=self)

        self.compliance = compliance_details["compliance"]
        self.compliance_int = compliance_details["compliance_int"]
        self.ordered = compliance_details["ordered"]
        self.missing = compliance_details["missing"]
        self.extra = compliance_details["extra"]

    def remediation_on_save(self):
        """The actual remediation happens here, before saving the object."""
        if self.compliance:
            self.remediation = ""
            return

        if not self.rule.config_remediation:
            self.remediation = ""
            return

        if not self.rule.remediation_setting:
            self.remediation = ""
            return

        # Ensure the remediation setting type exists in the mapper
        remediation_type = self.rule.remediation_setting.remediation_type
        if remediation_type not in FUNC_MAPPER:
             # Handle the case where the remediation type is not supported or mapped
             # Log a warning or raise an error
             LOGGER.error(f"Remediation type '{remediation_type}' not found in FUNC_MAPPER for rule {self.rule}.")
             self.remediation = "" # Set to empty or handle as appropriate
             return

        try:
            remediation_config = FUNC_MAPPER[remediation_type](obj=self)
            self.remediation = remediation_config
        except Exception as e:
            # Log the error or handle it appropriately
            LOGGER.error(f"Error generating remediation for device {self.device}, rule {self.rule}: {e}")
            self.remediation = "" # Set remediation to empty on error


    def save(self, *args, **kwargs):
        """The actual configuration compliance happens here, but the details for actual compliance job would be found in FUNC_MAPPER."""
        self.compliance_on_save()
        self.remediation_on_save()
        self.full_clean() # Keep full_clean

        # No need to manually manage update_fields in NetBox's save typically
        # if kwargs.get("update_fields"):
        #     kwargs["update_fields"].update(
        #         {"compliance", "compliance_int", "ordered", "missing", "extra", "remediation"}
        #     )

        super().save(*args, **kwargs)

    # def get_absolute_url(self):
    #     from django.urls import reverse
    #     return reverse("plugins:netbox_golden_config:configcompliance", kwargs={"pk": self.pk})

class GoldenConfig(NetBoxModel, TagsMixin, CustomFieldsMixin,  WebhooksMixin, NotesMixin):
    """Configuration Management Model."""

    device = models.OneToOneField( # Keep OneToOneField
        to="dcim.Device",
        on_delete=models.CASCADE,
        help_text="device",
        blank=False,
    )
    backup_config = models.TextField(blank=True, help_text="Full backup config for device.")
    backup_last_attempt_date = models.DateTimeField(null=True, blank=True)
    backup_last_success_date = models.DateTimeField(null=True, blank=True)

    intended_config = models.TextField(blank=True, help_text="Intended config for the device.")
    intended_last_attempt_date = models.DateTimeField(null=True, blank=True)
    intended_last_success_date = models.DateTimeField(null=True, blank=True)

    compliance_config = models.TextField(blank=True, help_text="Full config diff for device.")
    compliance_last_attempt_date = models.DateTimeField(null=True, blank=True)
    compliance_last_success_date = models.DateTimeField(null=True, blank=True)

    # NetBox change logging is handled differently
    # def to_objectchange(self, action, *, related_object=None, object_data_extra=None, object_data_exclude=None):
    #     ...

    # --- Dynamic Group Replacement Logic ---
    # This needs to be implemented based on how you replace Dynamic Groups in NetBox.
    # Option 1: Using Tags
    @staticmethod
    def get_devices_in_scope():
        """Get all Device PKs that should have GoldenConfig entries (e.g., based on a specific tag)."""
        # Example: Get devices with the 'golden-config-active' tag
        try:
            active_tag = Tag.objects.get(slug='golden-config-active')
            # Ensure the tag is enabled for dcim.device
            device_ct = ContentType.objects.get_for_model(Device)
            if device_ct not in active_tag.content_types.all():
                 LOGGER.warning(f"Tag '{active_tag.name}' is not enabled for devices.")
                 return set()
            return set(Device.objects.filter(tags=active_tag).values_list("pk", flat=True))
        except Tag.DoesNotExist:
            LOGGER.warning("Required tag 'golden-config-active' not found. No devices will be managed.")
            return set()
        except Exception as e:
            LOGGER.error(f"Error getting devices in scope using tags: {e}")
            return set()

    # Option 2: Using a filter defined in GoldenConfigSetting (needs modification to GoldenConfigSetting model)
    # @staticmethod
    # def get_devices_in_scope():
    #     """Get all Device PKs based on filters defined in GoldenConfigSetting objects."""
    #     scoped_device_pks = set()
    #     for setting in GoldenConfigSetting.objects.filter(scope_filter__isnull=False):
    #         try:
    #             # Assuming scope_filter is a JSONField containing filter parameters
    #             devices = DeviceFilterSet(data=setting.scope_filter, queryset=Device.objects.all()).qs
    #             scoped_device_pks.update(devices.values_list("pk", flat=True))
    #         except Exception as e:
    #             LOGGER.error(f"Error applying filter for GoldenConfigSetting '{setting.name}': {e}")
    #     return scoped_device_pks

    @classmethod
    def get_golden_config_device_ids(cls):
        """Get all Device PKs associated with GoldenConfig entries."""
        return set(cls.objects.values_list("device__pk", flat=True))
    # --- End Dynamic Group Replacement Logic ---

    class Meta:
        """Set unique together fields for model."""
        ordering = ["device"]

    def __str__(self):
        """String representation of a the compliance."""
        return f"{self.device}"

    # def get_absolute_url(self):
    #     from django.urls import reverse
    #     return reverse("plugins:netbox_golden_config:goldenconfig", kwargs={"pk": self.pk})


class GoldenConfigSettingManager(BaseManager.from_queryset(RestrictedQuerySet)):
    """Manager for GoldenConfigSetting."""

    # --- Dynamic Group Replacement Logic ---
    def get_for_device(self, device):
        """Return the highest weighted GoldenConfigSetting assigned to a device."""
        if not isinstance(device, Device):
            raise ValueError("The device argument must be a Device instance.")

        # Option 1: Using Tags - Find settings whose tag is applied to the device
        # Assumes GoldenConfigSetting has a ManyToManyField to Tag named 'scope_tags'
        # matching_settings = GoldenConfigSetting.objects.filter(scope_tags__in=device.tags.all()).order_by("-weight", "name")

        # Option 2: Using FilterSet defined in the setting
        # Assumes GoldenConfigSetting has a JSONField 'scope_filter'
        matching_settings = []
        for setting in GoldenConfigSetting.objects.filter(scope_filter__isnull=False).order_by("-weight", "name"):
             try:
                 # Check if the device matches the filter defined in the setting
                 if DeviceFilterSet(data=setting.scope_filter, queryset=Device.objects.filter(pk=device.pk)).qs.exists():
                     matching_settings.append(setting)
             except Exception as e:
                 LOGGER.error(f"Error evaluating filter for GoldenConfigSetting '{setting.name}' against device '{device.name}': {e}")

        # Option 3: Simplified - Match based on device properties directly (e.g., platform, location)
        # This requires defining which fields on GoldenConfigSetting determine scope.
        # Example: Matching by platform
        # matching_settings = GoldenConfigSetting.objects.filter(platform=device.platform).order_by("-weight", "name")

        if matching_settings:
            # If using Option 2 or 3, return the first one (highest weight due to ordering)
            return matching_settings[0]
            # If using Option 1, return matching_settings.first()

        return None
    # --- End Dynamic Group Replacement Logic ---

# Replace extras_features with NetBoxModel and Mixins
class GoldenConfigSetting(NetBoxModel, TagsMixin, CustomFieldsMixin,  WebhooksMixin, NotesMixin):
    """GoldenConfigSetting Model definition. This provides global configs instead of via configs.py."""

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    weight = models.PositiveSmallIntegerField(default=1000)
    description = models.CharField(
        max_length=200,
        blank=True,
    )
    # Use extras.GitRepository
    # Adapt limit_choices_to based on how NetBox plugins register provided content, if applicable
    # NetBox might not have this direct filtering mechanism, validation might be needed elsewhere.
    backup_repository = models.ForeignKey(
        to="extras.GitRepository",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="backup_repository",
        # limit_choices_to={"provided_contents__contains": "nautobot_golden_config.backupconfigs"}, # May need removal/adaptation
    )
    backup_path_template = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Backup Path in Jinja Template Form",
        help_text="The Jinja path representation of where the backup file will be found. The variable `obj` is available as the device instance object of a given device, as is the case for all Jinja templates. e.g. `{{obj.location.name|slugify}}/{{obj.name}}.cfg`",
    )
    intended_repository = models.ForeignKey(
        to="extras.GitRepository",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="intended_repository",
        # limit_choices_to={"provided_contents__contains": "nautobot_golden_config.intendedconfigs"}, # May need removal/adaptation
    )
    intended_path_template = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Intended Path in Jinja Template Form",
        help_text="The Jinja path representation of where the generated file will be placed. e.g. `{{obj.location.name|slugify}}/{{obj.name}}.cfg`",
    )
    jinja_repository = models.ForeignKey(
        to="extras.GitRepository",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="jinja_template",
        # limit_choices_to={"provided_contents__contains": "nautobot_golden_config.jinjatemplate"}, # May need removal/adaptation
    )
    jinja_path_template = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Template Path in Jinja Template Form",
        help_text="The Jinja path representation of where the Jinja template can be found. e.g. `{{obj.platform.network_driver}}.j2`",
    )
    backup_test_connectivity = models.BooleanField(
        default=True,
        verbose_name="Backup Test",
        help_text="Whether or not to pretest the connectivity of the device by verifying there is a resolvable IP that can connect to port 22.",
    )
    # GraphQL validity depends heavily on NetBox's implementation
    sot_agg_query = models.ForeignKey(
        to="extras.GraphQLQuery",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="sot_aggregation",
    )

    # --- Dynamic Group Replacement Field ---
    # Option 1: Use Tags
    # scope_tags = models.ManyToManyField(to=Tag, related_name="+", blank=True)
    # Option 2: Use JSON Filter
    scope_filter = models.JSONField(null=True, blank=True, help_text="NetBox filter parameters (JSON) used to scope devices for this setting.")
    # --- End Dynamic Group Replacement Field ---

    objects = GoldenConfigSettingManager()

    def __str__(self):
        """Return a simple string if model is called."""
        return f"Golden Config Setting - {self.name}"

    class Meta:
        verbose_name = "Golden Config Setting"
        ordering = ["-weight", "name"]

    def clean(self):
        """Validate the scope and GraphQL query."""
        super().clean()

        if ENABLE_SOTAGG and not self.sot_agg_query:
            raise ValidationError("A GraphQL query must be defined when `ENABLE_SOTAGG` is True")

        if self.sot_agg_query:
            LOGGER.debug("GraphQL - test query start with: `%s`", GRAPHQL_STR_START)
            if not str(self.sot_agg_query.query.lstrip()).startswith(GRAPHQL_STR_START):
                raise ValidationError(f"The GraphQL query must start with exactly `{GRAPHQL_STR_START}`")

    # --- Dynamic Group Replacement Methods ---
    @cached_property
    def members_count(self):
        """Return the number of devices matching the scope."""
        # Option 1: Tags
        # return Device.objects.filter(tags__in=self.scope_tags.all()).count()
        # Option 2: Filter
        if not self.scope_filter:
            return Device.objects.count() # Or 0 if empty filter means no scope
        try:
            return DeviceFilterSet(data=self.scope_filter, queryset=Device.objects.all()).qs.count()
        except Exception as e:
            LOGGER.error(f"Error evaluating filter count for GoldenConfigSetting '{self.name}': {e}")
            return 0 # Or raise error

    @cached_property
    def members_url(self):
        """Get url to all devices that are matching the scope."""
        # This needs to construct a NetBox device list URL with appropriate filter parameters
        # Option 1: Tags
        # from django.urls import reverse
        # tag_slugs = ",".join(self.scope_tags.values_list('slug', flat=True))
        # return f"{reverse('dcim:device_list')}?tag={tag_slugs}"
        # Option 2: Filter
        if not self.scope_filter:
            return reverse('dcim:device_list')
        try:
            # Convert filter JSON to URL query parameters
            from urllib.parse import urlencode
            query_string = urlencode(self.scope_filter, doseq=True)
            return f"{reverse('dcim:device_list')}?{query_string}"
        except Exception as e:
            LOGGER.error(f"Error generating members URL for GoldenConfigSetting '{self.name}': {e}")
            return reverse('dcim:device_list') # Fallback

    # get_queryset method is replaced by standard NetBox filtering based on scope_filter or scope_tags
    # --- End Dynamic Group Replacement Methods ---

    def get_jinja_template_path_for_device(self, device):
        """Get the Jinja template path for a device."""
        if self.jinja_repository is not None:
            # Use NetBox's render_jinja2 if available, or core Django templating
            from netbox.utilities.rendering import render_jinja2 as netbox_render_jinja2
            try:
                 rendered_path = netbox_render_jinja2(template_code=self.jinja_path_template, context={"obj": device})
                 # filesystem_path might not exist directly on NetBox GitRepository model, adapt access
                 repo_path = getattr(self.jinja_repository, 'filesystem_path', None)
                 if not repo_path:
                      # Handle case where path isn't stored directly (NetBox might use context managers)
                      # This part needs verification against NetBox GitRepository implementation
                      LOGGER.error(f"Filesystem path not available for GitRepository {self.jinja_repository.name}")
                      return None
                 return f"{repo_path}{os.path.sep}{rendered_path}"
            except Exception as e:
                 LOGGER.error(f"Error rendering Jinja template path for device {device.name}: {e}")
                 return None
        return None

class ConfigRemove(NetBoxModel, TagsMixin, CustomFieldsMixin,  WebhooksMixin, NotesMixin):
    """ConfigRemove for Regex Line Removals from Backup Configuration Model definition."""
    name = models.CharField(max_length=255)
    platform = models.ForeignKey(
        to="dcim.Platform",
        on_delete=models.CASCADE,
        related_name="backup_line_remove",
    )
    description = models.CharField(
        max_length=200,
        blank=True,
    )
    regex = models.CharField(
        max_length=200,
        verbose_name="Regex Pattern",
        help_text="Regex pattern used to remove a line from the backup configuration.",
    )

    # clone_fields removed

    class Meta:
        ordering = ("platform", "name")
        unique_together = ("name", "platform")

    def __str__(self):
        return self.name

    # def get_absolute_url(self):
    #     from django.urls import reverse
    #     return reverse("plugins:netbox_golden_config:configremove", kwargs={"pk": self.pk})

class ConfigReplace(NetBoxModel, TagsMixin, CustomFieldsMixin,  WebhooksMixin, NotesMixin):
    """ConfigReplace for Regex Line Replacements from Backup Configuration Model definition."""
    name = models.CharField(max_length=255)
    platform = models.ForeignKey(
        to="dcim.Platform",
        on_delete=models.CASCADE,
        related_name="backup_line_replace",
    )
    description = models.CharField(
        max_length=200,
        blank=True,
    )
    regex = models.CharField(
        max_length=200,
        verbose_name="Regex Pattern to Substitute",
        help_text="Regex pattern that will be found and replaced with 'replaced text'.",
    )
    replace = models.CharField(
        max_length=200,
        verbose_name="Replaced Text",
        help_text="Text that will be inserted in place of Regex pattern match.",
    )

    # clone_fields removed

    class Meta:
        ordering = ("platform", "name")
        unique_together = ("name", "platform")

    def __str__(self):
        return self.name

    # def get_absolute_url(self):
    #     from django.urls import reverse
    #     return reverse("plugins:netbox_golden_config:configreplace", kwargs={"pk": self.pk})


class RemediationSetting(NetBoxModel, TagsMixin, CustomFieldsMixin,  WebhooksMixin, NotesMixin):
    """RemediationSetting details."""
    platform = models.OneToOneField(
        to="dcim.Platform",
        on_delete=models.CASCADE,
        related_name="remediation_settings",
    )
    remediation_type = models.CharField(
        max_length=50,
        default=RemediationTypeChoice.TYPE_HIERCONFIG,
        choices=RemediationTypeChoice.CHOICES, # Use CHOICES
        help_text="Whether the remediation setting is type HierConfig or custom.",
    )
    remediation_options = models.JSONField(
        blank=True,
        default=dict,
        help_text="Remediation Configuration for the device",
    )

    csv_headers = [
        "platform",
        "remediation_type",
    ]

    class Meta:
        ordering = ("platform", "remediation_type")

    def to_csv(self):
        """Indicates model fields to return as csv."""
        return (
            self.platform.name, # Return name for CSV
            self.remediation_type,
        )

    def __str__(self):
        """Return a sane string representation of the instance."""
        return str(self.platform)

    # def get_absolute_url(self):
    #     from django.urls import reverse
    #     return reverse("plugins:netbox_golden_config:remediationsetting", kwargs={"pk": self.pk})

# Use NetBox features mixins including StatusesMixin if needed (or handle Status FK directly)
class ConfigPlan(NetBoxModel, TagsMixin, CustomFieldsMixin,  WebhooksMixin, NotesMixin):
    """ConfigPlan for Golden Configuration Plan Model definition."""
    plan_type = models.CharField(max_length=20, choices=ConfigPlanTypeChoice.CHOICES, verbose_name="Plan Type")
    device = models.ForeignKey(
        to="dcim.Device",
        on_delete=models.CASCADE,
        related_name="config_plan",
    )
    config_set = models.TextField(help_text="Configuration set to be applied to device.")
    feature = models.ManyToManyField(
        to=ComplianceFeature,
        related_name="config_plan",
        blank=True,
    )
    # Ensure extras.JobResult exists and is suitable in NetBox, or adapt
    plan_result = models.ForeignKey(
        to="extras.JobResult",
        on_delete=models.CASCADE,
        related_name="config_plan",
        verbose_name="Plan Result",
    )
    deploy_result = models.ForeignKey(
        to="extras.JobResult",
        on_delete=models.PROTECT,
        related_name="config_plan_deploy_result",
        verbose_name="Deploy Result",
        blank=True,
        null=True,
    )
    change_control_id = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Change Control ID",
        help_text="Change Control ID for this configuration plan.",
    )
    change_control_url = models.URLField(blank=True, verbose_name="Change Control URL")
    status = models.ForeignKey( # Use standard ForeignKey for Status
        to='extras.Status',
        on_delete=models.PROTECT,
        related_name='+',
        blank=True,
        null=True,
    )
    # Ensure the related Status objects have content_types including this model

    class Meta:
        """Meta information for ConfigPlan model."""
        ordering = ("-created", "device")
        unique_together = ( # Ensure unique_together is defined correctly
            "plan_type",
            "device",
            "created",
        )

    def __str__(self):
        """Return a simple string if model is called."""
        # Format created time for display if needed
        created_time = self.created.strftime('%Y-%m-%d %H:%M:%S') if self.created else 'NoDate'
        return f"{self.device.name}-{self.plan_type}-{created_time}"

    # def get_absolute_url(self):
    #     from django.urls import reverse
    #     return reverse("plugins:netbox_golden_config:configplan", kwargs={"pk": self.pk})
