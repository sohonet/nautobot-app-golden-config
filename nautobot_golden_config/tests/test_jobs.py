"""Basic Job Test."""

from unittest.mock import MagicMock, patch

from nautobot.apps.testing import TransactionTestCase, create_job_result_and_run_job
from nautobot.dcim.models import Device
from nautobot.extras.choices import JobResultStatusChoices, LogLevelChoices
from nautobot.extras.models import JobLogEntry

from nautobot_golden_config import jobs
from nautobot_golden_config.exceptions import IntendedGenerationFailure
from nautobot_golden_config.tests.conftest import (
    create_device,
    create_orphan_device,
    dgs_gc_settings_and_job_repo_objects,
)
from nautobot_golden_config.utilities import constant


@patch("nautobot_golden_config.nornir_plays.config_backup.run_backup", MagicMock(return_value="foo"))
@patch.object(jobs, "ensure_git_repository")
class GCReposBackupTestCase(TransactionTestCase):
    """Test the repos to sync and commit are working for backup job."""

    databases = ("default", "job_logs")

    def setUp(self) -> None:
        """Setup test data."""
        self.device = create_device(name="foobaz")
        self.device2 = create_orphan_device(name="foobaz2")
        dgs_gc_settings_and_job_repo_objects()
        super().setUp()

    @patch("nautobot_golden_config.utilities.constant.ENABLE_BACKUP", True)
    def test_backup_job_repos_one_setting(self, mock_ensure_git_repository):
        """Test backup job repo-types are backup only."""
        mock_ensure_git_repository.return_value = True
        job_result = create_job_result_and_run_job(
            module="nautobot_golden_config.jobs", name="BackupJob", device=Device.objects.filter(name=self.device.name)
        )

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="GC Repo Syncs")
        self.assertEqual(log_entries.first().message, "Repository types to sync: backup_repository")

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="Get Job Filter")
        self.assertEqual(log_entries.count(), 2)
        self.assertEqual(log_entries.last().message, "In scope device count for this job: 1")

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="GC After Run")
        self.assertEqual(log_entries.first().message, "Finished the Backup Configurations job execution.")

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="GC Repo Commit and Push")
        self.assertEqual(log_entries.count(), 1)

    @patch("nautobot_golden_config.utilities.constant.ENABLE_BACKUP", True)
    def test_backup_job_repos_two_setting(self, mock_ensure_git_repository):
        """Test backup job repo-types are backup only."""
        mock_ensure_git_repository.return_value = True
        job_result = create_job_result_and_run_job(
            module="nautobot_golden_config.jobs",
            name="BackupJob",
            device=Device.objects.all(),
        )

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="Get Job Filter")
        self.assertEqual(log_entries.count(), 2)
        self.assertEqual(log_entries.last().message, "In scope device count for this job: 2")

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="GC Repo Syncs")
        self.assertEqual(log_entries.first().message, "Repository types to sync: backup_repository")

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="GC After Run")
        self.assertEqual(log_entries.first().message, "Finished the Backup Configurations job execution.")

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="GC Repo Commit and Push")
        self.assertEqual(log_entries.count(), 1)

    @patch("nautobot_golden_config.utilities.constant.ENABLE_BACKUP", False)
    def test_backup_job_repos_one_setting_backup_disabled(self, mock_ensure_git_repository):
        """Test backup job repo-types are backup only."""
        mock_ensure_git_repository.return_value = True
        self.assertFalse(constant.ENABLE_BACKUP)
        job_result = create_job_result_and_run_job(
            module="nautobot_golden_config.jobs", name="BackupJob", device=Device.objects.filter(name=self.device.name)
        )
        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="GC Repo Syncs")
        self.assertEqual(log_entries.first().message, "Repository types to sync: ")

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="Get Job Filter")
        self.assertEqual(log_entries.count(), 2)
        self.assertEqual(log_entries.last().message, "In scope device count for this job: 1")

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="run")
        self.assertEqual(log_entries.last().message, "Backups are disabled in application settings.")

    @patch("nautobot_golden_config.utilities.constant.ENABLE_BACKUP", False)
    def test_backup_job_repos_two_setting_backup_disabled(self, mock_ensure_git_repository):
        """Test backup job repo-types are backup only."""
        mock_ensure_git_repository.return_value = True
        self.assertFalse(constant.ENABLE_BACKUP)
        job_result = create_job_result_and_run_job(
            module="nautobot_golden_config.jobs", name="BackupJob", device=Device.objects.all()
        )
        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="GC Repo Syncs")
        self.assertEqual(log_entries.first().message, "Repository types to sync: ")

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="Get Job Filter")
        self.assertEqual(log_entries.count(), 2)
        self.assertEqual(log_entries.last().message, "In scope device count for this job: 2")

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="run")
        self.assertEqual(log_entries.last().message, "Backups are disabled in application settings.")


