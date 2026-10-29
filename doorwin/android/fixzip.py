# 修正 aapt2 在 Windows 上产生的反斜杠资源路径，并加入 classes.dex
import zipfile, sys

src = zipfile.ZipFile('build/base.apk', 'r')
dst = zipfile.ZipFile('build/fixed.apk', 'w', zipfile.ZIP_DEFLATED)
for item in src.infolist():
    name = item.filename.replace('\\', '/')
    if name == 'classes.dex':
        continue  # 跳过旧的 dex，稍后统一加入
    data = src.read(item.filename)
    dst.writestr(zipfile.ZipInfo(name, item.date_time), data, compress_type=item.compress_type)

with open('build/classes.dex', 'rb') as f:
    dex = f.read()
dst.writestr(zipfile.ZipInfo('classes.dex'), dex, compress_type=zipfile.ZIP_DEFLATED)
dst.close()
src.close()

z = zipfile.ZipFile('build/fixed.apk')
bad = [n for n in z.namelist() if '\\' in n]
print('entries:', len(z.namelist()), '| bad-slash:', len(bad), '| dex:', 'classes.dex' in z.namelist())
z.close()
if bad:
    sys.exit(1)
