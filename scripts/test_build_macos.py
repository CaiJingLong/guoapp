from pathlib import Path
import tempfile
import unittest
from unittest import mock

from app_build import BuildVariant
import build_macos


class MacOSBuildTests(unittest.TestCase):
    def test_validation_build_preserves_edition_and_disables_images(self):
        arguments = build_macos.flutter_arguments(
            BuildVariant(True), debug=False, disable_remote_images=True)
        self.assertIn('--release', arguments)
        self.assertIn('--dart-define=ALL_SOURCES=true', arguments)
        self.assertIn('--dart-define=DISABLE_REMOTE_IMAGES=true', arguments)

    def test_signs_nested_code_before_application_and_verifies(self):
        with tempfile.TemporaryDirectory() as temporary:
            application = Path(temporary) / 'sample.app'
            framework = application / 'Contents/Frameworks/Media.framework'
            framework.mkdir(parents=True)
            library = application / 'Contents/Frameworks/libcore.dylib'
            binary = framework / 'Media'
            executable = application / 'Contents/MacOS/sample'
            executable.parent.mkdir(parents=True)
            for path in (library, binary, executable):
                path.write_bytes(b'\xcf\xfa\xed\xfe' + b'\0' * 28)
            resource = application / 'Contents/Resources/sample.txt'
            resource.parent.mkdir(parents=True)
            resource.write_text('synthetic')
            (framework / 'Alias').symlink_to('Media')
            with mock.patch.object(build_macos, 'run') as run:
                build_macos.sign_application(application, 'Local Development')
            calls = [call.args[0] for call in run.call_args_list]
            signed = [Path(call[-1]) for call in calls if '--sign' in call]
            self.assertIn(library, signed)
            self.assertIn(binary, signed)
            self.assertIn(framework, signed)
            self.assertEqual(signed[-1], application)
            self.assertLess(signed.index(binary), signed.index(framework))
            self.assertNotIn(resource, signed)
            self.assertNotIn(framework / 'Alias', signed)
            self.assertTrue(any('--verify' in call and '--deep' in call for call in calls))


if __name__ == '__main__':
    unittest.main()