@patch("nautobot_golden_config.nornir_plays.config_intended.run_template", MagicMock(return_value="foo"))
@patch.object(jobs, "ensure_git_repository")
class GCReposIntendedTestCase(TransactionTestCase):
    """Test the repos to sync and commit are working for intended job."""

    databases = ("default", "job_logs")

    def setUp(self) -> None:
        """Setup test data."""
        self.device = create_device(name="foobaz")
        self.device2 = create_orphan_device(name="foobaz2")
        dgs_gc_settings_and_job_repo_objects()
        super().setUp()

    def test_intended_job_repos_one_setting(self, mock_ensure_git_repository):
        """Test intended job one GC setting enabled_intended enabled"""
        mock_ensure_git_repository.return_value = True
        job_result = create_job_result_and_run_job(
            module="nautobot_golden_config.jobs",
            name="IntendedJob",
            device=Device.objects.filter(name=self.device.name),
        )

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="GC Repo Syncs")
        self.assertEqual(log_entries.first().message, "Repository types to sync: intended_repository, jinja_repository")

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="Get Job Filter")
        self.assertEqual(log_entries.count(), 2)
        self.assertEqual(log_entries.last().message, "In scope device count for this job: 1")

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="GC After Run")
        self.assertEqual(log_entries.first().message, "Finished the Generate Intended Configurations job execution.")

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="GC Repo Commit and Push")
        self.assertEqual(log_entries.count(), 1)

    def test_intended_job_repos_two_setting(self, mock_ensure_git_repository):
        """Test intended job two GC setting enabled_intended enabled"""
        mock_ensure_git_repository.return_value = True
        job_result = create_job_result_and_run_job(
            module="nautobot_golden_config.jobs", name="IntendedJob", device=Device.objects.all()
        )
        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="Get Job Filter")
        self.assertEqual(log_entries.count(), 2)
        self.assertEqual(log_entries.last().message, "In scope device count for this job: 2")

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="GC Repo Syncs")
        self.assertEqual(log_entries.first().message, "Repository types to sync: intended_repository, jinja_repository")

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="GC After Run")
        self.assertEqual(log_entries.first().message, "Finished the Generate Intended Configurations job execution.")

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="GC Repo Commit and Push")
        self.assertEqual(log_entries.count(), 1)

    @patch("nautobot_golden_config.utilities.constant.ENABLE_INTENDED", False)
    def test_intended_job_repos_one_setting_intended_disabled(self, mock_ensure_git_repository):
        """Test intended job one GC setting enabled_intended disabled"""
        mock_ensure_git_repository.return_value = True
        self.assertFalse(constant.ENABLE_INTENDED)
        job_result = create_job_result_and_run_job(
            module="nautobot_golden_config.jobs",
            name="IntendedJob",
            device=Device.objects.filter(name=self.device.name),
        )
        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="GC Repo Syncs")
        self.assertEqual(log_entries.first().message, "Repository types to sync: ")

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="Get Job Filter")
        self.assertEqual(log_entries.count(), 2)
        self.assertEqual(log_entries.last().message, "In scope device count for this job: 1")

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="run")
        self.assertEqual(log_entries.last().message, "Intended Generation is disabled in application settings.")

    @patch("nautobot_golden_config.utilities.constant.ENABLE_INTENDED", False)
    def test_intended_job_repos_two_setting_intended_disabled(self, mock_ensure_git_repository):
        """Test intended job two GC setting enabled_intended disabled"""
        mock_ensure_git_repository.return_value = True
        self.assertFalse(constant.ENABLE_INTENDED)
        job_result = create_job_result_and_run_job(
            module="nautobot_golden_config.jobs", name="IntendedJob", device=Device.objects.all()
        )
        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="Get Job Filter")
        self.assertEqual(log_entries.count(), 2)
        self.assertEqual(log_entries.last().message, "In scope device count for this job: 2")

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="GC Repo Syncs")
        self.assertEqual(log_entries.first().message, "Repository types to sync: ")

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="run")
        self.assertEqual(log_entries.last().message, "Intended Generation is disabled in application settings.")


