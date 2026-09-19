import zipfile
SRC = '/home/rjmendez/flock-alpr/re/android-fs/system/app/flock-object/flock-object.apk'
z = zipfile.ZipFile(SRC)
info = z.getinfo('AndroidManifest.xml')
print('compress_type', info.compress_type, 'size', info.file_size, 'compress_size', info.compress_size)
data = z.read('AndroidManifest.xml')
with open('/home/rjmendez/flock-alpr/re/deep/swarm/jni-harness/patch/rawmanifest/AndroidManifest.xml.bin', 'wb') as f:
    f.write(data)
print('written', len(data))
