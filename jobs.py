"""Jobs to run backups, intended config, and compliance."""

# pylint: disable=too-many-function-args,logging-fstring-interpolation
# TODO: Remove the following ignore, added to be able to pass pylint in CI.
# pylint: disable=arguments-differ

from datetime import datetime

from django.utils.timezone import make_aware
from netbox.jobs import Job, JobButtonReceiver, BooleanVar, ChoiceVar, MultiObjectVar, ObjectVar, StringVar, TextVar # NetBox Jobs base
# NetBox Models
from dcim.models import Device, DeviceType, Location, Manufacturer, Platform, Rack, RackGroup, Site # Use Site
from extras.models import Tag, Status, DynamicGroup, GitRepository, GraphQLQuery, JobResult # NetBox models
from tenancy.models import Tenant, TenantGroup

# Nornir Plugin adaptation
try:
    # Assuming a netbox-plugin-nornir exists
    from netbox_plugin_nornir.plugins.inventory.netbox_orm import NetBoxORMInventory as OrmInventory
    from netbox_plugin_nornir.exceptions import NornirNetBoxException as NornirPluginException
    from netbox_plugin_nornir.utils import register_jobs # Check registration method
except ImportError:
    # Fallback or placeholder if plugin doesn't exist or has different names
    print("WARNING: netbox-plugin-nornir not found or incompatible. Nornir jobs will likely fail.")
    OrmInventory = object # Placeholder
    NornirPluginException = Exception # Placeholder
    def register_jobs(*args): pass # Placeholder

# Nornir core imports remain the same
from nornir import InitNornir
from nornir.core.plugins.inventory import InventoryPluginRegister

# Local imports
from .choices import ConfigPlanTypeChoice # Use local choices
from .exceptions import BackupFailure, ComplianceFailure, IntendedGenerationFailure # Use local exceptions
from .models import ComplianceFeature, ConfigPlan, GoldenConfig # Use local models
from .nornir_plays.config_backup import config_backup
from .nornir_plays.config_compliance import config_compliance
from .nornir_plays.config_deployment import config_deployment
from .nornir_plays.config_intended import config_intended
from .utilities import constant # Use local constants
from .utilities.config_plan import (
    config_plan_default_status,
    generate_config_set_from_compliance_feature,
    generate_config_set_from_manual,
)
# Git utilities might need adaptation based on NetBox Git integration
from .utilities.git import GitRepo
# Helpers need adaptation for Dynamic Group replacement
from .utilities.helper import (
    get_device_to_settings_map,
    get_job_filter,
    # update_dynamic_groups_cache, # Replace with cache update for new scoping mechanism if needed
)

# Register Nornir Inventory - Adapt plugin name if needed
# InventoryPluginRegister.register("netbox-inventory", OrmInventory) # Assuming OrmInventory is the correct class

name = "Golden Configuration"  # pylint: disable=invalid-name


def get_repo_types_for_job(job_name):
    """Logic to determine which repo_types are needed based on job + plugin settings."""
    repo_types = []
    # Use constant utility directly
    if constant.ENABLE_BACKUP and "BackupJob" in job_name:
        repo_types.append("backup_repository")
    if constant.ENABLE_INTENDED and "IntendedJob" in job_name:
        repo_types.extend(["jinja_repository", "intended_repository"])
    if constant.ENABLE_COMPLIANCE and "ComplianceJob" in job_name:
        repo_types.extend(["intended_repository", "backup_repository"])
    if "All" in job_name:
        repo_types.extend(["backup_repository", "jinja_repository", "intended_repository"])
    return repo_types


