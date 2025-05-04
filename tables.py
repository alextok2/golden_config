"""Django Tables2 classes for netbox_golden_config app."""

from django.utils.html import format_html
import django_tables2 as tables # Use standard django_tables2
from netbox.tables import NetBoxTable, columns # Use NetBox table components

from . import models # Use local models
from .utilities.constant import CONFIG_FEATURES, ENABLE_BACKUP, ENABLE_COMPLIANCE, ENABLE_INTENDED # Use local constants

# Template column definitions (keep similar structure, adjust URLs/Context)
ALL_ACTIONS = """
{% load helpers %}
{% if backup == True %}
    {# Link to backup view (modal or separate page) #}
    {% if record.backup_config %}
        <a href="{% url 'plugins:netbox_golden_config:goldenconfig_backup' pk=record.device.pk %}" class="btn btn-xs btn-default" title="Backup Configuration"> {# Adjust class/styling #}
            <i class="mdi mdi-file-document-outline"></i>
        </a>
    {% else %}
        <span class="text-muted"><i class="mdi mdi-circle-small"></i></span>
    {% endif %}
{% endif %}
{% if intended == True %}
    {% if record.intended_config %}
        <a href="{% url 'plugins:netbox_golden_config:goldenconfig_intended' pk=record.device.pk %}" class="btn btn-xs btn-default" title="Intended Configuration">
            <i class="mdi mdi-text-box-check-outline"></i>
        </a>
    {% else %}
        <span class="text-muted"><i class="mdi mdi-circle-small"></i></span>
    {% endif %}
{% endif %}
{% if postprocessing == True %}
    {% if record.intended_config %}
        <a href="{% url 'plugins:netbox_golden_config:goldenconfig_postprocessing' pk=record.device.pk %}" class="btn btn-xs btn-default" title="Configuration after Postprocessing">
            <i class="mdi mdi-text-box-check"></i>
        </a>
    {% else %}
        <span class="text-muted"><i class="mdi mdi-circle-small"></i></span>
    {% endif %}
{% endif %}
{% if compliance == True %}
    {% if record.intended_config and record.backup_config %}
        <a href="{% url 'plugins:netbox_golden_config:goldenconfig_compliance' pk=record.device.pk %}" class="btn btn-xs btn-default" title="Compliance Details">
            <i class="mdi mdi-file-compare"></i>
        </a>
    {% else %}
        <span class="text-muted"><i class="mdi mdi-circle-small"></i></span>
    {% endif %}
{% endif %}
{% if sotagg == True %}
     {# Link to SOTAgg view #}
    <a href="{% url 'plugins:netbox_golden_config:goldenconfig_sotagg' pk=record.device.pk %}" class="btn btn-xs btn-default" title="SOT Aggregate Data">
        <i class="mdi mdi-code-json"></i>
    </a>
    {# Link to Run All Job (adapt Job URL) #}
    <a href="{% url 'extras:job_run_by_class' job_class_path='netbox_golden_config.jobs.AllGoldenConfig' %}?device={{ record.device.pk }}" class="btn btn-xs btn-default" title="Execute All Golden Config Jobs">
        <i class="mdi mdi-play-circle"></i>
    </a>
{% endif %}
"""

CONFIG_SET_BUTTON = """
{% load helpers %}
<button type="button" class="btn btn-xs btn-default" data-toggle="modal" data-target="#codeModal-{{ record.pk }}" title="View Config Set">
    <i class="mdi mdi-file-document-outline"></i>
</button>

<div class="modal fade" id="codeModal-{{ record.pk }}" role="dialog" tabindex="-1">
    <div class="modal-dialog modal-lg">
        <div class="modal-content">
            <div class="modal-header">
                 <h4 class="modal-title">Config Set - {{ record.device }}</h4>
                 <button type="button" class="close" data-dismiss="modal">&times;</button> {# Adjusted close button #}
            </div>
            <div class="modal-body">
                {# Use standard NetBox table styling #}
                <table class="table table-hover table-striped table-auto">
                    <tbody>
                        <tr>
                            <th style="width: 20%">Config Set</th>
                            <td>
                                <div class="float-right noprint"> {# Copy button styling #}
                                    <button class="btn btn-sm btn-primary copy-to-clipboard" data-clipboard-target="#config_set_{{ record.pk }}">
                                        <i class="mdi mdi-content-copy"></i>
                                    </button>
                                </div>
                                <pre id="config_set_{{ record.pk }}">{{ record.config_set }}</pre>
                            </td>
                        </tr>
                        <tr>
                            <th>Postprocessed Config Set</th>
                            <td>
                                <a href="{% url 'plugins:netbox_golden_config:goldenconfig_postprocessing' pk=record.device.pk %}?config_plan_id={{ record.pk }}" class="btn btn-xs btn-default" title="View Config Plan after Postprocessing" target="_blank">
                                    <i class="mdi mdi-text-box-check"></i> View
                                </a>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-default" data-dismiss="modal">Close</button>
            </div>
        </div>
    </div>
</div>
"""

