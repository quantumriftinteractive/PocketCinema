#include <SDL/SDL.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define MAX_ITEMS 64
#define MAX_LINE 256

static const unsigned char font[96][7] = {
    [0] = {0,0,0,0,0,0,0},          /* space */
    [1] = {4,4,4,4,0,4,0},          /* ! */
    [2] = {10,10,0,0,0,0,0},        /* " */
    [3] = {10,31,10,10,31,10,0},    /* # */
    [4] = {14,20,14,5,30,4,0},      /* $ */
    [5] = {24,25,2,4,8,19,3},       /* % */
    [6] = {12,18,20,8,21,18,13},    /* & */
    [7] = {4,4,0,0,0,0,0},          /* ' */
    [8] = {2,4,8,8,8,4,2},          /* ( */
    [9] = {8,4,2,2,2,4,8},          /* ) */
    [10] = {0,4,21,14,21,4,0},      /* * */
    [11] = {0,4,4,31,4,4,0},        /* + */
    [12] = {0,0,0,0,0,4,8},         /* , */
    [13] = {0,0,0,31,0,0,0},        /* - */
    [14] = {0,0,0,0,0,12,12},       /* . */
    [15] = {1,2,4,8,16,0,0},        /* / */
    [16] = {14,17,19,21,25,17,14},  /* 0 */
    [17] = {4,12,4,4,4,4,14},       /* 1 */
    [18] = {14,17,1,2,4,8,31},      /* 2 */
    [19] = {30,1,1,14,1,1,30},      /* 3 */
    [20] = {2,6,10,18,31,2,2},      /* 4 */
    [21] = {31,16,30,1,1,17,14},    /* 5 */
    [22] = {6,8,16,30,17,17,14},    /* 6 */
    [23] = {31,1,2,4,8,8,8},        /* 7 */
    [24] = {14,17,17,14,17,17,14},  /* 8 */
    [25] = {14,17,17,15,1,2,12},    /* 9 */
    [26] = {0,12,12,0,12,12,0},     /* : */
    [27] = {0,12,12,0,12,4,8},      /* ; */
    [28] = {2,4,8,16,8,4,2},        /* < */
    [29] = {0,0,31,0,31,0,0},       /* = */
    [30] = {8,4,2,1,2,4,8},         /* > */
    [31] = {14,17,1,2,4,0,4},       /* ? */
    [32] = {14,17,1,13,21,21,14},   /* @ */
    [33] = {14,17,17,31,17,17,17},  /* A */
    [34] = {30,17,17,30,17,17,30},  /* B */
    [35] = {14,17,16,16,16,17,14},  /* C */
    [36] = {30,17,17,17,17,17,30},  /* D */
    [37] = {31,16,16,30,16,16,31},  /* E */
    [38] = {31,16,16,30,16,16,16},  /* F */
    [39] = {14,17,16,23,17,17,14},  /* G */
    [40] = {17,17,17,31,17,17,17},  /* H */
    [41] = {14,4,4,4,4,4,14},       /* I */
    [42] = {7,2,2,2,18,18,12},      /* J */
    [43] = {17,18,20,24,20,18,17},  /* K */
    [44] = {16,16,16,16,16,16,31},  /* L */
    [45] = {17,27,21,21,17,17,17},  /* M */
    [46] = {17,25,21,19,17,17,17},  /* N */
    [47] = {14,17,17,17,17,17,14},  /* O */
    [48] = {30,17,17,30,16,16,16},  /* P */
    [49] = {14,17,17,17,21,18,13},  /* Q */
    [50] = {30,17,17,30,20,18,17},  /* R */
    [51] = {15,16,16,14,1,1,30},    /* S */
    [52] = {31,4,4,4,4,4,4},        /* T */
    [53] = {17,17,17,17,17,17,14},  /* U */
    [54] = {17,17,17,17,17,10,4},   /* V */
    [55] = {17,17,17,21,21,21,10},  /* W */
    [56] = {17,17,10,4,10,17,17},   /* X */
    [57] = {17,17,10,4,4,4,4},      /* Y */
    [58] = {31,1,2,4,8,16,31},      /* Z */
};

static void log_msg(const char *path, const char *msg) {
    if (!path || !*path) return;
    FILE *f = fopen(path, "a");
    if (!f) return;
    fprintf(f, "%s\n", msg);
    fclose(f);
}

static void rect(SDL_Surface *screen, int x, int y, int w, int h, Uint32 color) {
    SDL_Rect r = {screen->w - x - w, screen->h - y - h, w, h};
    SDL_FillRect(screen, &r, color);
}

static void draw_char(SDL_Surface *screen, char c, int x, int y, int scale, Uint32 color) {
    if (c >= 'a' && c <= 'z') c -= 32;
    if (c < 32 || c > 122) c = '?';
    const unsigned char *glyph = font[(int)c - 32];
    for (int row = 0; row < 7; row++) {
        for (int col = 0; col < 5; col++) {
            if (glyph[row] & (1 << (4 - col))) {
                rect(screen, x + col * scale, y + row * scale, scale, scale, color);
            }
        }
    }
}