@patch("nautobot_golden_config.nornir_plays.config_compliance.run_compliance", MagicMock(return_value="foo"))
@patch.object(jobs, "ensure_git_repository")
class GCReposComplianceTestCase(TransactionTestCase):
    """Test the repos to sync and commit are working for compliance job."""

    databases = ("default", "job_logs")

    def setUp(self) -> None:
        """Setup test data."""
        self.device = create_device(name="foobaz")
        self.device2 = create_orphan_device(name="foobaz2")
        dgs_gc_settings_and_job_repo_objects()
        super().setUp()

    def test_compliance_job_repos_one_setting(self, mock_ensure_git_repository):
        """Test compliance job one GC setting enabled_compliance enabled"""
        mock_ensure_git_repository.return_value = True
        job_result = create_job_result_and_run_job(
            module="nautobot_golden_config.jobs",
            name="ComplianceJob",
            device=Device.objects.filter(name=self.device.name),
        )

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="GC Repo Syncs")
        self.assertEqual(
            log_entries.first().message, "Repository types to sync: backup_repository, intended_repository"
        )

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="Get Job Filter")
        self.assertEqual(log_entries.count(), 2)
        self.assertEqual(log_entries.last().message, "In scope device count for this job: 1")

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="GC After Run")
        self.assertEqual(log_entries.first().message, "Finished the Perform Configuration Compliance job execution.")

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="GC Repo Commit and Push")
        self.assertEqual(log_entries.count(), 1)

    def test_compliance_job_repos_two_setting(self, mock_ensure_git_repository):
        """Test compliance job two GC setting enabled_compliance enabled"""
        mock_ensure_git_repository.return_value = True
        job_result = create_job_result_and_run_job(
            module="nautobot_golden_config.jobs", name="ComplianceJob", device=Device.objects.all()
        )
        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="Get Job Filter")
        self.assertEqual(log_entries.count(), 2)
        self.assertEqual(log_entries.last().message, "In scope device count for this job: 2")

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="GC Repo Syncs")
        self.assertEqual(
            log_entries.first().message, "Repository types to sync: backup_repository, intended_repository"
        )

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="GC After Run")
        self.assertEqual(log_entries.first().message, "Finished the Perform Configuration Compliance job execution.")

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="GC Repo Commit and Push")
        self.assertEqual(log_entries.count(), 1)

    @patch("nautobot_golden_config.utilities.constant.ENABLE_COMPLIANCE", False)
    def test_compliance_job_repos_one_setting_compliance_disabled(self, mock_ensure_git_repository):
        """Test compliance job one GC setting enabled_compliance disabled"""
        mock_ensure_git_repository.return_value = True
        self.assertFalse(constant.ENABLE_COMPLIANCE)
        job_result = create_job_result_and_run_job(
            module="nautobot_golden_config.jobs",
            name="ComplianceJob",
            device=Device.objects.filter(name=self.device.name),
        )
        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="GC Repo Syncs")
        self.assertEqual(log_entries.first().message, "Repository types to sync: ")

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="Get Job Filter")
        self.assertEqual(log_entries.count(), 2)
        self.assertEqual(log_entries.last().message, "In scope device count for this job: 1")

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="run")
        self.assertEqual(log_entries.last().message, "Compliance is disabled in application settings.")

    @patch("nautobot_golden_config.utilities.constant.ENABLE_COMPLIANCE", False)
    def test_compliance_job_repos_two_setting_compliance_disabled(self, mock_ensure_git_repository):
        """Test compliance job two GC setting enabled_compliance disabled"""
        mock_ensure_git_repository.return_value = True
        self.assertFalse(constant.ENABLE_COMPLIANCE)
        job_result = create_job_result_and_run_job(
            module="nautobot_golden_config.jobs", name="ComplianceJob", device=Device.objects.all()
        )
        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="Get Job Filter")
        self.assertEqual(log_entries.count(), 2)
        self.assertEqual(log_entries.last().message, "In scope device count for this job: 2")

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="GC Repo Syncs")
        self.assertEqual(log_entries.first().message, "Repository types to sync: ")

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="run")
        self.assertEqual(log_entries.last().message, "Compliance is disabled in application settings.")

    @patch("nautobot_golden_config.utilities.constant.ENABLE_BACKUP", False)
    def test_compliance_job_repos_backup_disabled(self, mock_ensure_git_repository):
        """Test compliance job one GC setting enabled_backup disabled"""
        mock_ensure_git_repository.return_value = True
        self.assertFalse(constant.ENABLE_BACKUP)
        job_result = create_job_result_and_run_job(
            module="nautobot_golden_config.jobs", name="ComplianceJob", device=Device.objects.all()
        )
        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="Get Job Filter")
        self.assertEqual(log_entries.count(), 2)
        self.assertEqual(log_entries.last().message, "In scope device count for this job: 2")

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="GC Repo Syncs")
        self.assertEqual(
            log_entries.first().message, "Repository types to sync: backup_repository, intended_repository"
        )

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="GC After Run")
        self.assertEqual(log_entries.first().message, "Finished the Perform Configuration Compliance job execution.")

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="GC Repo Commit and Push")
        self.assertEqual(log_entries.count(), 1)

    @patch("nautobot_golden_config.utilities.constant.ENABLE_INTENDED", False)
    def test_compliance_job_repos_intended_disabled(self, mock_ensure_git_repository):
        """Test compliance job one GC setting enabled_intended disabled"""
        mock_ensure_git_repository.return_value = True
        self.assertFalse(constant.ENABLE_INTENDED)
        job_result = create_job_result_and_run_job(
            module="nautobot_golden_config.jobs", name="ComplianceJob", device=Device.objects.all()
        )
        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="Get Job Filter")
        self.assertEqual(log_entries.count(), 2)
        self.assertEqual(log_entries.last().message, "In scope device count for this job: 2")
        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="GC Repo Syncs")
        self.assertEqual(
            log_entries.first().message, "Repository types to sync: backup_repository, intended_repository"
        )

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="GC After Run")
        self.assertEqual(log_entries.first().message, "Finished the Perform Configuration Compliance job execution.")

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="GC Repo Commit and Push")
        self.assertEqual(log_entries.count(), 1)

    @patch("nautobot_golden_config.utilities.constant.ENABLE_BACKUP", False)
    @patch("nautobot_golden_config.utilities.constant.ENABLE_INTENDED", False)
    def test_compliance_job_repos_both_disabled(self, mock_ensure_git_repository):
        """Test compliance job one GC setting both disabled"""
        mock_ensure_git_repository.return_value = True
        self.assertFalse(constant.ENABLE_BACKUP)
        self.assertFalse(constant.ENABLE_INTENDED)
        job_result = create_job_result_and_run_job(
            module="nautobot_golden_config.jobs", name="ComplianceJob", device=Device.objects.all()
        )
        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="Get Job Filter")
        self.assertEqual(log_entries.count(), 2)
        self.assertEqual(log_entries.last().message, "In scope device count for this job: 2")
        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="GC Repo Syncs")
        self.assertEqual(
            log_entries.first().message, "Repository types to sync: backup_repository, intended_repository"
        )

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="GC After Run")
        self.assertEqual(log_entries.first().message, "Finished the Perform Configuration Compliance job execution.")

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="GC Repo Commit and Push")
        self.assertEqual(log_entries.count(), 0)


