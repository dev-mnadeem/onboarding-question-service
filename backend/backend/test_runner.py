"""Run the suite with uploads going to a throwaway folder.

Several tests create documents. Without this they would be written next to
real uploads in ``MEDIA_ROOT``, which on a working install holds identity
documents.
"""

import shutil
import tempfile

from django.conf import settings
from django.test.runner import DiscoverRunner


class TempMediaRunner(DiscoverRunner):
    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        self._media_root = tempfile.mkdtemp(prefix="limitless-test-media-")
        self._real_media_root = settings.MEDIA_ROOT
        settings.MEDIA_ROOT = self._media_root

    def teardown_test_environment(self, **kwargs):
        settings.MEDIA_ROOT = self._real_media_root
        shutil.rmtree(self._media_root, ignore_errors=True)
        super().teardown_test_environment(**kwargs)
