#!/bin/sh

# Minimal pkg-config interface for the staged Miyoo sysroot. This is kept
# beside the FFplay experiment because the Windows build host has no native
# pkg-config executable.

case " $* " in
  *" --exists "*sdl*|*" --exists"*sdl*)
    exit 0
    ;;
  *" --version "*|--version)
    printf '0.29.2\n'
    exit 0
    ;;
  *" --exists "*libass*|*" --exists"*libass*)
    exit 0
    ;;
  *" --modversion "*libass*|*" --modversion"*libass*)
    printf '0.15.2\n'
    exit 0
    ;;
  *" --cflags "*libass*|*" --cflags"*libass*)
    printf '%s\n' '-I/usr/include'
    exit 0
    ;;
  *" --libs "*libass*|*" --libs"*libass*)
    printf '%s\n' '-L/usr/lib -lass -lfontconfig -lfreetype -lfribidi -lharfbuzz -lexpat -luuid -lglib-2.0 -lpcre -lpng16 -lbz2 -lz -lm -pthread'
    exit 0
    ;;
  *" --cflags "*sdl*|*" --cflags"*sdl*)
    printf '%s\n' '-I/usr/include/SDL'
    exit 0
    ;;
  *" --libs "*sdl*|*" --libs"*sdl*)
    printf '%s\n' '-L/usr/lib -lSDL'
    exit 0
    ;;
esac

exit 1