@patch("nautobot_golden_config.nornir_plays.config_backup.run_backup", MagicMock(return_value="foo"))
@patch("nautobot_golden_config.nornir_plays.config_intended.run_template", MagicMock(return_value="foo"))
@patch("nautobot_golden_config.nornir_plays.config_compliance.run_compliance", MagicMock(return_value="foo"))
@patch.object(jobs, "ensure_git_repository")
class GCReposRunAllSingleTestCase(TransactionTestCase):
    """Test the repos to sync and commit are working for run all single job."""

    databases = ("default", "job_logs")

    def setUp(self) -> None:
        """Setup test data."""
        self.device = create_device(name="foobaz")
        dgs_gc_settings_and_job_repo_objects()
        super().setUp()

    def test_run_all_job_single_repos(self, mock_ensure_git_repository):
        """Test run all job single on one GC setting enabled"""
        mock_ensure_git_repository.return_value = True
        job_result = create_job_result_and_run_job(
            module="nautobot_golden_config.jobs", name="AllGoldenConfig", device=self.device.id
        )
        self.assertTrue(constant.ENABLE_BACKUP)
        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="GC Repo Syncs")
        self.assertEqual(
            log_entries.first().message,
            "Repository types to sync: backup_repository, intended_repository, jinja_repository",
        )

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="Get Job Filter")
        self.assertEqual(log_entries.count(), 2)
        self.assertEqual(log_entries.last().message, "In scope device count for this job: 1")

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="GC After Run")
        self.assertEqual(
            log_entries.first().message,
            "Finished the Execute All Golden Configuration Jobs - Single Device job execution.",
        )

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="GC Repo Commit and Push")
        self.assertEqual(log_entries.count(), 1)

    @patch("nautobot_golden_config.utilities.constant.ENABLE_BACKUP", False)
    def test_run_all_job_single_repos_backup_disabled(self, mock_ensure_git_repository):
        """Test run all job single on one GC backup_disabled"""
        mock_ensure_git_repository.return_value = True
        job_result = create_job_result_and_run_job(
            module="nautobot_golden_config.jobs", name="AllGoldenConfig", device=self.device.id
        )
        self.assertFalse(constant.ENABLE_BACKUP)
        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="GC Repo Syncs")
        self.assertEqual(
            log_entries.first().message,
            "Repository types to sync: backup_repository, intended_repository, jinja_repository",
        )

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="Get Job Filter")
        self.assertEqual(log_entries.count(), 2)
        self.assertEqual(log_entries.last().message, "In scope device count for this job: 1")

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="GC After Run")
        self.assertEqual(
            log_entries.first().message,
            "Finished the Execute All Golden Configuration Jobs - Single Device job execution.",
        )

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="GC Repo Commit and Push")
        self.assertEqual(log_entries.count(), 1)

    @patch("nautobot_golden_config.utilities.constant.ENABLE_INTENDED", False)
    def test_run_all_job_single_repos_intended_disabled(self, mock_ensure_git_repository):
        """Test run all job single on one GC intended_disabled"""
        mock_ensure_git_repository.return_value = True
        job_result = create_job_result_and_run_job(
            module="nautobot_golden_config.jobs", name="AllGoldenConfig", device=self.device.id
        )
        self.assertFalse(constant.ENABLE_INTENDED)
        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="GC Repo Syncs")
        self.assertEqual(
            log_entries.first().message,
            "Repository types to sync: backup_repository, intended_repository, jinja_repository",
        )

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="Get Job Filter")
        self.assertEqual(log_entries.count(), 2)
        self.assertEqual(log_entries.last().message, "In scope device count for this job: 1")

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="GC After Run")
        self.assertEqual(
            log_entries.first().message,
            "Finished the Execute All Golden Configuration Jobs - Single Device job execution.",
        )

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="GC Repo Commit and Push")
        self.assertEqual(log_entries.count(), 1)

    @patch("nautobot_golden_config.utilities.constant.ENABLE_BACKUP", False)
    @patch("nautobot_golden_config.utilities.constant.ENABLE_INTENDED", False)
    def test_run_all_job_single_repos_both_disabled(self, mock_ensure_git_repository):
        """Test run all job single on one GC both_disabled"""
        mock_ensure_git_repository.return_value = True
        job_result = create_job_result_and_run_job(
            module="nautobot_golden_config.jobs", name="AllGoldenConfig", device=self.device.id
        )
        self.assertFalse(constant.ENABLE_BACKUP)
        self.assertFalse(constant.ENABLE_INTENDED)
        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="GC Repo Syncs")
        self.assertEqual(
            log_entries.first().message,
            "Repository types to sync: backup_repository, intended_repository, jinja_repository",
        )

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="Get Job Filter")
        self.assertEqual(log_entries.count(), 2)
        self.assertEqual(log_entries.last().message, "In scope device count for this job: 1")

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="GC After Run")
        self.assertEqual(
            log_entries.first().message,
            "Finished the Execute All Golden Configuration Jobs - Single Device job execution.",
        )

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="GC Repo Commit and Push")
        self.assertEqual(log_entries.count(), 0)


