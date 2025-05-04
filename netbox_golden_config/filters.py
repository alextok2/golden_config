"""Filtering for netbox_golden_config."""

import django_filters
from netbox.filtersets import NetBoxModelFilterSet # NetBox base filterset
# NetBox filters
from utilities.filters import MultiValueCharFilter, MultiValueDateFilter, MultiValueDateTimeFilter, TagFilter, TreeNodeMultipleChoiceFilter, RelatedMembershipBooleanFilter

# NetBox models
from dcim.models import Device, DeviceType, Location, Manufacturer, Platform, Rack, RackGroup, Site # Use Site
from extras.models import Tag, Status, Role, JobResult
from tenancy.models import Tenant, TenantGroup

from . import models # Use local models

# Define common device-related filters in a mixin or base class
class DeviceRelatedFilterSetMixin(django_filters.FilterSet):
     # Use NetBox standard fields where possible (e.g., ModelMultipleChoiceFilter)
     # Adjust `to_field_name` typically to 'slug' or 'name' for NetBox

     q = django_filters.CharFilter(
        method='search',
        label='Search',
    )
     tenant_group = TreeNodeMultipleChoiceFilter(
        queryset=TenantGroup.objects.all(),
        field_name='device__tenant__group', # Adjust field path if Tenant model differs
        to_field_name='slug',
        label='Tenant Group (slug)',
    )
     tenant = django_filters.ModelMultipleChoiceFilter(
        queryset=Tenant.objects.all(),
        field_name='device__tenant',
        to_field_name='slug',
        label='Tenant (slug)',
    )
     site = TreeNodeMultipleChoiceFilter( # Use Site
        queryset=Site.objects.all(),
        field_name='device__site',
        to_field_name='slug',
        label='Site (slug)',
    )
     location = TreeNodeMultipleChoiceFilter( # Keep if nested Locations are used
        queryset=Location.objects.all(),
        field_name='device__location',
        to_field_name='slug',
        label='Location (slug)',
        # query_params={'site_id': '$site'}, # Adjust filtering based on model relations
    )
     rack_group = TreeNodeMultipleChoiceFilter(
        queryset=RackGroup.objects.all(),
        field_name='device__rack__group', # Adjust field path
        to_field_name='slug',
        label='Rack group (slug)',
    )
     rack = django_filters.ModelMultipleChoiceFilter(
        field_name='device__rack',
        queryset=Rack.objects.all(),
        to_field_name='name', # Or 'id'
        label='Rack (name or ID)',
    )
     role = django_filters.ModelMultipleChoiceFilter(
        field_name='device__role',
        queryset=Role.objects.filter(content_types__model='device'),
        to_field_name='slug',
        label='Role (slug)',
    )
     manufacturer = django_filters.ModelMultipleChoiceFilter(
        field_name='device__device_type__manufacturer',
        queryset=Manufacturer.objects.all(),
        to_field_name='slug',
        label='Manufacturer (slug)',
    )
     platform = django_filters.ModelMultipleChoiceFilter(
        field_name='device__platform',
        queryset=Platform.objects.all(),
        to_field_name='slug',
        label='Platform (slug)',
    )
     device_status = django_filters.ModelMultipleChoiceFilter( # Use standard filter for Status FK
        field_name='device__status',
        queryset=Status.objects.filter(content_types__model='device'),
        to_field_name='slug',
        label='Device Status (slug)',
    )
     device_type = django_filters.ModelMultipleChoiceFilter(
        field_name='device__device_type',
        queryset=DeviceType.objects.all(),
        to_field_name='slug', # Use slug
        label='Device Type (slug)',
    )
     device = django_filters.ModelMultipleChoiceFilter(
        field_name='device',
        queryset=Device.objects.all(),
        to_field_name='name', # Or 'id'
        label='Device (name or ID)',
    )
     tag = TagFilter( # Use NetBox TagFilter
        field_name='device__tags'
     )

     # Search method if using q filter
     def search(self, queryset, name, value):
          if not value.strip():
              return queryset
          # Define fields to search against
          return queryset.filter(
              Q(device__name__icontains=value) |
              Q(device__serial__icontains=value) # Add other relevant device fields
              # Add searches for related fields if needed, e.g. Q(device__site__name__icontains=value)
          ).distinct()


