import argparse
import os
import platform
import shlex
import shutil
import subprocess
from pathlib import Path

from app_build import BuildVariant, add_variant_argument

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--platform', choices=['android', 'windows', 'darwin'], required=True)
parser.add_argument('--abi', action='append', choices=['arm64-v8a', 'armeabi-v7a', 'x86_64'])
parser.add_argument('--darwin-arch', action='append', choices=['arm64', 'x86_64'])
parser.add_argument('--darwin-output', type=Path)
add_variant_argument(parser)
options = parser.parse_args()
variant = BuildVariant(options.all_sources)

environment = os.environ.copy()
environment.setdefault('GOPROXY', 'https://goproxy.cn,direct')
environment.setdefault('GOSUMDB', 'off')
environment['CGO_ENABLED'] = '1'
go = shutil.which('go')
if not go:
    raise SystemExit('请先安装 Go 1.24.1 或更新版本。')
bootstrap_env = environment.copy()
bootstrap_env['GOSUMDB'] = os.environ.get('GOSUMDB', 'sum.golang.org')
if bootstrap_env['GOSUMDB'] == 'off':
    bootstrap_env['GOSUMDB'] = 'sum.golang.org'
toolchain_root = subprocess.check_output([go, 'env', 'GOROOT'], cwd=root / 'native',
    env=bootstrap_env, text=True).strip()
go = str(Path(toolchain_root) / 'bin' / ('go.exe' if platform.system() == 'Windows' else 'go'))

def build(goos, architecture, compiler, output, extra=None):
    output.parent.mkdir(parents=True, exist_ok=True)
    build_env = environment.copy()
    build_env.update(GOOS=goos, GOARCH=architecture, CC=str(compiler))
    if extra:
        build_env.update(extra)
    print('Building ' + str(output.relative_to(root)), flush=True)
    subprocess.run([go, 'build', '-trimpath', '-buildmode=c-shared',
                    '-ldflags=' + variant.linker_flags, '-o', str(output), './bridge'],
                   cwd=root / 'native', env=build_env, check=True)

if options.platform == 'android':
    sdk = os.environ.get('ANDROID_HOME') or os.environ.get('ANDROID_SDK_ROOT')
    if not sdk:
        raise SystemExit('请设置 ANDROID_HOME 为 Android SDK 目录。')
    ndk = Path(os.environ.get('ANDROID_NDK_HOME', Path(sdk) / 'ndk' / '28.2.13676358'))
    host = {'Darwin': 'darwin-x86_64', 'Linux': 'linux-x86_64', 'Windows': 'windows-x86_64'}[platform.system()]
    compilers = ndk / 'toolchains' / 'llvm' / 'prebuilt' / host / 'bin'
    mappings = {
        'arm64-v8a': ('arm64', 'aarch64-linux-android26-clang'),
        'armeabi-v7a': ('arm', 'armv7a-linux-androideabi26-clang'),
        'x86_64': ('amd64', 'x86_64-linux-android26-clang'),
    }
    for abi in options.abi or list(mappings):
        architecture, name = mappings[abi]
        compiler = compilers / (name + ('.cmd' if platform.system() == 'Windows' else ''))
        if not compiler.exists():
            raise SystemExit('缺少 Android NDK 编译器：' + str(compiler))
        output = root / 'android' / 'app' / 'src' / 'main' / 'jniLibs' / abi / 'libduanju_core.so'
        extra = {'CGO_LDFLAGS': '-Wl,-z,max-page-size=16384'}
        if architecture == 'arm':
            extra['GOARM'] = '7'
        build('android', architecture, compiler, output, extra)
elif options.platform == 'windows':
    compiler = shutil.which('x86_64-w64-mingw32-gcc') or (shutil.which('gcc') if platform.system() == 'Windows' else None)
    if not compiler:
        raise SystemExit('请安装 MinGW-w64，并将其 bin 目录加入 PATH。')
    build('windows', 'amd64', compiler, root / 'windows' / 'runner' / 'duanju_core.dll',
          {'CGO_LDFLAGS': '-static-libgcc'})
else:
    if platform.system() != 'Darwin':
        raise SystemExit('macOS 核心构建需要 macOS 和 Xcode Command Line Tools。')
    compiler = subprocess.check_output(['xcrun', '--sdk', 'macosx', '--find', 'clang'], text=True).strip()
    sdk = subprocess.check_output(['xcrun', '--sdk', 'macosx', '--show-sdk-path'], text=True).strip()
    minimum = os.environ.get('MACOSX_DEPLOYMENT_TARGET', '12.0')
    architectures = list(dict.fromkeys(options.darwin_arch or [platform.machine()]))
    output = (options.darwin_output or root / 'native' / 'build' / 'darwin' / 'libduanju_core.dylib').resolve()
    libraries = []
    for architecture in architectures:
        if architecture not in {'arm64', 'x86_64'}:
            raise SystemExit('不支持的 macOS 架构：' + architecture)
        flags = shlex.join(['-isysroot', sdk, '-arch', architecture, '-mmacosx-version-min=' + minimum])
        library = root / 'native' / 'build' / 'darwin' / architecture / 'libduanju_core.dylib'
        build('darwin', 'amd64' if architecture == 'x86_64' else 'arm64', compiler, library, {
            'CGO_CFLAGS': flags,
            'CGO_LDFLAGS': flags,
            'MACOSX_DEPLOYMENT_TARGET': minimum,
        })
        libraries.append(library)
    output.parent.mkdir(parents=True, exist_ok=True)
    if len(libraries) == 1:
        if libraries[0] != output:
            shutil.copy2(libraries[0], output)
    else:
        subprocess.run(['xcrun', 'lipo', '-create', *map(str, libraries), '-output', str(output)], check=True)
    subprocess.run(['xcrun', 'install_name_tool', '-id', '@rpath/libduanju_core.dylib', str(output)], check=True)
