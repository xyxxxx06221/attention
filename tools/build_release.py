"""Build the local release from an explicit source allowlist, never runtime data."""
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from version import VERSION


def build():
    files=list(ROOT.glob('*.py'))
    files += [ROOT/name for name in ('LICENSE','NOTICE','README.md','SECURITY.md','启动主一.bat','停止主一.bat','启动主一.command','停止主一.command')]
    for folder in ('dist','docs','examples'):
        files += [p for p in (ROOT/folder).rglob('*') if p.is_file() and p.name!='review.css']
    files += [ROOT/'tools'/'agent_import.py']
    files=sorted(set(files))
    for p in files:
        relative=p.relative_to(ROOT)
        if any(part in ('data','.git','__pycache__') for part in relative.parts) or p.suffix in ('.db','.sqlite','.log','.key'):
            raise ValueError('Refusing runtime data: '+str(relative))
    output=ROOT/'release-artifacts'
    output.mkdir(exist_ok=True)
    archive=output/f'Zhuyi-v{VERSION}-local.zip'
    manifest={str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in files:z.write(p,f'Zhuyi-v{VERSION}/'+p.relative_to(ROOT).as_posix())
        z.writestr(f'Zhuyi-v{VERSION}/MANIFEST.json',json.dumps({'version':VERSION,'files':manifest},indent=2,ensure_ascii=False))
    checksum=hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix('.sha256').write_text(checksum+'  '+archive.name+'\n',encoding='ascii')
    print(json.dumps({'archive':str(archive),'files':len(files),'bytes':archive.stat().st_size,'sha256':checksum},ensure_ascii=False))
    return archive


if __name__=='__main__':build()