@patch("nautobot_golden_config.nornir_plays.config_backup.run_backup", MagicMock(return_value="foo"))
@patch("nautobot_golden_config.nornir_plays.config_intended.run_template", MagicMock(return_value="foo"))
@patch("nautobot_golden_config.nornir_plays.config_compliance.run_compliance", MagicMock(return_value="foo"))
@patch.object(jobs, "ensure_git_repository")
class GCReposRunAllMultipleTestCase(TransactionTestCase):
    """Test the repos to sync and commit are working for run all multiple job."""

    databases = ("default", "job_logs")

    def setUp(self) -> None:
        """Setup test data."""
        self.device = create_device(name="foobaz")
        self.device2 = create_orphan_device(name="foobaz2")
        dgs_gc_settings_and_job_repo_objects()
        super().setUp()

    def test_run_all_job_multiple_repos(self, mock_ensure_git_repository):
        """Test run all job multiple on one GC setting enabled"""
        mock_ensure_git_repository.return_value = True
        job_result = create_job_result_and_run_job(
            module="nautobot_golden_config.jobs", name="AllDevicesGoldenConfig", device=Device.objects.all()
        )
        self.assertTrue(constant.ENABLE_BACKUP)
        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="GC Repo Syncs")
        self.assertEqual(
            log_entries.first().message,
            "Repository types to sync: backup_repository, intended_repository, jinja_repository",
        )

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="Get Job Filter")
        self.assertEqual(log_entries.count(), 2)
        self.assertEqual(log_entries.last().message, "In scope device count for this job: 2")

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="GC After Run")
        self.assertEqual(
            log_entries.first().message,
            "Finished the Execute All Golden Configuration Jobs - Multiple Device job execution.",
        )

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="GC Repo Commit and Push")
        self.assertEqual(log_entries.count(), 1)

    @patch("nautobot_golden_config.utilities.constant.ENABLE_BACKUP", False)
    def test_run_all_job_multiple_repos_backup_disabled(self, mock_ensure_git_repository):
        """Test run all job multiple on one GC backup_disabled"""
        mock_ensure_git_repository.return_value = True
        job_result = create_job_result_and_run_job(
            module="nautobot_golden_config.jobs", name="AllDevicesGoldenConfig", device=Device.objects.all()
        )
        self.assertFalse(constant.ENABLE_BACKUP)
        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="GC Repo Syncs")
        self.assertEqual(
            log_entries.first().message,
            "Repository types to sync: backup_repository, intended_repository, jinja_repository",
        )

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="Get Job Filter")
        self.assertEqual(log_entries.count(), 2)
        self.assertEqual(log_entries.last().message, "In scope device count for this job: 2")

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="GC After Run")
        self.assertEqual(
            log_entries.first().message,
            "Finished the Execute All Golden Configuration Jobs - Multiple Device job execution.",
        )

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="GC Repo Commit and Push")
        self.assertEqual(log_entries.count(), 1)

    @patch("nautobot_golden_config.utilities.constant.ENABLE_INTENDED", False)
    def test_run_all_job_multiple_repos_intended_disabled(self, mock_ensure_git_repository):
        """Test run all job multiple on one GC intended_disabled"""
        mock_ensure_git_repository.return_value = True
        job_result = create_job_result_and_run_job(
            module="nautobot_golden_config.jobs", name="AllDevicesGoldenConfig", device=Device.objects.all()
        )
        self.assertFalse(constant.ENABLE_INTENDED)
        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="GC Repo Syncs")
        self.assertEqual(
            log_entries.first().message,
            "Repository types to sync: backup_repository, intended_repository, jinja_repository",
        )

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="Get Job Filter")
        self.assertEqual(log_entries.count(), 2)
        self.assertEqual(log_entries.last().message, "In scope device count for this job: 2")

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="GC After Run")
        self.assertEqual(
            log_entries.first().message,
            "Finished the Execute All Golden Configuration Jobs - Multiple Device job execution.",
        )

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="GC Repo Commit and Push")
        self.assertEqual(log_entries.count(), 1)

    @patch("nautobot_golden_config.utilities.constant.ENABLE_BACKUP", False)
    @patch("nautobot_golden_config.utilities.constant.ENABLE_INTENDED", False)
    def test_run_all_job_multiple_repos_both_disabled(self, mock_ensure_git_repository):
        """Test run all job multiple on one GC both_disabled"""
        mock_ensure_git_repository.return_value = True
        job_result = create_job_result_and_run_job(
            module="nautobot_golden_config.jobs", name="AllDevicesGoldenConfig", device=Device.objects.all()
        )
        self.assertFalse(constant.ENABLE_BACKUP)
        self.assertFalse(constant.ENABLE_INTENDED)
        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="GC Repo Syncs")
        self.assertEqual(
            log_entries.first().message,
            "Repository types to sync: backup_repository, intended_repository, jinja_repository",
        )

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="Get Job Filter")
        self.assertEqual(log_entries.count(), 2)
        self.assertEqual(log_entries.last().message, "In scope device count for this job: 2")

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="GC After Run")
        self.assertEqual(
            log_entries.first().message,
            "Finished the Execute All Golden Configuration Jobs - Multiple Device job execution.",
        )

        log_entries = JobLogEntry.objects.filter(job_result=job_result, grouping="GC Repo Commit and Push")
        self.assertEqual(log_entries.count(), 0)