def get_refreshed_repos(job_obj, repo_types, data=None):
    """Small wrapper to pull latest branch, and return a GitRepo app specific object."""
    # This needs significant change to work without Dynamic Groups.
    # It should iterate through GoldenConfigSettings and find relevant repos based on
    # which settings apply to the devices in the `data` queryset.
    repository_records = set()
    device_qs = data # Assume data is the device queryset

    # Get the mapping of device PKs to their applicable GoldenConfigSetting
    device_setting_map = get_device_to_settings_map(device_qs)
    applicable_settings = set(device_setting_map.values())

    for setting in applicable_settings:
        for repo_type in repo_types:
            repo = getattr(setting, repo_type, None)
            if repo:
                repository_records.add(repo)

    # --- The rest of the function depends on NetBox's Git integration ---
    # Adapt ensure_git_repository and get_repo_from_url_to_path_and_from_branch imports/usage
    from extras.datasources.git import ensure_git_repository # Assuming NetBox path
    # get_repo_from_url_to_path_and_from_branch might not exist, adapt GitRepo instantiation

    repositories = {}
    for repository_record in repository_records:
        try:
            # Ensure repo is cloned/updated
            ensure_git_repository(repository_record, job_obj.log_debug) # Use job logger methods

            # Instantiate GitRepo helper - Adapt based on NetBox GitRepository model and helpers
            # This part is highly dependent on NetBox's Git handling specifics
            repo_path = getattr(repository_record, 'filesystem_path', None) # Check attribute name
            if not repo_path:
                 job_obj.log_warning(f"Filesystem path not found for GitRepository {repository_record.name}. Skipping refresh.")
                 continue

            # Construct the clone URL manually if get_repo_from_url_to_path_and_from_branch isn't available
            # This might need secrets handling if NetBox stores credentials differently
            clone_url = repository_record.remote_url # Basic case, may need token/user injection

            git_repo = GitRepo(
                repo_path,
                clone_url, # Use the constructed URL
                clone_initially=False,
                base_url=repository_record.remote_url,
                nautobot_repo_obj=repository_record,
            )
            commit = False
            # Check provided_contents based on NetBox's implementation
            if hasattr(repository_record, 'provided_contents'):
                if (
                    constant.ENABLE_INTENDED
                    and "netbox_golden_config.intendedconfigs" in repository_record.provided_contents # Adapt content identifier if needed
                ):
                    commit = True
                if (
                    constant.ENABLE_BACKUP
                    and "netbox_golden_config.backupconfigs" in repository_record.provided_contents # Adapt content identifier if needed
                ):
                    commit = True
            else:
                 job_obj.log_warning(f"GitRepository {repository_record.name} does not have 'provided_contents'. Assuming commit=True for relevant types based on settings.")
                 # Fallback logic if provided_contents isn't available
                 if constant.ENABLE_INTENDED and repo_type == "intended_repository": commit = True
                 if constant.ENABLE_BACKUP and repo_type == "backup_repository": commit = True


            repositories[str(repository_record.id)] = {"repo_obj": git_repo, "to_commit": commit}
        except Exception as e:
             job_obj.log_failure(f"Failed to refresh repository {repository_record.name}: {e}")
             # Decide whether to continue or raise based on `fail_job_on_task_failure`

    return repositories


def gc_repo_prep(job, data):
    """Prepare Golden Config git repos for work."""
    job.log_info("Compiling device data for GC job.", grouping="Get Job Filter")
    job.qs = get_job_filter(data) # Assumes get_job_filter is adapted
    job.log_info(f"In scope device count for this job: {job.qs.count()}", grouping="Get Job Filter")
    job.log_info("Mapping device(s) to GC Settings.", grouping="Device to Settings Map")
    job.device_to_settings_map = get_device_to_settings_map(queryset=job.qs) # Assumes get_device_to_settings_map is adapted
    gitrepo_types = list(set(get_repo_types_for_job(job.__class__.__name__))) # Use class name directly
    job.log_info(
        f"Repository types to sync: {', '.join(sorted(gitrepo_types))}",
        grouping="GC Repo Syncs",
    )
    current_repos = get_refreshed_repos(job_obj=job, repo_types=gitrepo_types, data=job.qs)
    return current_repos


def gc_repo_push(job, current_repos, commit_message=""):
    """Push any work from worker to git repos in Job."""
    now = make_aware(datetime.now())
    job.log_info(
        f"Finished the {job.Meta.name} job execution.",
        grouping="GC After Run",
    )
    if current_repos:
        for _, repo in current_repos.items():
            if repo["to_commit"]:
                job.log_info(
                    f"Pushing {job.Meta.name} results to repo {repo['repo_obj'].base_url}.",
                    grouping="GC Repo Commit and Push",
                )
                if not commit_message:
                    commit_message = f"{job.Meta.name.upper()} JOB {now}"

                try:
                     repo["repo_obj"].commit_with_added(commit_message)
                     repo["repo_obj"].push()
                     job.log_success(
                         f'{repo["repo_obj"].nautobot_repo_obj.name}: the new Git repository hash is "{repo["repo_obj"].head}"',
                         obj=repo["repo_obj"].nautobot_repo_obj, # Pass NetBox object
                         grouping="GC Repo Commit and Push",
                     )
                except Exception as e:
                     job.log_failure(
                          f"Failed to commit/push to {repo['repo_obj'].nautobot_repo_obj.name}: {e}",
                          obj=repo["repo_obj"].nautobot_repo_obj,
                           grouping="GC Repo Commit and Push",
                      )
                     # Optionally raise based on fail_job_on_task_failure


