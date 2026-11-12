"""Unit tests for nautobot_golden_config.nornir_plays.config_intended."""

import os
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.template import engines
from nornir_jinja2.plugins.tasks import template_file

from nautobot_golden_config.nornir_plays import config_intended
from nautobot_golden_config.utilities.helper import ThreadLocalJinjaEnv


class ThreadLocalJinjaEnvTest(unittest.TestCase):
    """Each Nornir worker thread must get its own Jinja environment."""

    def test_same_env_within_a_thread(self):
        jinja_envs = ThreadLocalJinjaEnv()
        self.assertIs(jinja_envs.env, jinja_envs.env)

    def test_different_env_per_thread(self):
        jinja_envs = ThreadLocalJinjaEnv()
        seen = []
        threads = [threading.Thread(target=lambda: seen.append(jinja_envs.env)) for _ in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        seen.append(jinja_envs.env)
        self.assertEqual(len({id(env) for env in seen}), 6)

    def test_env_has_django_filters_without_sharing_their_dict(self):
        env = ThreadLocalJinjaEnv().env
        self.assertIn("humanize_speed", env.filters)
        self.assertIsNot(env.filters, engines["jinja"].env.filters)

    def test_concurrent_renders_do_not_race_on_loader(self):
        """Regression test for `E1014: Unknown error - weak object has gone away`.

        nornir_jinja2's template_file replaces `env.loader` on every render, and Jinja's template cache key holds a
        weakref to the loader. With one environment shared by all threads, a thread could free the loader another
        thread had just taken a weakref to. A tiny GIL switch interval makes that window easy to hit: with a shared
        environment this loop fails roughly half of its renders.
        """
        with tempfile.TemporaryDirectory() as template_dir:
            with open(os.path.join(template_dir, "main.j2"), "w", encoding="utf8") as handle:
                handle.write("{% include 'include.j2' %}{{ value }}")
            with open(os.path.join(template_dir, "include.j2"), "w", encoding="utf8") as handle:
                handle.write("included ")

            jinja_envs = ThreadLocalJinjaEnv()
            task = SimpleNamespace(host={})
            errors = []

            def render(value):
                try:
                    result = template_file(
                        task, template="main.j2", path=template_dir, jinja_env=jinja_envs.env, value=value
                    )
                    if result.result != f"included {value}":
                        errors.append(f"bad render: {result.result!r}")
                except Exception as error:  # pylint: disable=broad-exception-caught
                    errors.append(repr(error))

            old_interval = sys.getswitchinterval()
            sys.setswitchinterval(1e-6)
            try:
                with ThreadPoolExecutor(max_workers=20) as executor:
                    list(executor.map(render, range(5000)))
            finally:
                sys.setswitchinterval(old_interval)

        self.assertEqual(errors, [])


class ConfigIntendedJinjaEnvTest(unittest.TestCase):
    """The play hands the Nornir tasks per-thread environments, never one shared environment."""

    @patch.object(config_intended, "NornirLogger", MagicMock())
    @patch.object(config_intended, "verify_settings", MagicMock())
    @patch.object(config_intended, "InitNornir")
    def test_play_passes_thread_local_env_to_tasks(self, mock_init_nornir):
        nornir_obj = mock_init_nornir.return_value.__enter__.return_value
        run = nornir_obj.with_processors.return_value.run
        run.return_value.failed = False

        job = MagicMock(device_to_settings_map={})
        config_intended.config_intended(job)

        self.assertIsInstance(run.call_args.kwargs["jinja_env"], ThreadLocalJinjaEnv)