MATCH_CONFIG = """{{ record.match_config|linebreaksbr }}"""

def actual_fields():
    """Convenience function to conditionally toggle columns based on settings."""
    # Use NetBox settings access
    from extras.plugins import get_plugin_config
    plugin_settings = get_plugin_config('netbox_golden_config', {})
    active_fields = ["pk", "name"] # Start with core fields
    if plugin_settings.get('enable_backup', False):
        active_fields.append("backup_last_success_date")
    if plugin_settings.get('enable_intended', False):
        active_fields.append("intended_last_success_date")
    if plugin_settings.get('enable_compliance', False):
        active_fields.append("compliance_last_success_date")
    # Add actions if any feature requiring it is enabled
    if any([plugin_settings.get(key, False) for key in ['enable_backup', 'enable_intended', 'enable_compliance', 'enable_sotagg', 'enable_postprocessing']]):
        active_fields.append("actions")
    return tuple(active_fields)


# Custom Columns (adapt if needed)
class PercentageColumn(tables.Column):
    """Column used to display percentage."""
    def render(self, value):
        return f"{value} %" if value is not None else "N/A"

class ComplianceColumn(tables.Column):
    """Column used to display config compliance status (True/False/None)."""
    def render(self, value):
        if value == 1:
            return format_html('<span class="text-success"><i class="mdi mdi-check-bold"></i></span>')
        elif value == 0:
            return format_html('<span class="text-danger"><i class="mdi mdi-close-thick"></i></span>')
        else: # value is None or other
            return format_html('<span class="text-muted"><i class="mdi mdi-minus-circle-outline"></i></span>')

# Tables
class ConfigComplianceTable(NetBoxTable):
    """Table for listing Device entries and their ConfigCompliance status."""
    # Use NetBox columns
    pk = columns.ToggleColumn()
    # Link to the device compliance tab view
    device = tables.TemplateColumn(
        template_code='<a href="{% url \'plugins:netbox_golden_config:configcompliance_devicetab\' pk=record.device %}?tab=golden_config_compliance"><strong>{{ record.device__name }}</strong></a>',
        verbose_name='Device'
    )
    # Dynamic feature columns
    # Note: Dynamically adding columns in __init__ can be complex with NetBoxTable's meta options.
    # It might be simpler to define a fixed set of potential columns or handle this in the view/template.
    # Placeholder for dynamic columns (implementation needed):
    # feature_col_1 = ComplianceColumn(verbose_name="Feature 1")
    # feature_col_2 = ComplianceColumn(verbose_name="Feature 2")
    # ...

    class Meta(NetBoxTable.Meta):
        model = models.ConfigCompliance
        # Fields will be determined dynamically or pre-defined
        fields = ('pk', 'device') # Start with base fields
        default_columns = ('pk', 'device') # Add dynamic feature columns here if known

    def __init__(self, *args, extra_columns=None, **kwargs):
         """Add dynamic feature columns."""
         base_columns = list(self.Meta.fields)
         default_columns = list(self.Meta.default_columns)

         # Get distinct features from the current queryset if possible, or all features
         features = []
         if 'queryset' in kwargs:
             # This relies on the pivoted queryset structure passed from the view
             if kwargs['queryset'].exists():
                  # Infer features from the keys of the first pivoted item, excluding known keys
                  known_keys = {'device', 'device__name', 'pk'}
                  features = [k for k in kwargs['queryset'][0].keys() if k not in known_keys]
         else:
             # Fallback: Get all features if queryset is not available at init
             features = list(models.ComplianceFeature.objects.values_list('slug', flat=True))

         # Define columns dynamically
         for feature_slug in sorted(features):
              col_name = feature_slug.replace('-', '_') # Sanitize slug for attribute name
              self.base_columns[col_name] = ComplianceColumn(verbose_name=feature_slug.replace('-', ' ').title())
              if col_name not in base_columns:
                   base_columns.append(col_name)
              if col_name not in default_columns:
                    default_columns.append(col_name)


         # Update Meta for the instance
         self.Meta.fields = tuple(base_columns)
         self.Meta.default_columns = tuple(default_columns)

         super().__init__(*args, extra_columns=extra_columns, **kwargs)