@patch.object(jobs, "ensure_git_repository", MagicMock(return_value=True))
class GCReposFailureHandlingTestCase(TransactionTestCase):
    """A crashed play must fail the job and log its traceback; device task failures follow the checkbox."""

    databases = ("default", "job_logs")

    def setUp(self) -> None:
        """Setup test data."""
        self.device = create_device(name="foobaz")
        dgs_gc_settings_and_job_repo_objects()
        # The test GitRepositories have no remote, so a real push would fail the job on its own.
        push_patcher = patch.object(jobs, "gc_repo_push")
        self.mock_push = push_patcher.start()
        self.addCleanup(push_patcher.stop)
        super().setUp()

    def _run(self, name, **kwargs):
        job_result = create_job_result_and_run_job(
            module="nautobot_golden_config.jobs",
            name=name,
            device=Device.objects.filter(name=self.device.name),
            **kwargs,
        )
        job_result.refresh_from_db()
        return job_result

    def _error_messages(self, job_result):
        return list(
            JobLogEntry.objects.filter(job_result=job_result, log_level=LogLevelChoices.LOG_ERROR).values_list(
                "message", flat=True
            )
        )

    @patch("nautobot_golden_config.utilities.constant.ENABLE_COMPLIANCE", True)
    @patch(
        "nautobot_golden_config.nornir_plays.config_compliance.get_rules",
        MagicMock(side_effect=RuntimeError("get_rules exploded")),
    )
    def test_play_exception_fails_job_and_logs_traceback(self):
        """An exception in the play is logged with its traceback and fails the job even with the checkbox off."""
        job_result = self._run("ComplianceJob", fail_job_on_task_failure=False)

        self.assertEqual(job_result.status, JobResultStatusChoices.STATUS_FAILURE)
        play_errors = JobLogEntry.objects.filter(job_result=job_result, grouping="GC Play Exception")
        self.assertEqual(play_errors.count(), 1)
        message = play_errors.first().message
        self.assertEqual(play_errors.first().log_level, LogLevelChoices.LOG_ERROR)
        self.assertIn("`E3001:`", message)
        self.assertIn("get_rules exploded", message)
        self.assertIn("Traceback (most recent call last)", message)
        # Repos are still pushed after a crash.
        self.mock_push.assert_called_once()

    @patch.object(jobs, "config_intended", MagicMock(side_effect=IntendedGenerationFailure()))
    def test_device_task_failures_logged_job_succeeds_when_checkbox_off(self):
        """Device task failures are logged, but only fail the job when fail_job_on_task_failure is set."""
        job_result = self._run("IntendedJob", fail_job_on_task_failure=False)

        self.assertEqual(job_result.status, JobResultStatusChoices.STATUS_SUCCESS)
        self.assertTrue(any("`E3030:`" in msg for msg in self._error_messages(job_result)))
        self.assertFalse(JobLogEntry.objects.filter(job_result=job_result, grouping="GC Play Exception").exists())

    @patch.object(jobs, "config_intended", MagicMock(side_effect=IntendedGenerationFailure()))
    def test_device_task_failures_fail_job_when_checkbox_on(self):
        """With fail_job_on_task_failure set, device task failures fail the job."""
        job_result = self._run("IntendedJob", fail_job_on_task_failure=True)

        self.assertEqual(job_result.status, JobResultStatusChoices.STATUS_FAILURE)
        self.assertFalse(JobLogEntry.objects.filter(job_result=job_result, grouping="GC Play Exception").exists())

    @patch("nautobot_golden_config.utilities.constant.ENABLE_INTENDED", True)
    @patch("nautobot_golden_config.utilities.constant.ENABLE_BACKUP", False)
    @patch("nautobot_golden_config.utilities.constant.ENABLE_COMPLIANCE", False)
    @patch.object(jobs, "config_intended", MagicMock(side_effect=RuntimeError("intended play exploded")))
    def test_all_golden_config_play_exception_fails_job(self):
        """The run-all job also logs a crashed play with its traceback and fails."""
        job_result = create_job_result_and_run_job(
            module="nautobot_golden_config.jobs",
            name="AllGoldenConfig",
            device=self.device.id,
            fail_job_on_task_failure=False,
        )
        job_result.refresh_from_db()

        self.assertEqual(job_result.status, JobResultStatusChoices.STATUS_FAILURE)
        message = JobLogEntry.objects.get(job_result=job_result, grouping="GC Play Exception").message
        self.assertIn("intended play exploded", message)
        self.assertIn("Traceback (most recent call last)", message)
        self.mock_push.assert_called_once()
