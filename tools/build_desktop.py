"""Build on the target OS. Keep build output away from the checked-in dist/ UI."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import sysconfig
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from version import VERSION


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT / 'release-artifacts' / 'desktop')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    work = ROOT / 'data' / 'desktop-build'
    work.mkdir(parents=True, exist_ok=True)
    if sys.platform not in ('win32', 'darwin'):
        raise SystemExit('Build Windows on Windows and macOS on macOS.')
    name = 'Zhuyi'
    licenses = work / 'runtime-licenses'
    licenses.mkdir(exist_ok=True)
    candidates = [Path(sys.base_prefix) / 'LICENSE.txt', Path(sysconfig.get_path('stdlib')) / 'LICENSE.txt']
    python_license = next((p for p in candidates if p.is_file()), ROOT / 'desktop-resources' / 'PYTHON-LICENSE.txt')
    shutil.copyfile(python_license, licenses / 'PYTHON-LICENSE.txt')
    distribution = importlib.metadata.distribution('pyinstaller')
    bootloader_license = next(distribution.locate_file(p) for p in distribution.files if str(p).endswith('/licenses/COPYING.txt'))
    shutil.copyfile(bootloader_license, licenses / 'PYINSTALLER-COPYING.txt')
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--onedir', '--windowed',
               '--name', name, '--distpath', str(work / 'bundle'), '--workpath', str(work / 'work'),
               '--specpath', str(work), '--icon', str(ROOT / 'dist' / 'logo.png'),
               '--add-data', str(ROOT / 'dist') + ':dist',
               '--add-data', str(ROOT / 'LICENSE') + ':.', '--add-data', str(ROOT / 'NOTICE') + ':.',
               '--add-data', str(ROOT / 'README.md') + ':.']
    command += ['--add-data', str(licenses) + ':runtime-licenses']
    if sys.platform == 'darwin':
        command += ['--osx-bundle-identifier', 'com.zhuyi.attention.local.v1']
    command += [str(ROOT / 'desktop.py')]
    subprocess.run(command, cwd=ROOT, check=True)
    if sys.platform == 'win32':
        bundle = work / 'bundle' / name
        executable = bundle / 'Zhuyi.exe'
        archive = output / f'Zhuyi-v{VERSION}-Windows-x64.zip'
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            for p in sorted(bundle.rglob('*')):
                if p.is_file():
                    z.write(p, 'Zhuyi/' + p.relative_to(bundle).as_posix())
            z.write(ROOT / 'README.md', 'Zhuyi/README.md')
            z.write(ROOT / 'LICENSE', 'Zhuyi/LICENSE')
            z.write(ROOT / 'NOTICE', 'Zhuyi/NOTICE')
    else:
        bundle = work / 'bundle' / (name + '.app')
        executable = bundle / 'Contents' / 'MacOS' / name
        architecture = 'arm64' if platform.machine() == 'arm64' else 'x64'
        archive = output / f'Zhuyi-v{VERSION}-macOS-{architecture}.zip'
        subprocess.run(['ditto', '-c', '-k', '--sequesterRsrc', '--keepParent', str(bundle), str(archive)], check=True)
    # Exercise the actual bundled executable with a fresh temporary database.
    subprocess.run([sys.executable, str(ROOT / 'tools' / 'smoke_desktop.py'), str(executable)], check=True)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix('.zip.sha256').write_text(digest + '  ' + archive.name + '\n', encoding='ascii')
    print(json.dumps({'archive': str(archive), 'bytes': archive.stat().st_size, 'sha256': digest}))


if __name__ == '__main__':
    main()