static void draw_text(SDL_Surface *screen, const char *text, int x, int y, int scale, Uint32 color, int max_chars) {
    int n = 0;
    for (const char *p = text; *p && n < max_chars; p++, n++) {
        draw_char(screen, *p, x + n * 6 * scale, y, scale, color);
    }
}

static void draw_menu(SDL_Surface *screen, const char *title, const char *bottom, char **items, int count, int selected) {
    Uint32 bg = SDL_MapRGB(screen->format, 12, 14, 18);
    Uint32 row = SDL_MapRGB(screen->format, 30, 84, 116);
    Uint32 white = SDL_MapRGB(screen->format, 240, 244, 248);
    Uint32 muted = SDL_MapRGB(screen->format, 170, 180, 190);
    Uint32 accent = SDL_MapRGB(screen->format, 255, 222, 120);
    SDL_FillRect(screen, NULL, bg);

    draw_text(screen, title ? title : "POCKETSTREMIO", 20, 18, 3, white, 32);

    int visible = 8;
    int start = selected - visible / 2;
    if (start < 0) start = 0;
    if (start > count - visible) start = count - visible;
    if (start < 0) start = 0;

    for (int i = 0; i < visible && start + i < count; i++) {
        int idx = start + i;
        int y = 78 + i * 40;
        if (idx == selected) {
            rect(screen, 14, y - 8, 612, 34, row);
            draw_text(screen, ">", 24, y, 2, accent, 1);
        }
        draw_text(screen, items[idx], 52, y, 2, idx == selected ? white : muted, 45);
    }

    draw_text(screen, bottom ? bottom : "UP/DOWN MOVE  A SELECT  B BACK", 20, 440, 2, muted, 48);
    SDL_Flip(screen);
}

int main(int argc, char **argv) {
    const char *title = argc > 1 ? argv[1] : "PocketStremio";
    const char *bottom = argc > 2 ? argv[2] : "Up/Down move  A select  B back";
    const char *log_path = getenv("POCKETSTREMIO_SELECTOR_LOG");
    char *items[MAX_ITEMS];
    char line[MAX_LINE];
    int count = 0;

    while (count < MAX_ITEMS && fgets(line, sizeof(line), stdin)) {
        line[strcspn(line, "\r\n")] = '\0';
        if (!line[0]) continue;
        items[count] = strdup(line);
        if (!items[count]) return 2;
        count++;
    }
    if (count == 0) return 3;

    /* The vendor SDL backend writes diagnostics to stdout. Keep stdout clean
       because the caller uses it as the selector's structured result. */
    int result_fd = dup(STDOUT_FILENO);
    FILE *result_out = result_fd >= 0 ? fdopen(result_fd, "w") : NULL;
    if (!result_out || !freopen("/dev/null", "w", stdout)) return 4;

    if (SDL_Init(SDL_INIT_VIDEO) != 0) {
        log_msg(log_path, SDL_GetError());
        return 5;
    }
    SDL_ShowCursor(SDL_DISABLE);
    SDL_EnableKeyRepeat(250, 80);
    SDL_Surface *screen = SDL_SetVideoMode(640, 480, 32, SDL_SWSURFACE);
    if (!screen) {
        log_msg(log_path, SDL_GetError());
        SDL_Quit();
        return 6;
    }

    int selected = 0;
    int done = 0;
    int rc = 1;
    draw_menu(screen, title, bottom, items, count, selected);

    while (!done) {
        SDL_Event event;
        if (!SDL_WaitEvent(&event)) continue;
        if (event.type == SDL_QUIT) {
            done = 1;
        } else if (event.type == SDL_KEYDOWN) {
            SDLKey key = event.key.keysym.sym;
            char buf[96];
            snprintf(buf, sizeof(buf), "sdl-selector key=%d selected=%d", (int)key, selected);
            log_msg(log_path, buf);
            if (key == SDLK_UP) {
                selected = selected > 0 ? selected - 1 : count - 1;
                draw_menu(screen, title, bottom, items, count, selected);
            } else if (key == SDLK_DOWN) {
                selected = selected + 1 < count ? selected + 1 : 0;
                draw_menu(screen, title, bottom, items, count, selected);
            } else if (key == SDLK_SPACE || key == SDLK_RETURN || key == SDLK_LALT) {
                rc = 0;
                done = 1;
            } else if (key == SDLK_LCTRL || key == SDLK_ESCAPE || key == SDLK_BACKSPACE) {
                rc = 1;
                done = 1;
            }
        }
    }

    char buf[160];
    snprintf(buf, sizeof(buf), "sdl-selector exit rc=%d selected_index=%d selected_value=%s",
             rc, selected, rc == 0 ? items[selected] : "");
    log_msg(log_path, buf);

    SDL_Quit();
    if (rc == 0) {
        fprintf(result_out, "%s\n", items[selected]);
        fflush(result_out);
    }
    fclose(result_out);
    for (int i = 0; i < count; i++) free(items[i]);
    return rc;
}
