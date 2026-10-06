import argparse
import hashlib
import os
import platform
import plistlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

from app_build import BuildVariant, add_variant_argument

root = Path(__file__).resolve().parents[1]


def run(arguments, **kwargs):
    subprocess.run(arguments, cwd=root, check=True, **kwargs)


def flutter_arguments(variant, debug=False, disable_remote_images=False):
    arguments = ['build', 'macos', '--debug' if debug else '--release',
                 '--no-pub', *variant.flutter_arguments]
    if disable_remote_images:
        arguments.append('--dart-define=DISABLE_REMOTE_IMAGES=true')
    return arguments


def sign_application(application, identity):
    signatures = {b'\xcf\xfa\xed\xfe', b'\xce\xfa\xed\xfe', b'\xfe\xed\xfa\xcf',
                  b'\xfe\xed\xfa\xce', b'\xca\xfe\xba\xbe', b'\xca\xfe\xba\xbf'}
    code = []
    for path in application.rglob('*'):
        if path.is_symlink():
            continue
        if path.is_dir() and path.suffix in {'.framework', '.app', '.xpc'}:
            code.append(path)
        elif path.is_file():
            with path.open('rb') as stream:
                if stream.read(4) in signatures:
                    code.append(path)
    for path in sorted(code, key=lambda value: len(value.parts), reverse=True) + [application]:
        run(['codesign', '--force', '--sign', identity, '--timestamp=none',
             '--preserve-metadata=entitlements', str(path)])
    run(['codesign', '--verify', '--deep', '--strict', '--verbose=2', str(application)])


def embed_core():
    variant = BuildVariant.from_dart_defines(os.environ.get('DART_DEFINES', ''))
    architectures = os.environ.get('ARCHS', '').split()
    if not architectures or any(value not in {'arm64', 'x86_64'} for value in architectures):
        raise SystemExit('Xcode 未提供有效的 macOS ARCHS。')
    target = Path(os.environ['TARGET_BUILD_DIR'])
    output = target / os.environ['FRAMEWORKS_FOLDER_PATH'] / 'libduanju_core.dylib'
    arguments = [sys.executable, str(root / 'scripts/build_native.py'),
                 '--platform', 'darwin', '--darwin-output', str(output), *variant.arguments]
    for architecture in architectures:
        arguments.extend(['--darwin-arch', architecture])
    run(arguments)
    if os.environ.get('CODE_SIGNING_ALLOWED') != 'NO':
        identity = os.environ.get('EXPANDED_CODE_SIGN_IDENTITY') or '-'
        run(['codesign', '--force', '--sign', identity, '--timestamp=none', str(output)])
    path = target / os.environ['INFOPLIST_PATH']
    data = plistlib.loads(path.read_bytes())
    data['CFBundleDisplayName'] = variant.name
    data['CFBundleName'] = variant.name
    path.write_bytes(plistlib.dumps(data, fmt=plistlib.FMT_BINARY, sort_keys=False))


def main():
    parser = argparse.ArgumentParser(description='构建 macOS 开发快照；Go 核心由 Xcode 自动编译并嵌入')
    parser.add_argument('--xcode-core', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--debug', action='store_true', help='生成 Debug 应用，不导出 ZIP')
    parser.add_argument('--sign-identity', default='-', help='本机钥匙串的签名名称或 SHA-1；默认临时签名')
    parser.add_argument('--disable-remote-images', action='store_true', help='验证时禁用站源图片请求')
    add_variant_argument(parser)
    options = parser.parse_args()
    if platform.system() != 'Darwin':
        raise SystemExit('macOS 构建需要 macOS、完整 Xcode、Flutter、Go 和 CocoaPods。')
    if options.xcode_core:
        embed_core()
        return
    flutter = os.environ.get('FLUTTER_BIN') or shutil.which('flutter')
    if not flutter or not shutil.which('go') or not shutil.which('pod'):
        raise SystemExit('请安装符合 README 版本要求的 Flutter、Go 和 CocoaPods，并加入 PATH。')
    variant = BuildVariant(options.all_sources)
    environment = os.environ.copy()
    environment['DUANJU_PYTHON'] = sys.executable
    run([flutter, 'pub', 'get', '--enforce-lockfile'], env=environment)
    run([flutter, *flutter_arguments(variant, options.debug, options.disable_remote_images)], env=environment)
    configuration = 'Debug' if options.debug else 'Release'
    application = root / 'build/macos/Build/Products' / configuration / 'duanju_app.app'
    if not (application / 'Contents/Frameworks/libduanju_core.dylib').is_file():
        raise SystemExit('macOS 应用缺少 Go 核心，未导出安装包。')
    sign_application(application, options.sign_identity)
    if options.debug:
        print(application)
        return
    version = re.search(r'^version:\s*(\S+)', (root / 'pubspec.yaml').read_text(), re.MULTILINE).group(1)
    output = root / 'dist/macos'
    output.mkdir(parents=True, exist_ok=True)
    suffix = '-no-images' if options.disable_remote_images else ''
    destination = output / f'{variant.slug}-{version}-macos-preview{suffix}.zip'
    run(['ditto', '-c', '-k', '--sequesterRsrc', '--keepParent', str(application), str(destination)])
    digest = hashlib.sha256()
    with destination.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    destination.with_suffix('.zip.sha256').write_text(f'{digest.hexdigest()}  {destination.name}\n', encoding='ascii')
    print(destination)
    print('开发快照：未公证，平台验收状态以 README 为准。')


if __name__ == '__main__':
    main()
