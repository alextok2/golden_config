"""Forms for Device Configuration Backup."""

import json

import django.forms as django_forms
from django.conf import settings
from utilities.forms import BootstrapMixin, DynamicModelChoiceField, DynamicModelMultipleChoiceField, SlugField, TagFilterField # NetBox forms
from utilities.forms.fields import CommentField, DynamicModelChoiceField, DynamicModelMultipleChoiceField, MultipleChoiceField # NetBox specific fields
from utilities.forms.widgets import APISelect, APISelectMultiple, BulkEditNullBooleanSelect, DatePicker, Select2, StaticSelect2, StaticSelect2Multiple # NetBox widgets

# NetBox models
from dcim.models import Device, DeviceType, Location, Manufacturer, Platform, Rack, RackGroup, Site # Use Site
from extras.models import DynamicGroup, GitRepository, GraphQLQuery, JobResult, Role, Status, Tag
from tenancy.models import Tenant, TenantGroup
from packaging import version # Keep packaging

from . import models # Use local models
from .choices import ComplianceRuleConfigTypeChoice, ConfigPlanTypeChoice, RemediationTypeChoice # Use local choices

# Use NetBox's Filter Form base if available and needed, or standard forms + BootstrapMixin
# from utilities.forms import FilterForm as NetBoxFilterForm

class BaseFilterForm(BootstrapMixin, django_forms.Form): # Basic filter form base
    q = django_forms.CharField(required=False, label="Search")


class DeviceRelatedFilterForm(BaseFilterForm):
    """Base FilterForm for below FilterForms."""
    # Adapt fields and widgets for NetBox

    tenant_group = DynamicModelMultipleChoiceField(
        queryset=TenantGroup.objects.all(),
        to_field_name='slug', # Use slug usually in NetBox
        required=False,
        label="Tenant group",
    )
    tenant = DynamicModelMultipleChoiceField(
        queryset=Tenant.objects.all(),
        to_field_name='slug', # Use slug
        required=False,
        query_params={"group": "$tenant_group"},
    )
    # Use Site instead of Location unless nested locations are used
    site = DynamicModelMultipleChoiceField(
        queryset=Site.objects.all(),
        to_field_name='slug', # Use slug
        required=False,
        label="Site",
    )
    location = DynamicModelMultipleChoiceField( # Keep if nested locations are used
        queryset=Location.objects.all(),
        to_field_name='slug', # Use slug
        required=False,
        label="Location",
        query_params={"site": "$site"}, # Filter by site
    )
    rack_group = DynamicModelMultipleChoiceField(
        queryset=RackGroup.objects.all(),
        to_field_name='slug', # Use slug
        required=False,
        label="Rack group",
        query_params={"site": "$site"}, # Filter by site
    )
    rack = DynamicModelMultipleChoiceField(
        queryset=Rack.objects.all(),
        to_field_name='name',
        required=False,
        label="Rack",
        query_params={
            "site": "$site",
            "group": "$rack_group", # Use group instead of group_id
        },
    )
    role = DynamicModelMultipleChoiceField(
        queryset=Role.objects.filter(content_types__model="device"), # Filter roles applicable to devices
        to_field_name='slug', # Use slug
        required=False,
    )
    manufacturer = DynamicModelMultipleChoiceField(
        queryset=Manufacturer.objects.all(),
        to_field_name='slug', # Use slug
        required=False,
        label="Manufacturer"
    )
    device_type = DynamicModelMultipleChoiceField(
        queryset=DeviceType.objects.all(),
        to_field_name='slug', # Use slug
        required=False,
        label="Device Model",
        # display_field="model", # NetBox uses __str__ by default
        query_params={"manufacturer": "$manufacturer"},
    )
    platform = DynamicModelMultipleChoiceField(
        queryset=Platform.objects.all(),
        to_field_name='slug', # Use slug
        required=False,
    )
    device = DynamicModelMultipleChoiceField(
        queryset=Device.objects.all(),
        to_field_name='name',
        required=False,
        label="Device",
    )
    tag = TagFilterField(models.GoldenConfig) # Use NetBox TagFilterField

