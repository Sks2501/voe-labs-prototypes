"""Build a small signed APK with the installed official SDK, without Gradle downloads."""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile
import xml.etree.ElementTree as ET


def main():
    parser=argparse.ArgumentParser()
    for name in ('sdk','java','signing-key','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    source=Path(__file__).resolve().parent/'app'/'src'/'main'
    manifest=ET.parse(source/'AndroidManifest.xml').getroot()
    namespace='{http://schemas.android.com/apk/res/android}'
    version=manifest.attrib[namespace+'versionName'];version_code=int(manifest.attrib[namespace+'versionCode'])
    if not re.fullmatch(r'\d+\.\d+\.\d+',version):raise ValueError('Invalid release version')
    filename='sexta-feira-android-'+version+'.apk'
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    if shutil.disk_usage(output).free<512*1024**2:
        raise RuntimeError('At least 512 MiB free required on build volume')
    work=Path(tempfile.mkdtemp(prefix='android-build-',dir=output))
    tools=args.sdk/'build-tools'/'35.0.0'
    android=args.sdk/'platforms'/'android-35'/'android.jar'
    java=args.java/'bin'/'java.exe';javac=args.java/'bin'/'javac.exe'
    for path in (java,javac,android,tools/'aapt2.exe',tools/'lib'/'d8.jar',tools/'lib'/'apksigner.jar',args.signing_key):
        if not path.is_file():raise FileNotFoundError(path)
    if not os.environ.get('SEXTA_ANDROID_STOREPASS'):
        raise RuntimeError('Release password must be supplied through the private process environment')
    env=dict(os.environ,TEMP=str(work),TMP=str(work))
    def run(*command):
        subprocess.run([str(item) for item in command],check=True,env=env,cwd=work)
    resources=work/'resources.zip';unsigned=work/'unsigned.apk';aligned=work/'aligned.apk'
    classes=work/'classes';generated=work/'generated';dex=work/'dex';tests=work/'test-classes'
    for path in (classes,generated,dex,tests):path.mkdir()
    run(tools/'aapt2.exe','compile','--dir',source/'res','-o',resources)
    run(tools/'aapt2.exe','link','-o',unsigned,'-I',android,'--manifest',source/'AndroidManifest.xml','--java',generated,resources)
    policy=source/'java'/'online'/'teambike'/'sextafeira'/'OriginPolicy.java'
    run(javac,'-encoding','UTF-8','-d',tests,policy,Path(__file__).parent/'tests'/'OriginPolicyTest.java')
    run(java,'-cp',tests,'online.teambike.sextafeira.OriginPolicyTest')
    sources=sorted((source/'java').rglob('*.java'))+sorted(generated.rglob('*.java'))
    run(javac,'-encoding','UTF-8','-source','8','-target','8','-classpath',android,'-d',classes,*sources)
    classjar=work/'classes.jar'
    with zipfile.ZipFile(classjar,'w') as archive:
        for path in sorted(classes.rglob('*.class')):archive.write(path,path.relative_to(classes).as_posix())
    run(java,'-Xmx512m','-cp',tools/'lib'/'d8.jar','com.android.tools.r8.D8','--release','--min-api','26','--lib',android,'--output',dex,classjar)
    with zipfile.ZipFile(unsigned,'a',compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(dex.glob('*.dex')):archive.write(path,path.name)
    run(tools/'zipalign.exe','-f','4',unsigned,aligned)
    apk=work/filename
    signer=tools/'lib'/'apksigner.jar'
    run(java,'-jar',signer,'sign','--ks',args.signing_key,'--ks-key-alias','sexta-feira','--ks-pass','env:SEXTA_ANDROID_STOREPASS','--key-pass','env:SEXTA_ANDROID_STOREPASS','--out',apk,aligned)
    verified=subprocess.run([str(java),'-jar',str(signer),'verify','--verbose','--print-certs',str(apk)],check=True,env=env,cwd=work,capture_output=True,text=True)
    print(verified.stdout)
    certificate=re.search(r'certificate SHA-256 digest: ([a-f0-9]{64})',verified.stdout).group(1)
    run(tools/'zipalign.exe','-c','4',apk)
    run(tools/'aapt.exe','dump','badging',apk)
    def file_hash(path):
        with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
    digest=file_hash(apk)
    final=output/filename
    if final.exists() and file_hash(final)!=digest:
        raise RuntimeError('Existing release preserved; increment version instead of replacing a different APK')
    if not final.exists():shutil.copyfile(apk,final)
    receipt={'version':version,'version_code':version_code,'package':'online.teambike.sextafeira','min_android':'8.0','min_sdk':26,
        'target_sdk':35,'bytes':final.stat().st_size,'sha256':digest,'filename':final.name,
        'api_origin':'https://sexta.teambike.online','native_origin_checks':14,'sdk_build_tools':'35.0.0','certificate_sha256':certificate}
    (output/'android-release.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(receipt))


if __name__=='__main__':main()
