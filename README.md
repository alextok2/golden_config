# golden_config
Removed Files:

datasources.py: Functionality needs reimplementation using NetBox mechanisms.

details.py: Nautobot-specific UI detail view definitions.

All files under migrations/: Need regeneration.

filter_extensions.py: Specific to Nautobot's filter extension points. NetBox filtering is typically done within the FilterSet class itself.

app-config-schema.json: Nautobot specific App configuration schema.

Key Changes Summary:

Base Classes: Replaced Nautobot base classes (NautobotAppConfig, PluginTemplateExtension, NautobotUIViewSet, NautobotModelSerializer, NautobotFilterSet, NautobotModelForm, NautobotBulkEditForm, BaseTable, StatusTableMixin) with their NetBox equivalents (PluginConfig, PluginTemplateExtension (used differently), NetBoxModelViewSet, NetBoxModelSerializer, NetBoxModelFilterSet, standard Django forms with BootstrapMixin, NetBoxTable, columns).

Imports: Updated imports to use NetBox models (dcim.Site, utilities.forms, netbox.views, etc.) and plugin framework components. Replaced Nautobot helper imports with NetBox equivalents or standard Django/Python methods. Nornir plugin imports were conditionally adapted assuming netbox-plugin-nornir.

Dynamic Groups: Removed direct references to DynamicGroup on GoldenConfigSetting. Added placeholder fields (scope_filter JSONField) and manager methods (get_for_device, members_count, members_url) that need concrete implementation based on the chosen scoping mechanism (Tags, Filters). Job filtering logic (get_job_filter) and the Sync job were adapted conceptually.

Settings & Configuration: Adapted access to plugin settings using settings.PLUGINS_CONFIG. Removed Constance-specific logic.

UI Components: Replaced Nautobot PluginTemplateExtension usage with NetBox's method (defining extensions in __init__.py and implementing methods like right_page or tabs). Adapted templates to use NetBox CSS classes, template tags ({% load helpers %}, {% render_table %}), and structure. Removed Nautobot-specific UI files (details.py).

Jobs: Adapted Job base classes (netbox.jobs.Job, JobButtonReceiver), variable types (ObjectVar, MultiObjectVar), and the run method signature (data, commit). Adapted logging to use self.log_* methods. Adapted exception handling for Nornir based on the assumed netbox-plugin-nornir exception type. Removed Nautobot-specific fail_job_on_task_failure. Adapted Job Button receiver conceptually.

Models: Inherited from NetBoxModel and feature mixins (TagsMixin, etc.). Replaced Nautobot-specific fields like StatusField with standard ForeignKey to extras.Status. Adapted to_objectchange removal as NetBox handles change logging differently. Added standard CHOICES attribute to ChoiceSets. Adapted get_absolute_url removal/comments. Added default values to some BooleanField and JSONField instances for database compatibility.

Forms & Filters: Used NetBox form/filter components (BootstrapMixin, NetBoxModelFilterSet, DynamicModel*Field, SlugField, TagFilterField, NetBox widgets). Adapted field names (site instead of location, slugs instead of PKs often). Reworked filter logic where necessary (e.g., search method, device scope filters).

API: Used NetBox API base classes (NetBoxModelViewSet, NetBoxModelSerializer). Used NetBox nested serializers (WritableNestedSerializer). Adapted URL routing using NetBoxRouter. Adapted permission classes.

Signals: Used standard Django signals (post_save, post_migrate). Adapted signal receiver functions to use NetBox models and print/log messages suitable for migrations/startup. Job Button signal logic requires significant review for NetBox UI integration.

Datasources/Migrations: Removed datasources.py and all migration files. These need to be handled specific to the NetBox environment.

Templates: Adapted template inheritance (base/base.html), included NetBox template tags, updated CSS classes for NetBox styling (e.g., panel, btn, table), adapted modal structures, and updated URLs. Included JavaScript for features like ClipboardJS and Diff2HTML assuming they might be loaded by NetBox or need to be included by the plugin.

This adaptation provides a structurally similar plugin for NetBox, but requires significant testing and refinement, especially around Dynamic Group replacement, GraphQL interaction, Nornir plugin integration, Job Button UI, Datasource syncing (if needed), and specific UI behaviors within NetBox templates. Generate new database migrations after applying these changes.