def gc_repos(func):
    """Decorator used for handle repo syncing, commiting, and pushing."""
    def gc_repo_wrapper(self, data, commit): # NetBox Jobs pass data and commit differently
        """Decorator used for handle repo syncing, commiting, and pushing."""
        # Adapt data extraction if needed. NetBox passes data dict directly.
        job_data = data
        current_repos = gc_repo_prep(job=self, data=job_data)
        try:
            # Pass job_data and commit status to the decorated function
            func(self, job_data, commit)
        except NornirPluginException as error: # Use adapted Nornir exception
            error_msg = f"`E3001:` General Exception handler, original error message ```{error}```"
            self.log_failure(error_msg)
            # NetBox jobs typically handle failure based on log_failure/log_warning calls
            # Re-raising might stop the job abruptly depending on NetBox version.
            # Consider just logging failure unless job failure is explicitly desired here.
            # if job_data.get("fail_job_on_task_failure"):
            #    raise NornirPluginException(error_msg) from error
        except Exception as error:
             error_msg = f"`E3001:` Unhandled Exception: ```{error}```"
             self.log_failure(error_msg)
             # if job_data.get("fail_job_on_task_failure"):
             #    raise NornirPluginException(error_msg) from error

        finally:
            # Use commit status passed by NetBox job runner
            if commit:
                 gc_repo_push(job=self, current_repos=current_repos, commit_message=job_data.get("commit_message"))
            else:
                 self.log_info("Commit set to False, skipping Git push.")

    return gc_repo_wrapper


class FormEntry:
    """Class definition to use as Mixin for NetBox Job form definitions."""
    # Use NetBox field types (MultiObjectVar needs `model` directly)
    # Ensure querysets point to NetBox models
    tenant_group = MultiObjectVar(model=TenantGroup, required=False)
    tenant = MultiObjectVar(model=Tenant, required=False)
    site = MultiObjectVar(model=Site, required=False) # Use Site
    location = MultiObjectVar(model=Location, required=False) # Keep if nested locations used
    rack_group = MultiObjectVar(model=RackGroup, required=False)
    rack = MultiObjectVar(model=Rack, required=False)
    role = MultiObjectVar(model=Role, queryset=Role.objects.filter(content_types__model="device"), required=False)
    manufacturer = MultiObjectVar(model=Manufacturer, required=False)
    platform = MultiObjectVar(model=Platform, required=False)
    device_type = MultiObjectVar(model=DeviceType, required=False) # display_field handled by default
    device = MultiObjectVar(model=Device, required=False)
    tags = MultiObjectVar( # Adapt Tag usage if needed
        model=Tag, required=False, display_field="name", queryset=Tag.objects.filter(content_types__model="device")
    )
    status = MultiObjectVar( # Adapt Status usage
        model=Status, required=False, queryset=Status.objects.filter(content_types__model="device"), display_field="name", label="Device Status"
    )
    debug = BooleanVar(description="Enable for more verbose debug logging")


class GoldenConfigJobMixin(Job):
    """Reused mixin to be able to set defaults for instance attributes in all GC jobs."""
    # fail_job_on_task_failure = BooleanVar(description="If any tasks for any device fails, fail the entire job result.") # NetBox jobs fail based on log_failure
    commit_message = StringVar(
        label="Git commit message",
        required=False,
        description=r"If empty, defaults to `{job.Meta.name.upper()} JOB {now}`.",
        min_length=2,
        max_length=72,
    )

    # NetBox Jobs don't typically initialize instance variables like this in __init__
    # self.qs = None
    # self.device_to_settings_map = {}
    # Use self.logger provided by NetBox Job base class

    class Meta:
        commit_default = True # Standard NetBox attribute for commit control