class GoldenConfigFilterForm(DeviceRelatedFilterForm):
    """Filter Form for GoldenConfig."""
    model = models.GoldenConfig
    field_order = [
        "q",
        "tenant_group",
        "tenant",
        "site", # Use site
        "location",
        "rack_group",
        "rack",
        "role",
        "manufacturer",
        "platform",
        # Add device_status filter if needed, depends on Status model usage
        "device_type",
        "device",
        "tag",
    ]
    # q defined in BaseFilterForm

# NetBox BulkEditForm might be different, adapt if necessary
class GoldenConfigBulkEditForm(BootstrapMixin, django_forms.Form):
    """BulkEdit form for GoldenConfig instances."""
    # Typically NetBox uses a pk QuerySet in the view, not explicitly in the form
    pk = DynamicModelMultipleChoiceField(queryset=models.GoldenConfig.objects.all(), widget=django_forms.MultipleHiddenInput)
    # Add fields to bulk edit here, e.g.:
    # description = django_forms.CharField(max_length=200, required=False)

    class Meta:
        nullable_fields = [] # Define fields that can be cleared


class ConfigComplianceFilterForm(DeviceRelatedFilterForm):
    """Filter Form for ConfigCompliance instances."""
    model = models.ConfigCompliance
    field_order = [
        "q",
        "tenant_group",
        "tenant",
        "site", # Use site
        "location",
        "rack_group",
        "rack",
        "role",
        "manufacturer",
        "platform",
        "device_status",
        "device_type",
        "device",
        "tag",
    ]
    # q defined in BaseFilterForm

    # Add device status filter
    device_status = DynamicModelMultipleChoiceField(
        queryset=Status.objects.filter(content_types__model="device"), # Filter status applicable to devices
        required=False,
        label='Device Status',
        to_field_name='slug' # Use slug
    )


# ComplianceRule
class ComplianceRuleForm(BootstrapMixin, django_forms.ModelForm): # Use standard ModelForm + BootstrapMixin
    """Form for ComplianceRule instances."""
    platform = DynamicModelChoiceField(queryset=Platform.objects.all())
    feature = DynamicModelChoiceField(queryset=models.ComplianceFeature.objects.all())

    class Meta:
        model = models.ComplianceRule
        fields = "__all__"


class ComplianceRuleFilterForm(BaseFilterForm): # Use custom base
    """Filter Form for ComplianceRule instances."""
    model = models.ComplianceRule

    platform = DynamicModelMultipleChoiceField(
        queryset=Platform.objects.all(),
        to_field_name='slug', # Use slug
        required=False
    )
    feature = DynamicModelMultipleChoiceField(
        queryset=models.ComplianceFeature.objects.all(),
        to_field_name='slug', # Use slug
        required=False
    )
    tag = TagFilterField(model)


class ComplianceRuleBulkEditForm(BootstrapMixin, django_forms.Form): # Use standard Form + BootstrapMixin
    """BulkEdit form for ComplianceRule instances."""
    pk = DynamicModelMultipleChoiceField(queryset=models.ComplianceRule.objects.all(), widget=django_forms.MultipleHiddenInput)
    description = django_forms.CharField(max_length=200, required=False)
    config_type = django_forms.ChoiceField(
        required=False,
        choices=ComplianceRuleConfigTypeChoice.CHOICES, # Use CHOICES
        # Use add_blank_choice if needed
    )
    config_ordered = django_forms.NullBooleanField(required=False, widget=BulkEditNullBooleanSelect())
    custom_compliance = django_forms.NullBooleanField(required=False, widget=BulkEditNullBooleanSelect())
    config_remediation = django_forms.NullBooleanField(required=False, widget=BulkEditNullBooleanSelect())

    class Meta:
        nullable_fields = ['description']


