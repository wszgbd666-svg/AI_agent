# 校验 APK 内容：条目名必须为正斜杠，且包含关键资源
import zipfile, sys

apk = sys.argv[1] if len(sys.argv) > 1 else 'doorwin.apk'
z = zipfile.ZipFile(apk)
names = z.namelist()
bad = [n for n in names if '\\' in n]
need = ['assets/index.html', 'assets/js/main.js', 'assets/lib/three.min.js',
        'classes.dex', 'AndroidManifest.xml']
missing = [n for n in need if n not in names]
print('entries:', len(names))
print('bad-slash entries:', len(bad), bad[:3])
print('missing:', missing)
z.close()
sys.exit(1 if bad or missing else 0)
