"""Django urlpatterns declaration for netbox_golden_config app."""

from django.urls import path
# Use NetBox viewset router if using DRF ViewSets, otherwise standard Django URLs
# from netbox.api.routers import NetBoxRouter
from netbox.views import generic # Use NetBox generic views
from . import views # Use local views

# Use standard Django URL patterns for non-API views
urlpatterns = [
    # Golden Config Views
    path("golden-config/", views.GoldenConfigListView.as_view(), name="goldenconfig_list"),
    path("golden-config/delete/", views.GoldenConfigBulkDeleteView.as_view(), name="goldenconfig_bulk_delete"),
    path("golden-config/<uuid:pk>/", views.GoldenConfigView.as_view(), name="goldenconfig"),
    path("golden-config/<uuid:pk>/delete/", views.GoldenConfigDeleteView.as_view(), name="goldenconfig_delete"),
    path("golden-config/<uuid:pk>/changelog/", generic.ObjectChangeLogView.as_view(), name="goldenconfig_changelog", kwargs={"model": models.GoldenConfig}),
    # Modal/Detail Action Views
    path("golden-config/<uuid:pk>/backup/", views.GoldenConfigActionView.as_view(), name="goldenconfig_backup", kwargs={'action_name': 'backup'}),
    path("golden-config/<uuid:pk>/intended/", views.GoldenConfigActionView.as_view(), name="goldenconfig_intended", kwargs={'action_name': 'intended'}),
    path("golden-config/<uuid:pk>/compliance/", views.GoldenConfigActionView.as_view(), name="goldenconfig_compliance", kwargs={'action_name': 'compliance'}),
    path("golden-config/<uuid:pk>/sotagg/", views.GoldenConfigActionView.as_view(), name="goldenconfig_sotagg", kwargs={'action_name': 'sotagg'}),
    path("golden-config/<uuid:pk>/postprocessing/", views.GoldenConfigActionView.as_view(), name="goldenconfig_postprocessing", kwargs={'action_name': 'postprocessing'}),

    # Config Compliance Views
    path("config-compliance/", views.ConfigComplianceListView.as_view(), name="configcompliance_list"),
    path("config-compliance/delete/", views.ConfigComplianceBulkDeleteView.as_view(), name="configcompliance_bulk_delete"),
    path("config-compliance/<uuid:pk>/", views.ConfigComplianceView.as_view(), name="configcompliance"),
    path("config-compliance/<uuid:pk>/delete/", views.ConfigComplianceDeleteView.as_view(), name="configcompliance_delete"),
    path("config-compliance/<uuid:pk>/changelog/", generic.ObjectChangeLogView.as_view(), name="configcompliance_changelog", kwargs={"model": models.ConfigCompliance}),
    path("config-compliance/overview/", views.ConfigComplianceOverview.as_view(), name="configcompliance_overview"),
    # Device Tab View (needs a corresponding view function/class)
    path("devices/<uuid:pk>/compliance-tab/", views.ConfigComplianceDeviceTabView.as_view(), name="configcompliance_devicetab"), # Example URL

    # Compliance Feature Views
    path("compliance-features/", views.ComplianceFeatureListView.as_view(), name="compliancefeature_list"),
    path("compliance-features/add/", views.ComplianceFeatureEditView.as_view(), name="compliancefeature_add"),
    path("compliance-features/import/", generic.BulkImportView.as_view(), name="compliancefeature_import", kwargs={"model": models.ComplianceFeature}),
    path("compliance-features/edit/", views.ComplianceFeatureBulkEditView.as_view(), name="compliancefeature_bulk_edit"),
    path("compliance-features/delete/", views.ComplianceFeatureBulkDeleteView.as_view(), name="compliancefeature_bulk_delete"),
    path("compliance-features/<slug:slug>/", views.ComplianceFeatureView.as_view(), name="compliancefeature"), # Use slug for detail view if preferred
    path("compliance-features/<slug:slug>/edit/", views.ComplianceFeatureEditView.as_view(), name="compliancefeature_edit"),
    path("compliance-features/<slug:slug>/delete/", views.ComplianceFeatureDeleteView.as_view(), name="compliancefeature_delete"),
    path("compliance-features/<slug:slug>/changelog/", generic.ObjectChangeLogView.as_view(), name="compliancefeature_changelog", kwargs={"model": models.ComplianceFeature}),

    # Compliance Rule Views
    path("compliance-rules/", views.ComplianceRuleListView.as_view(), name="compliancerule_list"),
    path("compliance-rules/add/", views.ComplianceRuleEditView.as_view(), name="compliancerule_add"),
    path("compliance-rules/import/", generic.BulkImportView.as_view(), name="compliancerule_import", kwargs={"model": models.ComplianceRule}),
    path("compliance-rules/edit/", views.ComplianceRuleBulkEditView.as_view(), name="compliancerule_bulk_edit"),
    path("compliance-rules/delete/", views.ComplianceRuleBulkDeleteView.as_view(), name="compliancerule_bulk_delete"),
    path("compliance-rules/<uuid:pk>/", views.ComplianceRuleView.as_view(), name="compliancerule"),
    path("compliance-rules/<uuid:pk>/edit/", views.ComplianceRuleEditView.as_view(), name="compliancerule_edit"),
    path("compliance-rules/<uuid:pk>/delete/", views.ComplianceRuleDeleteView.as_view(), name="compliancerule_delete"),
    path("compliance-rules/<uuid:pk>/changelog/", generic.ObjectChangeLogView.as_view(), name="compliancerule_changelog", kwargs={"model": models.ComplianceRule}),

    # Golden Config Setting Views
    path("golden-config-settings/", views.GoldenConfigSettingListView.as_view(), name="goldenconfigsetting_list"),
    path("golden-config-settings/add/", views.GoldenConfigSettingEditView.as_view(), name="goldenconfigsetting_add"),
    path("golden-config-settings/import/", generic.BulkImportView.as_view(), name="goldenconfigsetting_import", kwargs={"model": models.GoldenConfigSetting}),
    path("golden-config-settings/edit/", views.GoldenConfigSettingBulkEditView.as_view(), name="goldenconfigsetting_bulk_edit"),
    path("golden-config-settings/delete/", views.GoldenConfigSettingBulkDeleteView.as_view(), name="goldenconfigsetting_bulk_delete"),
    path("golden-config-settings/<slug:slug>/", views.GoldenConfigSettingView.as_view(), name="goldenconfigsetting"), # Use slug if preferred
    path("golden-config-settings/<slug:slug>/edit/", views.GoldenConfigSettingEditView.as_view(), name="goldenconfigsetting_edit"),
    path("golden-config-settings/<slug:slug>/delete/", views.GoldenConfigSettingDeleteView.as_view(), name="goldenconfigsetting_delete"),
    path("golden-config-settings/<slug:slug>/changelog/", generic.ObjectChangeLogView.as_view(), name="goldenconfigsetting_changelog", kwargs={"model": models.GoldenConfigSetting}),

    # Config Remove Views
    path("config-removes/", views.ConfigRemoveListView.as_view(), name="configremove_list"),
    path("config-removes/add/", views.ConfigRemoveEditView.as_view(), name="configremove_add"),
    path("config-removes/import/", generic.BulkImportView.as_view(), name="configremove_import", kwargs={"model": models.ConfigRemove}),
    path("config-removes/edit/", views.ConfigRemoveBulkEditView.as_view(), name="configremove_bulk_edit"),
    path("config-removes/delete/", views.ConfigRemoveBulkDeleteView.as_view(), name="configremove_bulk_delete"),
    path("config-removes/<uuid:pk>/", views.ConfigRemoveView.as_view(), name="configremove"),
    path("config-removes/<uuid:pk>/edit/", views.ConfigRemoveEditView.as_view(), name="configremove_edit"),
    path("config-removes/<uuid:pk>/delete/", views.ConfigRemoveDeleteView.as_view(), name="configremove_delete"),
    path("config-removes/<uuid:pk>/changelog/", generic.ObjectChangeLogView.as_view(), name="configremove_changelog", kwargs={"model": models.ConfigRemove}),

    # Config Replace Views
    path("config-replaces/", views.ConfigReplaceListView.as_view(), name="configreplace_list"),
    path("config-replaces/add/", views.ConfigReplaceEditView.as_view(), name="configreplace_add"),
    path("config-replaces/import/", generic.BulkImportView.as_view(), name="configreplace_import", kwargs={"model": models.ConfigReplace}),
    path("config-replaces/edit/", views.ConfigReplaceBulkEditView.as_view(), name="configreplace_bulk_edit"),
    path("config-replaces/delete/", views.ConfigReplaceBulkDeleteView.as_view(), name="configreplace_bulk_delete"),
    path("config-replaces/<uuid:pk>/", views.ConfigReplaceView.as_view(), name="configreplace"),
    path("config-replaces/<uuid:pk>/edit/", views.ConfigReplaceEditView.as_view(), name="configreplace_edit"),
    path("config-replaces/<uuid:pk>/delete/", views.ConfigReplaceDeleteView.as_view(), name="configreplace_delete"),
    path("config-replaces/<uuid:pk>/changelog/", generic.ObjectChangeLogView.as_view(), name="configreplace_changelog", kwargs={"model": models.ConfigReplace}),

    # Remediation Setting Views
    path("remediation-settings/", views.RemediationSettingListView.as_view(), name="remediationsetting_list"),
    path("remediation-settings/add/", views.RemediationSettingEditView.as_view(), name="remediationsetting_add"),
    path("remediation-settings/import/", generic.BulkImportView.as_view(), name="remediationsetting_import", kwargs={"model": models.RemediationSetting}),
    path("remediation-settings/edit/", views.RemediationSettingBulkEditView.as_view(), name="remediationsetting_bulk_edit"),
    path("remediation-settings/delete/", views.RemediationSettingBulkDeleteView.as_view(), name="remediationsetting_bulk_delete"),
    path("remediation-settings/<uuid:pk>/", views.RemediationSettingView.as_view(), name="remediationsetting"),
    path("remediation-settings/<uuid:pk>/edit/", views.RemediationSettingEditView.as_view(), name="remediationsetting_edit"),
    path("remediation-settings/<uuid:pk>/delete/", views.RemediationSettingDeleteView.as_view(), name="remediationsetting_delete"),
    path("remediation-settings/<uuid:pk>/changelog/", generic.ObjectChangeLogView.as_view(), name="remediationsetting_changelog", kwargs={"model": models.RemediationSetting}),

    # Config Plan Views
    path("config-plans/", views.ConfigPlanListView.as_view(), name="configplan_list"),
    path("config-plans/add/", views.ConfigPlanEditView.as_view(), name="configplan_add"), # If direct add is needed
    path("config-plans/import/", generic.BulkImportView.as_view(), name="configplan_import", kwargs={"model": models.ConfigPlan}),
    path("config-plans/edit/", views.ConfigPlanBulkEditView.as_view(), name="configplan_bulk_edit"),
    path("config-plans/delete/", views.ConfigPlanBulkDeleteView.as_view(), name="configplan_bulk_delete"),
    path("config-plans/<uuid:pk>/", views.ConfigPlanView.as_view(), name="configplan"),
    path("config-plans/<uuid:pk>/edit/", views.ConfigPlanEditView.as_view(), name="configplan_edit"),
    path("config-plans/<uuid:pk>/delete/", views.ConfigPlanDeleteView.as_view(), name="configplan_delete"),
    path("config-plans/<uuid:pk>/changelog/", generic.ObjectChangeLogView.as_view(), name="configplan_changelog", kwargs={"model": models.ConfigPlan}),
    # Bulk Deploy View
    path("config-plans/bulk-deploy/", views.ConfigPlanBulkDeployView.as_view(), name="configplan_bulk_deploy"),

    # Tool Views
    path("generate-intended-config/", views.GenerateIntendedConfigToolView.as_view(), name="generate_intended_config"),
    # path("docs/", RedirectView.as_view(url=static("netbox_golden_config/docs/index.html")), name="docs"), # Adapt docs URL
]