# ComplianceFeature
class ComplianceFeatureForm(BootstrapMixin, django_forms.ModelForm):
    """Form for ComplianceFeature instances."""
    slug = SlugField() # Use NetBox SlugField

    class Meta:
        model = models.ComplianceFeature
        fields = "__all__"


class ComplianceFeatureFilterForm(BaseFilterForm): # Use custom base
    """Filter Form for ComplianceFeature instances."""
    model = models.ComplianceFeature
    name = DynamicModelMultipleChoiceField( # Allow multiple for filtering
          queryset=models.ComplianceFeature.objects.all(),
          to_field_name='name',
          required=False
      )
    slug = DynamicModelMultipleChoiceField( # Allow multiple for filtering
          queryset=models.ComplianceFeature.objects.all(),
          to_field_name='slug',
          required=False
      )
    tag = TagFilterField(model)


class ComplianceFeatureBulkEditForm(BootstrapMixin, django_forms.Form): # Use standard Form + BootstrapMixin
    """BulkEdit form for ComplianceFeature instances."""
    pk = DynamicModelMultipleChoiceField(queryset=models.ComplianceFeature.objects.all(), widget=django_forms.MultipleHiddenInput)
    description = django_forms.CharField(max_length=200, required=False)

    class Meta:
        nullable_fields = ['description']


# ConfigRemove
class ConfigRemoveForm(BootstrapMixin, django_forms.ModelForm):
    """Form for ConfigRemove instances."""
    platform = DynamicModelChoiceField(queryset=Platform.objects.all())

    class Meta:
        model = models.ConfigRemove
        fields = "__all__"


class ConfigRemoveFilterForm(BaseFilterForm): # Use custom base
    """Filter Form for ConfigRemove."""
    model = models.ConfigRemove
    platform = DynamicModelMultipleChoiceField(
        queryset=Platform.objects.all(),
        to_field_name='slug', # Use slug
        required=False
    )
    name = DynamicModelMultipleChoiceField( # Allow multiple
        queryset=models.ConfigRemove.objects.all(),
        to_field_name='name',
        required=False
    )
    tag = TagFilterField(model)


class ConfigRemoveBulkEditForm(BootstrapMixin, django_forms.Form): # Use standard Form + BootstrapMixin
    """BulkEdit form for ConfigRemove instances."""
    pk = DynamicModelMultipleChoiceField(queryset=models.ConfigRemove.objects.all(), widget=django_forms.MultipleHiddenInput)
    description = django_forms.CharField(max_length=200, required=False)

    class Meta:
        nullable_fields = ['description']


# ConfigReplace
class ConfigReplaceForm(BootstrapMixin, django_forms.ModelForm):
    """Form for ConfigReplace instances."""
    platform = DynamicModelChoiceField(queryset=Platform.objects.all())

    class Meta:
        model = models.ConfigReplace
        fields = "__all__"


class ConfigReplaceFilterForm(BaseFilterForm): # Use custom base
    """Filter Form for ConfigReplace."""
    model = models.ConfigReplace
    platform = DynamicModelMultipleChoiceField(
        queryset=Platform.objects.all(),
        to_field_name='slug', # Use slug
        required=False
    )
    name = DynamicModelMultipleChoiceField( # Allow multiple
        queryset=models.ConfigReplace.objects.all(),
        to_field_name='name',
        required=False
    )
    tag = TagFilterField(model)


class ConfigReplaceBulkEditForm(BootstrapMixin, django_forms.Form): # Use standard Form + BootstrapMixin
    """BulkEdit form for ConfigReplace instances."""
    pk = DynamicModelMultipleChoiceField(queryset=models.ConfigReplace.objects.all(), widget=django_forms.MultipleHiddenInput)
    description = django_forms.CharField(max_length=200, required=False)

    class Meta:
        nullable_fields = ['description']