class ConfigComplianceGlobalFeatureTable(NetBoxTable):
    """Table for feature compliance report."""
    name = tables.Column(accessor="rule__feature__slug", verbose_name="Feature")
    count = tables.Column(accessor="count", verbose_name="Total")
    compliant = tables.Column(accessor="compliant", verbose_name="Compliant")
    non_compliant = tables.Column(accessor="non_compliant", verbose_name="Non-Compliant")
    comp_percent = PercentageColumn(accessor="comp_percent", verbose_name="Compliance (%)")

    class Meta(NetBoxTable.Meta):
        model = models.ConfigCompliance # Use underlying model for context
        fields = ["name", "count", "compliant", "non_compliant", "comp_percent"]
        default_columns = fields


class ConfigComplianceDeleteTable(NetBoxTable):
    """Table for device compliance report bulk delete confirmation."""
    device = tables.Column(accessor="device__name", verbose_name="Device Name", linkify=True) # Linkify device
    feature = tables.Column(accessor="rule__feature__name", verbose_name="Feature")
    # Removed pk toggle for delete confirmation table

    class Meta(NetBoxTable.Meta):
        model = models.ConfigCompliance
        fields = ("device", "feature")
        default_columns = fields


class DeleteGoldenConfigTable(NetBoxTable):
    """Table used in bulk delete confirmation for GoldenConfig."""
    pk = columns.ToggleColumn()
    device = tables.Column(linkify=True) # Linkify device

    class Meta(NetBoxTable.Meta):
        model = models.GoldenConfig
        fields = ('pk', 'device') # Only show device
        default_columns = fields


class GoldenConfigTable(NetBoxTable):
    """Table to display Config Management Status."""
    pk = columns.ToggleColumn()
    name = tables.Column(accessor='device', verbose_name="Device", linkify=True) # Link directly to device

    # Conditional columns based on settings
    # These need access to plugin settings, which might be tricky in a Table class.
    # Consider handling conditional display in the template or view.
    # Or, define all columns and hide/show based on context passed to the template.
    backup_last_success_date = columns.DateTimeColumn(verbose_name="Backup Status")
    intended_last_success_date = columns.DateTimeColumn(verbose_name="Intended Status")
    compliance_last_success_date = columns.DateTimeColumn(verbose_name="Compliance Status")

    actions = columns.TemplateColumn(
        template_code=ALL_ACTIONS,
        verbose_name="Actions",
        attrs={"td": {"class": "text-right text-nowrap noprint"}}, # NetBox styling
        extra_context=CONFIG_FEATURES # Pass settings flags
    )

    def render_backup_last_success_date(self, record, value):
        return self._render_status_date(record, value, "backup")

    def render_intended_last_success_date(self, record, value):
        return self._render_status_date(record, value, "intended")

    def render_compliance_last_success_date(self, record, value):
        return self._render_status_date(record, value, "compliance")

    def _render_status_date(self, record, value, prefix):
        """Helper to render status date with color."""
        last_success = getattr(record, f"{prefix}_last_success_date", None)
        last_attempt = getattr(record, f"{prefix}_last_attempt_date", None)

        if not last_attempt:
            return columns.CLEAR_CHECKBOX # Or '—' or other placeholder
        if last_success == last_attempt:
            # Using <span> with text-success for color
            return format_html('<span class="text-success">{}</span>', columns.DateTimeColumn().render(last_success))
        # Using <span> with text-danger for color
        rendered_date = columns.DateTimeColumn().render(last_success) if last_success else "Never"
        return format_html('<span class="text-danger">{}</span>', rendered_date)


    class Meta(NetBoxTable.Meta):
        model = models.GoldenConfig
        fields = actual_fields() # Dynamically set fields based on settings
        default_columns = actual_fields()


class ComplianceFeatureTable(NetBoxTable):
    """Table to display Compliance Features."""
    pk = columns.ToggleColumn()
    name = tables.Column(linkify=True)
    actions = columns.ActionsColumn(actions=('edit', 'delete')) # NetBox standard actions

    class Meta(NetBoxTable.Meta):
        model = models.ComplianceFeature
        fields = ("pk", "name", "slug", "description", "tags", "actions") # Add tags if using TagsMixin
        default_columns = ("pk", "name", "slug", "description", "tags", "actions")


class ComplianceRuleTable(NetBoxTable):
    """Table to display Compliance Rules."""
    pk = columns.ToggleColumn()
    feature = tables.Column(linkify=True)
    platform = tables.Column(linkify=True)
    match_config = columns.TemplateColumn(template_code=MATCH_CONFIG)
    config_ordered = columns.BooleanColumn()
    custom_compliance = columns.BooleanColumn()
    config_remediation = columns.BooleanColumn()
    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = models.ComplianceRule
        fields = (
            "pk", "feature", "platform", "description", "config_ordered",
            "match_config", "config_type", "custom_compliance", "config_remediation", "tags", "actions" # Add tags
        )
        default_columns = (
            "pk", "feature", "platform", "description", "config_ordered",
            "match_config", "config_type", "custom_compliance", "config_remediation", "tags", "actions"
        )