class ComplianceJob(GoldenConfigJobMixin, FormEntry):
    """Job to to run the compliance engine."""

    class Meta(GoldenConfigJobMixin.Meta): # Inherit Meta
        name = "Perform Configuration Compliance"
        description = "Run configuration compliance on your network infrastructure."
        has_sensitive_variables = False # NetBox uses this pattern

    @gc_repos
    def run(self, data, commit): # NetBox jobs pass data and commit
        """Run config compliance report script."""
        self.logger.warning("Starting config compliance nornir play.") # Use self.logger
        if not constant.ENABLE_COMPLIANCE:
            msg = "Compliance is disabled in application settings."
            self.logger.error(msg) # Use self.logger
            raise NornirPluginException(msg) # Raise exception to potentially fail job
        config_compliance(self) # Pass self (the job instance)


class IntendedJob(GoldenConfigJobMixin, FormEntry):
    """Job to to run generation of intended configurations."""

    class Meta(GoldenConfigJobMixin.Meta): # Inherit Meta
        name = "Generate Intended Configurations"
        description = "Generate the configuration for your intended state."
        has_sensitive_variables = False

    @gc_repos
    def run(self, data, commit): # NetBox jobs pass data and commit
        """Run config generation script."""
        self.logger.debug("Building device settings mapping and running intended config nornir play.")
        if not constant.ENABLE_INTENDED:
             msg = "Intended Generation is disabled in application settings."
             self.logger.error(msg)
             raise NornirPluginException(msg)
        config_intended(self)


class BackupJob(GoldenConfigJobMixin, FormEntry):
    """Job to to run the backup job."""

    class Meta(GoldenConfigJobMixin.Meta): # Inherit Meta
        name = "Backup Configurations"
        description = "Backup the configurations of your network devices."
        has_sensitive_variables = False

    @gc_repos
    def run(self, data, commit): # NetBox jobs pass data and commit
        """Run config backup process."""
        self.logger.debug("Starting config backup nornir play.")
        if not constant.ENABLE_BACKUP:
             msg = "Backups are disabled in application settings."
             self.logger.error(msg)
             raise NornirPluginException(msg)
        config_backup(self)


class AllGoldenConfig(GoldenConfigJobMixin):
    """Job to to run all three jobs against a single device."""
    # Keep FormEntry fields separate for clarity in NetBox Job UI
    device = ObjectVar(model=Device, required=True)
    debug = BooleanVar(description="Enable for more verbose debug logging")

    class Meta(GoldenConfigJobMixin.Meta): # Inherit Meta
        name = "Execute All Golden Configuration Jobs - Single Device"
        description = "Process to run all Golden Configuration jobs configured."
        has_sensitive_variables = False

    def run(self, data, commit): # NetBox jobs pass data and commit
        """Run all jobs on a single device."""
        current_repos = gc_repo_prep(job=self, data=data)
        failed_jobs = []
        error_msg, jobs_list = "", "All"
        fail_job = False # Track if job should fail

        # Pass self (job instance) to the Nornir plays
        for enabled, play in [
            (constant.ENABLE_INTENDED, config_intended),
            (constant.ENABLE_BACKUP, config_backup),
            (constant.ENABLE_COMPLIANCE, config_compliance),
        ]:
            try:
                if enabled:
                    play(self)
            except BackupFailure:
                self.logger.error("Backup failure occurred!")
                failed_jobs.append("Backup")
                fail_job = True
            except IntendedGenerationFailure:
                self.logger.error("Intended failure occurred!")
                failed_jobs.append("Intended")
                fail_job = True
            except ComplianceFailure:
                self.logger.error("Compliance failure occurred!")
                failed_jobs.append("Compliance")
                fail_job = True
            except Exception as error:
                error_msg = f"`E3001:` General Exception handler in AllGoldenConfig, original error message ```{error}```"
                self.logger.error(error_msg)
                fail_job = True

        if commit:
             gc_repo_push(job=self, current_repos=current_repos, commit_message=data.get("commit_message"))
        else:
             self.logger.info("Commit set to False, skipping Git push.")

        if len(failed_jobs) > 1:
            jobs_list = ", ".join(failed_jobs)
        elif len(failed_jobs) == 1:
            jobs_list = failed_jobs[0]

        if fail_job:
            failure_msg = f"`E3030:` Failure during {jobs_list} Job(s)."
            self.log_failure(failure_msg + (f" | Error: {error_msg}" if error_msg else "")) # Log failure to NetBox Job log
            # Raising exception might not be needed if log_failure is used

