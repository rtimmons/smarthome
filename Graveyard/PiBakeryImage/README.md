tasks.TODO

- resin.io
- http://elinux.org/RPi_Easy_SD_Card_Setup
- https://github.com/RPi-Distro/pi-gen

```
cd "/Library/Application Support/PiBakery/os/"
raspbian-lite-pibakery.7z
7z e raspbian-lite-pibakery.7z

diskutil list
diskutil unmountDisk /dev/disk2
brew install p7zip
brew install pv

sudo \
    dd if="raspbian-lite-pibakery-new.img" \
    | pv | \
    dd of=/dev/disk2 \
       bs=1m
```

- crib the interesting stuff from davidferguson's cool [pibakery](https://github.com/davidferguson/pibakery)