# GoldenConfigSetting
class GoldenConfigSettingForm(BootstrapMixin, django_forms.ModelForm):
    """Form for GoldenConfigSetting instances."""
    slug = SlugField()
    # Dynamic Group replacement - choose one:
    # Option 1: Tags
    # scope_tags = DynamicModelMultipleChoiceField(queryset=Tag.objects.all(), required=False)
    # Option 2: JSON Filter (use a TextArea)
    scope_filter = django_forms.CharField(
         required=False,
         widget=django_forms.Textarea(attrs={'rows': 5}),
         label='Scope Filter (JSON)',
         help_text='Enter NetBox filter parameters as JSON to scope devices for this setting.'
    )
    # Ensure GraphQLQuery field uses appropriate widget if different in NetBox
    sot_agg_query = DynamicModelChoiceField(queryset=GraphQLQuery.objects.all(), required=False)

    class Meta:
        model = models.GoldenConfigSetting
        fields = "__all__"
        # Exclude dynamic_group if it was removed from the model
        # exclude = ['dynamic_group']

    def clean_scope_filter(self):
         """Validate the scope_filter JSON."""
         data = self.cleaned_data['scope_filter']
         if not data:
             return None # Allow empty filter
         try:
             parsed_data = json.loads(data)
             if not isinstance(parsed_data, dict):
                 raise ValidationError("Scope filter must be a valid JSON object.")
             # Optional: Add further validation of filter keys/values against Device model fields
             return parsed_data
         except json.JSONDecodeError:
             raise ValidationError("Invalid JSON format for scope filter.")


class GoldenConfigSettingFilterForm(BaseFilterForm): # Use custom base
    """Filter Form for GoldenConfigSetting instances."""
    model = models.GoldenConfigSetting
    name = django_forms.CharField(required=False)
    slug = django_forms.CharField(required=False) # Add slug filter
    weight = django_forms.IntegerField(required=False)
    # Adapt GitRepository filtering based on NetBox plugin content declaration method (might need custom filter)
    backup_repository = DynamicModelMultipleChoiceField(
        queryset=GitRepository.objects.all(), # Adjust queryset if possible
        required=False,
        to_field_name='name',
    )
    intended_repository = DynamicModelMultipleChoiceField(
        queryset=GitRepository.objects.all(), # Adjust queryset if possible
        required=False,
        to_field_name='name',
    )
    jinja_repository = DynamicModelMultipleChoiceField(
        queryset=GitRepository.objects.all(), # Adjust queryset if possible
        required=False,
        to_field_name='name',
    )
    tag = TagFilterField(model)


class GoldenConfigSettingBulkEditForm(BootstrapMixin, django_forms.Form): # Use standard Form + BootstrapMixin
    """BulkEdit form for GoldenConfigSetting instances."""
    pk = DynamicModelMultipleChoiceField(queryset=models.GoldenConfigSetting.objects.all(), widget=django_forms.MultipleHiddenInput)
    weight = django_forms.IntegerField(required=False)
    description = django_forms.CharField(max_length=200, required=False)
    backup_path_template = django_forms.CharField(max_length=255, required=False)
    intended_path_template = django_forms.CharField(max_length=255, required=False)
    jinja_path_template = django_forms.CharField(max_length=255, required=False)
    backup_test_connectivity = django_forms.NullBooleanField(required=False, widget=BulkEditNullBooleanSelect())
    backup_repository = DynamicModelChoiceField(queryset=GitRepository.objects.all(), required=False)
    intended_repository = DynamicModelChoiceField(queryset=GitRepository.objects.all(), required=False)
    jinja_repository = DynamicModelChoiceField(queryset=GitRepository.objects.all(), required=False)
    sot_agg_query = DynamicModelChoiceField(queryset=GraphQLQuery.objects.all(), required=False)
    # scope_tags = DynamicModelMultipleChoiceField(queryset=Tag.objects.all(), required=False) # Option 1 for scope
    scope_filter = django_forms.CharField(required=False, widget=django_forms.Textarea(attrs={'rows': 5})) # Option 2 for scope


    class Meta:
        nullable_fields = [ # Define fields that can be cleared in bulk edit
             'description', 'backup_repository', 'backup_path_template',
             'intended_repository', 'intended_path_template', 'jinja_repository',
             'jinja_path_template', 'backup_test_connectivity', 'sot_agg_query',
             # 'scope_tags', # Option 1
             'scope_filter', # Option 2
             ]