class ConfigRemoveTable(NetBoxTable):
    """Table to display Config Removals."""
    pk = columns.ToggleColumn()
    name = tables.Column(linkify=True)
    platform = tables.Column(linkify=True)
    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = models.ConfigRemove
        fields = ("pk", "name", "platform", "description", "regex", "tags", "actions") # Add tags
        default_columns = ("pk", "name", "platform", "description", "regex", "tags", "actions")


class ConfigReplaceTable(NetBoxTable):
    """Table to display Config Replacements."""
    pk = columns.ToggleColumn()
    name = tables.Column(linkify=True)
    platform = tables.Column(linkify=True)
    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = models.ConfigReplace
        fields = ("pk", "name", "platform", "description", "regex", "replace", "tags", "actions") # Add tags
        default_columns = ("pk", "name", "platform", "description", "regex", "replace", "tags", "actions")


class GoldenConfigSettingTable(NetBoxTable):
    """Table for GoldenConfigSetting list view."""
    pk = columns.ToggleColumn()
    name = tables.Column(linkify=True)
    weight = tables.Column()
    # Dynamic Group replaced - show scope info instead
    # Option 1: Tags
    # scope_tags = columns.TagColumn(url_name='plugins:netbox_golden_config:goldenconfigsetting_list')
    # Option 2: Filter
    scope_filter = columns.JSONColumn() # Display filter as JSON
    # Maybe add a count of scoped devices? Requires annotation in the view.
    # device_count = tables.Column(verbose_name="Scoped Devices")

    # Show boolean indicators for linked repos
    backup_repository = columns.BooleanColumn(verbose_name="Backup Repo")
    intended_repository = columns.BooleanColumn(verbose_name="Intended Repo")
    jinja_repository = columns.BooleanColumn(verbose_name="Jinja Repo")
    sot_agg_query = columns.BooleanColumn(verbose_name="GraphQL Query")

    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = models.GoldenConfigSetting
        fields = (
            "pk", "name", "weight", "description",
            # "scope_tags", # Option 1
            "scope_filter", # Option 2
            # "device_count", # Add if annotated
            "backup_repository", "intended_repository", "jinja_repository", "sot_agg_query",
            "tags", "actions" # Add tags
        )
        default_columns = fields

    # BooleanColumn renders True/False, no custom render needed unless specific icon desired
    # def render_backup_repository(...):
    # def render_intended_repository(...):
    # def render_jinja_repository(...):


class RemediationSettingTable(NetBoxTable):
    """Table to display RemediationSetting Rules."""
    pk = columns.ToggleColumn()
    platform = tables.Column(linkify=True)
    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = models.RemediationSetting
        fields = ("pk", "platform", "remediation_type", "tags", "actions") # Add tags
        default_columns = ("pk", "platform", "remediation_type", "tags", "actions")


class ConfigPlanTable(NetBoxTable): # Use NetBoxTable, Status handling might need columns.StatusColumn
    """Table to display Config Plans."""
    pk = columns.ToggleColumn()
    device = tables.Column(linkify=True)
    created = columns.DateTimeColumn() # Standard datetime column
    # Link to Job Results (adapt URL name)
    plan_result = columns.TemplateColumn(
        template_code='<a href="{% url \'extras:jobresult\' pk=record.plan_result.pk %}"><i class="mdi mdi-clipboard-text-play-outline"></i></a>',
        verbose_name="Plan Result"
    )
    deploy_result = columns.TemplateColumn(
        template_code="""
        {% if record.deploy_result %}
            <a href="{% url 'extras:jobresult' pk=record.deploy_result.pk %}"><i class="mdi mdi-clipboard-text-play-outline"></i></a>
        {% else %}
            &mdash;
        {% endif %}
        """,
        verbose_name="Deploy Result"
    )
    config_set = columns.TemplateColumn(
         template_code=CONFIG_SET_BUTTON,
         verbose_name="Config Set",
         orderable=False
    )
    tags = columns.TagColumn(url_name='plugins:netbox_golden_config:configplan_list') # Use NetBox TagColumn
    status = columns.StatusColumn() # Use NetBox StatusColumn
    feature = columns.ManyToManyColumn(linkify_items=True) # Display M2M features
    actions = columns.ActionsColumn(actions=('edit', 'delete')) # Add standard actions

    class Meta(NetBoxTable.Meta):
        model = models.ConfigPlan
        fields = (
            "pk", "device", "created", "plan_type", "feature", "change_control_id",
            "change_control_url", "plan_result", "deploy_result", "config_set", "status", "tags", "actions"
        )
        default_columns = (
            "pk", "device", "created", "plan_type", "feature", "change_control_id",
            "plan_result", "deploy_result", "config_set", "status", "tags", "actions"
        )