class AllDevicesGoldenConfig(GoldenConfigJobMixin, FormEntry):
    """Job to to run all three jobs against multiple devices."""

    class Meta(GoldenConfigJobMixin.Meta): # Inherit Meta
        name = "Execute All Golden Configuration Jobs - Multiple Devices" # Adjusted name
        description = "Process to run all Golden Configuration jobs configured against multiple devices."
        has_sensitive_variables = False

    def run(self, data, commit): # NetBox jobs pass data and commit
        """Run all jobs on multiple devices."""
        current_repos = gc_repo_prep(job=self, data=data)
        failed_jobs = []
        error_msg, jobs_list = "", "All"
        fail_job = False

        for enabled, play in [
            (constant.ENABLE_INTENDED, config_intended),
            (constant.ENABLE_BACKUP, config_backup),
            (constant.ENABLE_COMPLIANCE, config_compliance),
        ]:
            try:
                if enabled:
                    play(self)
            except BackupFailure:
                self.logger.error("Backup failure occurred!")
                failed_jobs.append("Backup")
                fail_job = True
            except IntendedGenerationFailure:
                self.logger.error("Intended failure occurred!")
                failed_jobs.append("Intended")
                fail_job = True
            except ComplianceFailure:
                self.logger.error("Compliance failure occurred!")
                failed_jobs.append("Compliance")
                fail_job = True
            except Exception as error:
                error_msg = f"`E3001:` General Exception handler in AllDevicesGoldenConfig, original error message ```{error}```"
                self.logger.error(error_msg)
                fail_job = True

        if commit:
             gc_repo_push(job=self, current_repos=current_repos, commit_message=data.get("commit_message"))
        else:
             self.logger.info("Commit set to False, skipping Git push.")

        if len(failed_jobs) > 1:
            jobs_list = ", ".join(failed_jobs)
        elif len(failed_jobs) == 1:
            jobs_list = failed_jobs[0]

        if fail_job:
            failure_msg = f"`E3030:` Failure during {jobs_list} Job(s)."
            self.log_failure(failure_msg + (f" | Error: {error_msg}" if error_msg else ""))