# Remediation Setting
class RemediationSettingForm(BootstrapMixin, django_forms.ModelForm):
    """Create/Update Form for Remediation Settings instances."""
    platform = DynamicModelChoiceField(queryset=Platform.objects.all())

    class Meta:
        model = models.RemediationSetting
        fields = "__all__"


class RemediationSettingFilterForm(BaseFilterForm): # Use custom base
    """Filter Form for Remediation Settings."""
    model = models.RemediationSetting
    platform = DynamicModelMultipleChoiceField(
        queryset=Platform.objects.all(),
        required=False,
        to_field_name="slug" # Use slug
    )
    remediation_type = django_forms.ChoiceField(
        choices=[('', '---------')] + list(RemediationTypeChoice.CHOICES), # Add blank choice manually
        required=False,
        widget=StaticSelect2(), # Use NetBox widget
        label="Remediation Type",
    )
    tag = TagFilterField(model)


class RemediationSettingBulkEditForm(BootstrapMixin, django_forms.Form): # Use standard Form + BootstrapMixin
    """BulkEdit form for RemediationSetting instances."""
    pk = DynamicModelMultipleChoiceField(queryset=models.RemediationSetting.objects.all(), widget=django_forms.MultipleHiddenInput)
    remediation_type = django_forms.ChoiceField(
         choices=[('', '---------')] + list(RemediationTypeChoice.CHOICES), # Add blank choice
         required=False,
         label="Remediation Type"
         )
    remediation_options = django_forms.CharField(required=False, widget=django_forms.Textarea(attrs={'rows': 5}), label='Remediation Options (JSON)') # Allow editing options as JSON

    class Meta:
        nullable_fields = ['remediation_options']

    def clean_remediation_options(self):
         """Validate the remediation_options JSON."""
         data = self.cleaned_data['remediation_options']
         if not data:
             return None
         try:
             parsed_data = json.loads(data)
             if not isinstance(parsed_data, dict):
                 raise ValidationError("Remediation options must be a valid JSON object.")
             return parsed_data
         except json.JSONDecodeError:
             raise ValidationError("Invalid JSON format for remediation options.")


