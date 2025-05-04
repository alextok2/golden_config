"""Signal helpers."""

from django.apps import apps as global_apps
from django.db.models.signals import post_save # Standard Django signal
from django.dispatch import receiver
from utilities.choices import ColorChoices # NetBox choices
from dcim.models import Platform # NetBox model
from extras.models import Status, Job, JobButton, ContentType # NetBox models

from . import models # Use local models

def post_migrate_create_statuses(sender, apps=global_apps, **kwargs):  # pylint: disable=unused-argument
    """Callback function for post_migrate() -- create Status records."""
    # Status = apps.get_model("extras", "Status") # Use direct import now
    # ContentType = apps.get_model("contenttypes", "ContentType") # Use direct import now
    status_model = apps.get_model("netbox_golden_config", "ConfigPlan") # Get the model from *this* app
    content_type = ContentType.objects.get_for_model(status_model)

    # Ensure Status model has necessary fields if different from Nautobot
    status_data = [
        {"name": "Approved", "color": ColorChoices.COLOR_GREEN, "description": "Config plan is approved"},
        {"name": "Not Approved", "color": ColorChoices.COLOR_RED, "description": "Config plan is not approved"},
        {"name": "In Progress", "color": ColorChoices.COLOR_GREY, "description": "Config deployment has started and not completed or failed"},
        {"name": "Completed", "color": ColorChoices.COLOR_DARK_GREY, "description": "Config deploy has been successfully completed"},
        {"name": "Failed", "color": ColorChoices.COLOR_DARK_RED, "description": "Config deploy has failed"},
    ]

    for config in status_data:
        status, created = Status.objects.get_or_create(
            name=config["name"],
            defaults={
                'color': config['color'],
                'description': config['description'],
                # Add other fields if NetBox Status model requires them
            }
        )
        # Associate the status with the ConfigPlan content type
        status.content_types.add(content_type)
        if created:
             print(f'Created Status "{config["name"]}"') # Use print for migrations or logging

def post_migrate_create_job_button(sender, apps=global_apps, **kwargs):  # pylint: disable=unused-argument
    """Callback function for post_migrate() -- create JobButton records."""
    # Job = apps.get_model("extras", "Job") # Use direct import
    # JobButton = apps.get_model("extras", "JobButton") # Use direct import
    # ContentType = apps.get_model("contenttypes", "ContentType") # Use direct import

    # Job Buttons work differently in NetBox UI. This logic might need removal or complete rework.
    # Typically, buttons are added via navigation.py or directly in templates.
    # If JobButton model *is* used for API/backend logic, adapt this.

    # Example check (needs verification against NetBox Job model structure):
    try:
        # Ensure the Job class_path matches the one registered in NetBox
        deploy_job = Job.objects.get(job_class_name="netbox_golden_config.jobs.DeployConfigPlanJobButtonReceiver")
    except Job.DoesNotExist:
        print("Deploy Config Plan Job not found, skipping Job Button creation.") # Use print for migrations
        return

    configplan_model = apps.get_model("netbox_golden_config", "ConfigPlan")
    configplan_type = ContentType.objects.get_for_model(configplan_model)

    # Check if JobButton model exists and has similar fields in NetBox
    if hasattr(JobButton, 'objects'):
        job_button, created = JobButton.objects.get_or_create(
            name="Deploy Config Plan",
            job=deploy_job, # Assuming JobButton relates to Job
            defaults={
                "text": "Deploy",
                "button_class": "primary", # Check NetBox CSS classes
                # Add other necessary defaults for NetBox JobButton
            },
        )
        if job_button: # Check if button object was created/retrieved
             job_button.content_types.set([configplan_type])
             if created:
                  print("Created Job Button 'Deploy Config Plan'")
    else:
         print("JobButton model not found or incompatible, skipping creation.")


@receiver(post_save, sender=models.ConfigCompliance)
def config_compliance_platform_cleanup(sender, instance, **kwargs):  # pylint: disable=unused-argument
    """Signal helper to delete any orphaned ConfigCompliance objects. Caused by device platform changes."""
    if instance.device and instance.device.platform:
        cc_wrong_platform = models.ConfigCompliance.objects.filter(device=instance.device).exclude(
            rule__platform=instance.device.platform
        )
        count = cc_wrong_platform.count()
        if count > 0:
            cc_wrong_platform.delete()
            print(f"Deleted {count} orphaned ConfigCompliance objects for device {instance.device.name} due to platform change.") # Use print or logging
    elif not instance.device:
         # Handle case where instance.device might be None if signal triggered unexpectedly
         print(f"Warning: config_compliance_platform_cleanup triggered for ConfigCompliance pk={instance.pk} with no associated device.")