class GenerateConfigPlans(Job, FormEntry): # Inherit NetBox Job and FormEntry
    """Job to generate config plans."""

    # Config Plan generation fields
    plan_type = ChoiceVar(choices=ConfigPlanTypeChoice.CHOICES)
    feature = MultiObjectVar(model=ComplianceFeature, required=False)
    change_control_id = StringVar(required=False)
    change_control_url = StringVar(required=False)
    commands = TextVar(required=False)

    class Meta:
        name = "Generate Config Plans"
        description = "Generate config plans for devices."
        has_sensitive_variables = False
        # NetBox doesn't have 'hidden' attribute, control visibility via Job registration/UI groups
        # hidden = True
        commit_default = False # Don't commit by default for plan generation

    # No __init__ needed for these instance variables in NetBox Job

    @property
    def plan_status(self):
        """The default status for ConfigPlan."""
        # Ensure config_plan_default_status is adapted if needed
        return config_plan_default_status()

    def _validate_inputs(self, data):
        """Validate job input data."""
        self._plan_type = data["plan_type"]
        self._feature = data.get("feature", []) # feature is now a QuerySet
        self._change_control_id = data.get("change_control_id", "")
        self._change_control_url = data.get("change_control_url", "")
        self._commands = data.get("commands", "")
        if self._plan_type in ["intended", "missing", "remediation"]:
            if not self._feature:
                self._feature = ComplianceFeature.objects.all() # Use direct QuerySet
        if self._plan_type in ["manual"]:
            if not self._commands:
                error_msg = "No commands entered for config plan generation."
                self.log_failure(error_msg)
                raise ValueError(error_msg) # Raise to stop job execution

    def _generate_config_plan_from_feature(self):
        """Generate config plans from features."""
        for device in self._device_qs:
            config_sets = []
            features_for_plan = [] # Track features added to this specific plan
            for feature_instance in self._feature: # Iterate through QuerySet
                # Adapt generate_config_set_from_compliance_feature if needed
                config_set = generate_config_set_from_compliance_feature(device, self._plan_type, feature_instance)
                if not config_set:
                    continue
                config_sets.append(config_set)
                features_for_plan.append(feature_instance)

            if not config_sets:
                _features_str = ", ".join([str(feat) for feat in self._feature])
                self.log_debug(f"Device `{device}` does not have `{self._plan_type}` configs for `{_features_str}`.")
                continue

            # Join string config sets, handle non-string types if necessary
            if all(isinstance(cs, str) for cs in config_sets):
                final_config_set = "\n".join(config_sets)
            else:
                 # Handle potential non-string data (e.g., JSON) appropriately
                 # For now, log warning and skip or attempt JSON dump
                 self.log_warning(f"Non-string config set generated for device {device} features {features_for_plan}. Attempting JSON dump.")
                 try:
                     final_config_set = json.dumps(config_sets, indent=2) # Example JSON handling
                 except TypeError:
                     self.log_failure(f"Could not serialize config set for device {device}. Skipping.")
                     continue

            config_plan = ConfigPlan.objects.create(
                device=device,
                plan_type=self._plan_type,
                config_set=final_config_set,
                change_control_id=self._change_control_id,
                change_control_url=self._change_control_url,
                status=self.plan_status,
                plan_result=self.job_result, # Use self.job_result provided by NetBox Job
            )
            config_plan.feature.set(features_for_plan) # Use set() for M2M
            # config_plan.validated_save() # Not standard in NetBox models, rely on save()
            _features_str = ", ".join([str(feat) for feat in features_for_plan])
            self.log_success(
                f"Config plan created for `{device}` with feature(s) `{_features_str}`.", obj=config_plan
            )

    def _generate_config_plan_from_manual(self):
        """Generate config plans from manual."""
        # NetBox Job context might differ, adapt if needed
        default_context = {
            # "request": self.request, # Not typically available directly
            "user": self.user, # User is available
        }
        for device in self._device_qs:
            # Adapt generate_config_set_from_manual if needed
            config_set = generate_config_set_from_manual(device, self._commands, context=default_context)
            if not config_set:
                self.log_debug(
                    f"Device {device} did not return a rendered config set from the provided commands."
                )
                continue
            config_plan = ConfigPlan.objects.create(
                device=device,
                plan_type=self._plan_type,
                config_set=config_set,
                change_control_id=self._change_control_id,
                change_control_url=self._change_control_url,
                status=self.plan_status,
                plan_result=self.job_result, # Use self.job_result
            )
            self.log_success(f"Config plan created for {device} with manual commands.", obj=config_plan)

    def run(self, data, commit): # NetBox jobs pass data and commit
        """Run config plan generation process."""
        # self.logger.debug("Updating Dynamic Group Cache.") # Replace cache update logic
        # update_dynamic_groups_cache() # Adapt or remove
        self.log_info("Starting config plan generation job.")
        self._validate_inputs(data) # Pass data dict
        try:
            # Adapt get_job_filter if needed
            self._device_qs = get_job_filter(data)
        except NornirPluginException as error: # Use adapted exception
            error_msg = str(error)
            self.log_failure(error_msg) # Log failure
            return # Stop execution

        if self._plan_type in ["intended", "missing", "remediation"]:
            self.log_debug("Starting config plan generation for compliance features.")
            self._generate_config_plan_from_feature()
        elif self._plan_type in ["manual"]:
            self.log_debug("Starting config plan generation for manual commands.")
            self._generate_config_plan_from_manual()
        else:
            error_msg = f"Unknown config plan type {self._plan_type}."
            self.log_failure(error_msg)
            return

        self.log_success("Config plan generation completed.")


class DeployConfigPlans(Job): # Inherit NetBox Job
    """Job to deploy config plans."""

    config_plan = MultiObjectVar(model=ConfigPlan, required=True)
    debug = BooleanVar(description="Enable for more verbose debug logging")

    class Meta:
        name = "Deploy Config Plans"
        description = "Deploy config plans to devices."
        has_sensitive_variables = False
        commit_default = True # Commit by default for deployment

    # No __init__ needed

    def run(self, data, commit): # NetBox jobs pass data and commit
        """Run config plan deployment process."""
        # self.logger.debug("Updating Dynamic Group Cache.") # Adapt cache update
        # update_dynamic_groups_cache() # Adapt or remove
        self.log_info("Starting config plan deployment job.")
        # Store data if needed by the play function
        self.job_data = data # Store data passed to the job run method
        config_deployment(self) # Pass self (job instance)