# ConfigPlan
# Note: Creating ConfigPlans is usually done via a Job/Script in the original plugin.
# This form is primarily for *filtering* and potentially limited updates.
# If direct creation via UI is desired, adapt this form further.
class ConfigPlanForm(BootstrapMixin, django_forms.ModelForm):
    """Form for *creating* ConfigPlan instances (adapt if needed, usually via Job)."""
    # Fields relevant for *manual* plan creation or Job input form
    plan_type = django_forms.ChoiceField(choices=ConfigPlanTypeChoice.CHOICES, widget=StaticSelect2())
    feature = DynamicModelMultipleChoiceField(
        queryset=models.ComplianceFeature.objects.all(),
        required=False, # Optional for manual plans
        help_text="Note: Selecting no features will generate plans for all applicable features.",
    )
    commands = django_forms.CharField(
        widget=django_forms.Textarea,
        required=False, # Only required for manual plan type
        help_text=(
            "Enter your configuration template here representing CLI configuration.<br>"
            'You may use Jinja2 templating. Example: <code>{% if "foo" in bar %}foo{% endif %}</code><br>'
            "You can also reference the device object with <code>obj</code>.<br>"
            "For example: <code>hostname {{ obj.name }}</code> or <code>ip address {{ obj.primary_ip4.host }}</code>"
        ),
    )

    # Device Selection Fields (might be separate in a Job form)
    tenant_group = DynamicModelMultipleChoiceField(queryset=TenantGroup.objects.all(), required=False)
    tenant = DynamicModelMultipleChoiceField(queryset=Tenant.objects.all(), required=False, query_params={"group": "$tenant_group"})
    site = DynamicModelMultipleChoiceField(queryset=Site.objects.all(), required=False) # Use Site
    location = DynamicModelMultipleChoiceField(queryset=Location.objects.all(), required=False, query_params={"site": "$site"})
    rack_group = DynamicModelMultipleChoiceField(queryset=RackGroup.objects.all(), required=False, query_params={"site": "$site"})
    rack = DynamicModelMultipleChoiceField(queryset=Rack.objects.all(), required=False, query_params={"group": "$rack_group", "site": "$site"})
    role = DynamicModelMultipleChoiceField(queryset=Role.objects.filter(content_types__model="device"), required=False)
    manufacturer = DynamicModelMultipleChoiceField(queryset=Manufacturer.objects.all(), required=False)
    platform = DynamicModelMultipleChoiceField(queryset=Platform.objects.all(), required=False)
    device_type = DynamicModelMultipleChoiceField(queryset=DeviceType.objects.all(), required=False)
    device = DynamicModelMultipleChoiceField(queryset=Device.objects.all(), required=False)
    tag = DynamicModelMultipleChoiceField( # Use Tag instead of Tags
        queryset=Tag.objects.filter(content_types__model="device"),
        required=False
    )
    status = DynamicModelMultipleChoiceField( # Use Status instead of Statuses
        queryset=Status.objects.filter(content_types__model="device"),
        required=False
    )

    class Meta:
        model = models.ConfigPlan
        # Define fields needed for creation form, excluding Job results, etc.
        fields = [
             'plan_type', 'feature', 'commands', 'change_control_id', 'change_control_url',
             # Include device filter fields if this form is used for Job input
             'tenant_group', 'tenant', 'site', 'location', 'rack_group', 'rack',
             'role', 'manufacturer', 'platform', 'device_type', 'device', 'tag', 'status',
        ]
        widgets = { # Example widgets
             'change_control_url': django_forms.URLInput(),
        }

    # hide_form_data logic needs to be implemented using JavaScript in the template
    # You can pass the data structure to the template context and use JS there.
    # Example:
    # def __init__(self, *args, **kwargs):
    #     super().__init__(*args, **kwargs)
    #     self.hide_form_data = json.dumps(...) # Define your structure


class ConfigPlanUpdateForm(BootstrapMixin, django_forms.ModelForm): # Use standard ModelForm
    """Form for updating existing ConfigPlan instances."""
    status = DynamicModelChoiceField(
        queryset=Status.objects.filter(content_types__model='netbox_golden_config.configplan'), # Filter Status for ConfigPlan
    )
    tags = DynamicModelMultipleChoiceField( # Use standard field for tags
        queryset=Tag.objects.filter(content_types__model='netbox_golden_config.configplan'),
        required=False
    )

    class Meta:
        model = models.ConfigPlan
        fields = ( # Define only updatable fields
            "change_control_id",
            "change_control_url",
            "status",
            "tags",
        )