class GoldenConfigFilterSet(DeviceRelatedFilterSetMixin, NetBoxModelFilterSet): # Inherit mixin and NetBox base
    """Filter capabilities for GoldenConfig instances."""

    class Meta:
        model = models.GoldenConfig
        # Define fields specific to GoldenConfig model itself, if any
        fields = ['id', 'device'] # Add other direct fields if needed

        # Inherit device-related fields from the mixin automatically


class ConfigComplianceFilterSet(DeviceRelatedFilterSetMixin, NetBoxModelFilterSet): # Inherit mixin and NetBox base
    """Filter capabilities for ConfigCompliance instances."""

    feature = django_filters.ModelMultipleChoiceFilter(
        field_name='rule__feature',
        queryset=models.ComplianceFeature.objects.all(),
        to_field_name='slug', # Filter by feature slug
        label='Compliance Feature (slug)',
    )
    # Add compliance boolean filter
    compliance = django_filters.BooleanFilter()
    ordered = django_filters.BooleanFilter()


    class Meta:
        model = models.ConfigCompliance
        # Define fields specific to ConfigCompliance model itself
        fields = ['id', 'device', 'rule', 'compliance', 'ordered', 'feature']

        # Inherit device-related fields from the mixin


class ComplianceFeatureFilterSet(NetBoxModelFilterSet):
    """Filter capabilities for ComplianceFeature instances."""
    tag = TagFilter() # Add TagFilter

    class Meta:
        model = models.ComplianceFeature
        fields = ['id', 'name', 'slug', 'description', 'tag']


class ComplianceRuleFilterSet(NetBoxModelFilterSet):
    """Filter capabilities for ComplianceRule instances."""
    tag = TagFilter()
    platform = django_filters.ModelMultipleChoiceFilter(
        queryset=Platform.objects.all(),
        to_field_name='slug',
        label='Platform (slug)',
    )
    feature = django_filters.ModelMultipleChoiceFilter(
        queryset=models.ComplianceFeature.objects.all(),
        to_field_name='slug',
        label='Feature (slug)',
    )

    class Meta:
        model = models.ComplianceRule
        fields = ['id', 'platform', 'feature', 'description', 'config_ordered', 'config_type', 'custom_compliance', 'config_remediation', 'tag']


class ConfigRemoveFilterSet(NetBoxModelFilterSet):
    """Filter capabilities for ConfigRemove instances."""
    tag = TagFilter()
    platform = django_filters.ModelMultipleChoiceFilter(
        queryset=Platform.objects.all(),
        to_field_name='slug',
        label='Platform (slug)',
    )

    class Meta:
        model = models.ConfigRemove
        fields = ['id', 'name', 'platform', 'description', 'regex', 'tag']


class ConfigReplaceFilterSet(NetBoxModelFilterSet):
    """Filter capabilities for ConfigReplace instances."""
    tag = TagFilter()
    platform = django_filters.ModelMultipleChoiceFilter(
        queryset=Platform.objects.all(),
        to_field_name='slug',
        label='Platform (slug)',
    )

    class Meta:
        model = models.ConfigReplace
        fields = ['id', 'name', 'platform', 'description', 'regex', 'replace', 'tag']