# NetBox JobButtonReceiver needs adaptation based on how Job Buttons are implemented in NetBox UI
class DeployConfigPlanJobButtonReceiver(JobButtonReceiver):
    """Job button to deploy a config plan."""

    class Meta:
        name = "Deploy Config Plan (Job Button Receiver)"
        has_sensitive_variables = False
        commit_default = True

    # No __init__ needed

    def receive_job_button(self, obj):
        """Run config plan deployment process when triggered by a button."""
        # This method needs adaptation based on NetBox Job Button implementation.
        # It might receive different arguments or need to fetch context differently.
        self.log_info("Starting config plan deployment job triggered by button.")
        # self.logger.debug("Updating Dynamic Group Cache.") # Adapt cache update
        # update_dynamic_groups_cache() # Adapt or remove

        # Ensure the passed object `obj` is a ConfigPlan instance
        if not isinstance(obj, ConfigPlan):
             self.log_failure(f"Received invalid object type for Job Button: {type(obj)}")
             return

        # Construct data expected by the run method/config_deployment play
        # The user who clicked the button might be available via `self.request.user` if context is passed
        self.job_data = {"debug": False, "config_plan": ConfigPlan.objects.filter(id=obj.id)}
        # self.user = self.request.user # Make user available if needed by plays

        # Call the Nornir play function
        config_deployment(self)


class SyncGoldenConfigWithScope(Job): # Renamed from SyncGoldenConfigWithDynamicGroups
    """Job to sync (add/remove) GoldenConfig table based on GoldenConfigSetting scopes."""

    class Meta:
        name = "Sync GoldenConfig Table with Scopes" # Updated name
        description = "Add or remove GoldenConfig entries based on GoldenConfigSettings scopes (Tags/Filters)."
        has_sensitive_variables = False
        commit_default = False # No git interaction needed

    def run(self, data, commit):
        """Run GoldenConfig sync based on defined scopes."""
        # self.logger.debug("Updating Scope Cache.") # Adapt cache update if any
        # update_dynamic_groups_cache() # Adapt or remove
        self.log_info("Starting sync of GoldenConfig with GoldenConfigSetting scopes.")

        # Get Pks based on the chosen scoping mechanism (Tags or Filters)
        try:
             # Assumes get_devices_in_scope() is adapted in the GoldenConfig model
             scoped_device_pks = models.GoldenConfig.get_devices_in_scope()
        except Exception as e:
             self.log_failure(f"Error determining devices in scope: {e}")
             return

        gc_device_pks = models.GoldenConfig.get_golden_config_device_ids()

        device_pks_to_remove = gc_device_pks.difference(scoped_device_pks)
        device_pks_to_add = scoped_device_pks.difference(gc_device_pks)

        gc_entries_to_remove = models.GoldenConfig.objects.filter(device__pk__in=device_pks_to_remove)
        removal_count = gc_entries_to_remove.count()
        if removal_count > 0:
            self.log_info(f"Removing {removal_count} GoldenConfig entries for devices no longer in scope...")
            for gc_entry_removal in gc_entries_to_remove:
                self.log_debug(f"Removing GoldenConfig entry for {gc_entry_removal.device.name}") # Log device name
            gc_entries_to_remove.delete()
            self.log_success(f"Successfully removed {removal_count} GoldenConfig entries.")

        devices_to_add_gc_entries = Device.objects.filter(pk__in=device_pks_to_add)
        added_count = 0
        for device in devices_to_add_gc_entries:
            gc_entry, created = models.GoldenConfig.objects.get_or_create(device=device)
            if created:
                self.log_debug(f"Adding GoldenConfig entry for device {device.name}")
                added_count += 1

        if added_count > 0:
            self.log_success(f"Successfully added {added_count} GoldenConfig entries.")

        self.log_success("GoldenConfig sync completed.")


# Register Jobs using NetBox's method (assuming `register_jobs` from netbox_plugin_nornir)
register_jobs(BackupJob)
register_jobs(IntendedJob)
register_jobs(ComplianceJob)
register_jobs(GenerateConfigPlans)
register_jobs(DeployConfigPlans)
register_jobs(DeployConfigPlanJobButtonReceiver) # Registration might differ for JobButtonReceivers
register_jobs(AllGoldenConfig)
register_jobs(AllDevicesGoldenConfig)
register_jobs(SyncGoldenConfigWithScope) # Register renamed job