class ConfigPlanFilterForm(DeviceRelatedFilterForm): # Inherit device filters
    """Filter Form for ConfigPlan."""
    model = models.ConfigPlan

    created__before = django_forms.DateField(label="Created Before", required=False, widget=DatePicker()) # Use DateField
    created__after = django_forms.DateField(label="Created After", required=False, widget=DatePicker())  # Use DateField
    plan_type = django_forms.ChoiceField(
        choices=[('', '---------')] + list(ConfigPlanTypeChoice.CHOICES), # Add blank choice manually
        required=False,
        widget=StaticSelect2(), # Use NetBox widget
        label="Plan Type",
    )
    feature = DynamicModelMultipleChoiceField(
        queryset=models.ComplianceFeature.objects.all(),
        required=False,
        to_field_name="slug", # Use slug
        label="Feature",
    )
    change_control_id = django_forms.CharField(required=False, label="Change Control ID")
    # JobResult filtering might need adaptation based on NetBox JobResult model/relations
    plan_result = DynamicModelMultipleChoiceField(
        queryset=JobResult.objects.filter(obj_type=ContentType.objects.get(app_label='netbox_golden_config', model='configplan'), status__in=['completed', 'failed', 'errored']), # Example filter
        label="Plan Result",
        required=False,
        # display_field="created", # Adjust display field
        to_field_name="pk", # Use PK
    )
    deploy_result = DynamicModelMultipleChoiceField(
        queryset=JobResult.objects.filter(obj_type=ContentType.objects.get(app_label='netbox_golden_config', model='configplan'), status__in=['completed', 'failed', 'errored']), # Example filter
        label="Deploy Result",
        required=False,
        # display_field="created", # Adjust display field
        to_field_name="pk", # Use PK
    )
    status = DynamicModelMultipleChoiceField(
        required=False,
        queryset=Status.objects.filter(content_types__model='netbox_golden_config.configplan'),
        to_field_name="slug", # Use slug
        label="Status",
    )
    # tag defined in DeviceRelatedFilterForm

    field_order = [ # Define field order
        'q', 'plan_type', 'feature', 'change_control_id', 'status', 'created__before', 'created__after',
        'plan_result', 'deploy_result', 'tag',
        # Device fields from parent
        'tenant_group', 'tenant', 'site', 'location', 'rack_group', 'rack',
        'role', 'manufacturer', 'platform', 'device_type', 'device', 'device_status'
        ]


class ConfigPlanBulkEditForm(BootstrapMixin, django_forms.Form): # Use standard Form + BootstrapMixin
    """BulkEdit form for ConfigPlan instances."""
    pk = DynamicModelMultipleChoiceField(queryset=models.ConfigPlan.objects.all(), widget=django_forms.MultipleHiddenInput)
    status = DynamicModelChoiceField(
        queryset=Status.objects.filter(content_types__model='netbox_golden_config.configplan'),
        required=False,
    )
    change_control_id = django_forms.CharField(required=False, label="Change Control ID")
    change_control_url = django_forms.URLField(required=False, label="Change Control URL")
    # Add tags for bulk editing if needed
    add_tags = DynamicModelMultipleChoiceField(queryset=Tag.objects.all(), required=False)
    remove_tags = DynamicModelMultipleChoiceField(queryset=Tag.objects.all(), required=False)


    class Meta:
        nullable_fields = [
            "change_control_id",
            "change_control_url",
            "status", # Allow clearing status
            # Add tags if they can be cleared
        ]


# This form seems specific to a UI tool, adapt if needed for NetBox UI or remove if tool is separate
class GenerateIntendedConfigForm(BootstrapMixin, django_forms.Form):
    """Form for generating intended configuration (likely used in a custom view or script form)."""
    device = DynamicModelChoiceField(
        queryset=Device.objects.all(),
        required=True,
        label="Device",
    )
    graphql_query = DynamicModelChoiceField(
        queryset=GraphQLQuery.objects.all(),
        required=True,
        label="GraphQL Query",
        # query_params need adaptation if NetBox GraphQLQuery model differs
        # query_params={"variables__contains": "device_id"}, # Example adaptation
    )
    # Git branch selection might need different handling depending on NetBox Git integration
    git_repository_branch = django_forms.ChoiceField(widget=StaticSelect2, required=False) # Make optional?

    # def __init__(self, *args, **kwargs):
    #     """Conditionally hide the git_repository_branch field based on NetBox version."""
    #     super().__init__(*args, **kwargs)
    #     # NetBox version check logic would go here if needed
    #     # if version.parse(settings.VERSION) < version.parse("..."):
    #     #     self.fields["git_repository_branch"].widget = django_forms.HiddenInput
