#!/bin/sh
# Build modem73 (upstream RFnexus/modem73) as headless Windows exe, cross from Linux.
# Linux: g++-mingw-w64. Windows: MSYS2 MINGW64 shell with CC=gcc CXX=g++ sh build-modem73-win.sh
# Needs: git, x86_64-w64-mingw32-g++ (Debian/Ubuntu: g++-mingw-w64-x86-64-posix),
#        and modem73-win-oe3gas.patch next to this script.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
[ -d modem73 ] || git clone https://github.com/RFnexus/modem73.git
cd modem73
git checkout -- . && git clean -fdq
patch -p1 < "$HERE/modem73-win-oe3gas.patch"
VER=$(sed -n 's/^BASE_VERSION := //p' Makefile)-win
CC=${CC:-x86_64-w64-mingw32-gcc}; CXX=${CXX:-x86_64-w64-mingw32-g++}
I="-Ideps/aicodix/dsp -Ideps/aicodix/code -Ideps/aicodix/modem"
$CC -c -O2 -o deps/miniaudio.o deps/miniaudio.c
$CC -c -O2 -o deps/cJSON.o deps/cJSON.c
$CXX -std=c++17 -O3 -DMODEM73_VERSION=\"$VER\" $I kiss_tnc.cc deps/miniaudio.o deps/cJSON.o \
     -o modem73.exe -static -lws2_32 -lsetupapi -lole32
echo "built modem73/modem73.exe ($VER, headless)"