class GoldenConfigSettingFilterSet(NetBoxModelFilterSet):
    """Filter capabilities for GoldenConfigSetting instances."""
    tag = TagFilter()

    # Custom filter method for devices matching the setting's scope
    # This requires adapting based on the chosen scope mechanism (Tags or Filter)
    has_devices = RelatedMembershipBooleanFilter(
         field_name='pk', # Placeholder, logic is in filter method
         label='Has scoped devices',
         method='filter_has_devices'
    )
    # Filter by device (find settings that apply to a specific device)
    device_id = django_filters.ModelChoiceFilter(
         queryset=Device.objects.all(),
         method='filter_by_device',
         label='Settings Applying to Device (ID)',
    )

    # Add filters for repositories if needed
    backup_repository = django_filters.ModelMultipleChoiceFilter(
         field_name='backup_repository',
         queryset=GitRepository.objects.all(),
         to_field_name='name',
         label='Backup Repository (name)',
    )
    intended_repository = django_filters.ModelMultipleChoiceFilter(
         field_name='intended_repository',
         queryset=GitRepository.objects.all(),
         to_field_name='name',
         label='Intended Repository (name)',
    )
    jinja_repository = django_filters.ModelMultipleChoiceFilter(
         field_name='jinja_repository',
         queryset=GitRepository.objects.all(),
         to_field_name='name',
         label='Jinja Repository (name)',
    )


    class Meta:
        model = models.GoldenConfigSetting
        fields = ['id', 'name', 'slug', 'weight', 'description', 'tag', 'has_devices', 'device_id']

    def filter_by_device(self, queryset, name, value):
         """Filter settings that apply to the given device."""
         if not value:
             return queryset
         device = value # value is the Device instance when ModelChoiceFilter is used
         # Use the manager method (needs adaptation)
         applicable_setting = models.GoldenConfigSetting.objects.get_for_device(device)
         if applicable_setting:
             return queryset.filter(pk=applicable_setting.pk)
         return queryset.none()

    def filter_has_devices(self, queryset, name, value):
         """Filter settings based on whether they currently scope any devices."""
         # This requires iterating through settings and checking their scope, which can be slow.
         # It's better to implement this check efficiently based on the chosen scope mechanism.
         pks_with_devices = []
         for setting in queryset:
             # Replace with actual scope check logic
             # Example using scope_filter:
             if setting.scope_filter and DeviceFilterSet(data=setting.scope_filter, queryset=Device.objects.all()).qs.exists():
                  pks_with_devices.append(setting.pk)
             # Example using scope_tags:
             # elif setting.scope_tags.exists() and Device.objects.filter(tags__in=setting.scope_tags.all()).exists():
             #     pks_with_devices.append(setting.pk)

         if value: # True - show only settings that scope devices
             return queryset.filter(pk__in=pks_with_devices)
         # False - show only settings that do *not* scope devices
         return queryset.exclude(pk__in=pks_with_devices)


class RemediationSettingFilterSet(NetBoxModelFilterSet):
    """Filter capabilities for RemediationSetting instances."""
    tag = TagFilter()
    platform = django_filters.ModelMultipleChoiceFilter(
        queryset=Platform.objects.all(),
        to_field_name='slug',
        label='Platform (slug)',
    )
    remediation_type = django_filters.ChoiceFilter(
         choices=models.RemediationTypeChoice.CHOICES,
    )

    class Meta:
        model = models.RemediationSetting
        fields = ['id', 'platform', 'remediation_type', 'tag']


class ConfigPlanFilterSet(DeviceRelatedFilterSetMixin, NetBoxModelFilterSet): # Inherit device filters
    """Filter capabilities for ConfigPlan instances."""
    tag = TagFilter() # Already inherited? Ensure it targets ConfigPlan tags if needed, or redefine.
    tag = TagFilter(
         field_name='tags' # Explicitly target ConfigPlan tags
     )

    feature = django_filters.ModelMultipleChoiceFilter(
        queryset=models.ComplianceFeature.objects.all(),
        to_field_name='slug',
        label='Feature (slug)',
    )
    status = django_filters.ModelMultipleChoiceFilter(
        queryset=Status.objects.filter(content_types__model='configplan', app_label='netbox_golden_config'), # Filter Status for ConfigPlan
        to_field_name='slug',
        label='Status (slug)',
    )
    plan_type = django_filters.ChoiceFilter(
        choices=models.ConfigPlanTypeChoice.CHOICES,
    )
    created = MultiValueDateFilter() # Use NetBox Date Filter
    plan_result = django_filters.ModelMultipleChoiceFilter(
        queryset=JobResult.objects.all(), # May need further filtering based on Job type
        to_field_name='pk',
        label='Plan Job Result (ID)',
    )
    deploy_result = django_filters.ModelMultipleChoiceFilter(
        queryset=JobResult.objects.all(), # May need further filtering based on Job type
        to_field_name='pk',
        label='Deploy Job Result (ID)',
    )
    change_control_id = django_filters.CharFilter(
        lookup_expr='icontains', # Allow partial match
    )

    class Meta:
        model = models.ConfigPlan
        fields = [
            'id', 'plan_type', 'device', 'feature', 'plan_result', 'deploy_result',
            'change_control_id', 'status', 'created', 'tag',
            # Inherited device fields will also be available
        ]

    # Override search method if needed to include ConfigPlan specific fields
    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        # Search device fields using parent method (assuming DeviceRelatedFilterSetMixin has `search`)
        qs_device_search = super().search(queryset, name, value)
        # Search ConfigPlan specific fields
        qs_plan_search = queryset.filter(
            Q(change_control_id__icontains=value) |
            Q(config_set__icontains=value) # Search config set content? Be careful with performance.
        )
        return (qs_device_search | qs_plan_search).distinct()
