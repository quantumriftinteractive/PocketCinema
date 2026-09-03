#include <SDL/SDL.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include "qrcodegen.h"

#define MAX_ITEMS 64
#define MAX_LINE 256
#define MAX_QR_TEXT 1024

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

static int write_action(const char *path, const char *action) {
    FILE *f;
    int ok;
    if (!path || !*path || !action || !*action) return 0;
    f = fopen(path, "w");
    if (!f) return 0;
    ok = fprintf(f, "%s\n", action) >= 0;
    if (fclose(f) != 0) ok = 0;
    return ok;
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

static int has_line_break(const char *text) {
    return text && strstr(text, "\\n") != NULL;
}

static int update_dynamic_first_item(char **items, int count, const char *path) {
    char value[MAX_LINE];
    char *replacement;
    FILE *file;

    if (!path || !*path || count < 1) return 0;
    file = fopen(path, "r");
    if (!file) return 0;
    if (!fgets(value, sizeof(value), file)) {
        fclose(file);
        return 0;
    }
    fclose(file);
    if (!strchr(value, '\n') && strlen(value) == sizeof(value) - 1) return 0;
    value[strcspn(value, "\r\n")] = '\0';
    if (!value[0] || strchr(value, '\t') || strcmp(items[0], value) == 0) return 0;
    replacement = strdup(value);
    if (!replacement) return 0;
    free(items[0]);
    items[0] = replacement;
    return 1;
}

static void draw_item(SDL_Surface *screen, const char *text, int x, int y,
                      int scale, Uint32 color, int max_chars, int max_lines) {
    int line = 0;
    int column = 0;
    int n = 0;
    for (const char *p = text; *p && line < max_lines && n < max_chars * max_lines; p++, n++) {
        if (*p == '\\' && p[1] == 'n') {
            line++;
            column = 0;
            p++;
            continue;
        }
        if (column < max_chars) {
            draw_char(screen, *p, x + column * 6 * scale,
                      y + line * 18, scale, color);
            column++;
        }
    }
}

static void draw_menu(SDL_Surface *screen, const char *title, const char *bottom, char **items, int count, int selected) {
    Uint32 bg = SDL_MapRGB(screen->format, 12, 14, 18);
    Uint32 row = SDL_MapRGB(screen->format, 30, 84, 116);
    Uint32 white = SDL_MapRGB(screen->format, 240, 244, 248);
    Uint32 muted = SDL_MapRGB(screen->format, 170, 180, 190);
    Uint32 accent = SDL_MapRGB(screen->format, 255, 222, 120);
    SDL_FillRect(screen, NULL, bg);

    draw_text(screen, title ? title : "POCKETCINEMA", 20, 18, 3, white, 32);

    int multiline = 0;
    for (int i = 0; i < count; i++) {
        if (has_line_break(items[i])) {
            multiline = 1;
            break;
        }
    }
    int visible = multiline ? 4 : 8;
    int row_height = multiline ? 80 : 40;
    int row_box_height = multiline ? 72 : 34;
    int start = selected - visible / 2;
    if (start < 0) start = 0;
    if (start > count - visible) start = count - visible;
    if (start < 0) start = 0;

    for (int i = 0; i < visible && start + i < count; i++) {
        int idx = start + i;
        int y = 78 + i * row_height;
        if (idx == selected) {
            rect(screen, 14, y - 8, 612, row_box_height, row);
            draw_text(screen, ">", 24, y, 2, accent, 1);
        }
        draw_item(screen, items[idx], 52, y, 2, idx == selected ? white : muted,
                  45, multiline ? 3 : 1);
    }

    draw_text(screen, bottom ? bottom : "UP/DOWN MOVE  A SELECT  B BACK", 20, 440, 2, muted, 48);
    SDL_Flip(screen);
}

static void draw_qr(SDL_Surface *screen, const char *title, const char *bottom,
                    const char *value, const uint8_t qrcode[]) {
    Uint32 background = SDL_MapRGB(screen->format, 12, 14, 18);
    Uint32 white = SDL_MapRGB(screen->format, 255, 255, 255);
    Uint32 black = SDL_MapRGB(screen->format, 0, 0, 0);
    Uint32 muted = SDL_MapRGB(screen->format, 170, 180, 190);
    int size = qrcodegen_getSize(qrcode);
    int total = size + 8;
    int scale = 340 / total;
    int pixels;
    int origin_x;
    int origin_y;
    int x;
    int y;

    if (scale < 1) scale = 1;
    pixels = total * scale;
    origin_x = (screen->w - pixels) / 2;
    origin_y = 48 + (340 - pixels) / 2;
    SDL_FillRect(screen, NULL, background);
    draw_text(screen, title, 20, 16, 3, white, 32);
    rect(screen, origin_x, origin_y, pixels, pixels, white);
    for (y = 0; y < size; y++) {
        for (x = 0; x < size; x++) {
            if (qrcodegen_getModule(qrcode, x, y)) {
                rect(screen, origin_x + (x + 4) * scale,
                     origin_y + (y + 4) * scale, scale, scale, black);
            }
        }
    }
    draw_text(screen, value, 20, 398, 1, muted, 100);
    draw_text(screen, bottom, 20, 438, 2, muted, 48);
    SDL_Flip(screen);
}

int main(int argc, char **argv) {
    int qr_mode = argc > 1 && strcmp(argv[1], "--qr") == 0;
    const char *title = argc > (qr_mode ? 2 : 1) ? argv[qr_mode ? 2 : 1] : "PocketCinema";
    const char *bottom = argc > (qr_mode ? 3 : 2) ? argv[qr_mode ? 3 : 2] : "Up/Down move  A select  B back";
    /* Retained compiled-helper ABI; not a user configuration key. */
    const char *log_path = getenv("POCKETSTREMIO_SELECTOR_LOG");
    const char *dynamic_first_item_path =
        getenv("POCKETSTREMIO_DYNAMIC_FIRST_ITEM_FILE");
    const char *x_action_path = getenv("POCKETSTREMIO_SELECTOR_X_ACTION_FILE");
    char *items[MAX_ITEMS];
    char line[MAX_LINE];
    char qr_text[MAX_QR_TEXT];
    uint8_t temp_buffer[qrcodegen_BUFFER_LEN_MAX];
    uint8_t qrcode[qrcodegen_BUFFER_LEN_MAX];
    int count = 0;

    if (qr_mode) {
        if (!fgets(qr_text, sizeof(qr_text), stdin)) return 3;
        if (!strchr(qr_text, '\n') && !feof(stdin)) return 3;
        qr_text[strcspn(qr_text, "\r\n")] = '\0';
        if (!qr_text[0] ||
            !qrcodegen_encodeText(qr_text, temp_buffer, qrcode,
                                  qrcodegen_Ecc_MEDIUM,
                                  qrcodegen_VERSION_MIN, 20,
                                  qrcodegen_Mask_AUTO, true)) {
            return 3;
        }
    } else {
        while (count < MAX_ITEMS && fgets(line, sizeof(line), stdin)) {
            line[strcspn(line, "\r\n")] = '\0';
            if (!line[0]) continue;
            items[count] = strdup(line);
            if (!items[count]) return 2;
            count++;
        }
        if (count == 0) return 3;
    }

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
    const char *result_action = "cancel";
    Uint32 last_dynamic_check = 0;
    if (!qr_mode) {
        update_dynamic_first_item(items, count, dynamic_first_item_path);
    }
    if (qr_mode) {
        draw_qr(screen, title, bottom, qr_text, qrcode);
    } else {
        draw_menu(screen, title, bottom, items, count, selected);
    }

    while (!done) {
        SDL_Event event;
        if (!qr_mode && dynamic_first_item_path && *dynamic_first_item_path) {
            Uint32 now = SDL_GetTicks();
            if (now - last_dynamic_check >= 200) {
                if (update_dynamic_first_item(
                        items, count, dynamic_first_item_path)) {
                    draw_menu(screen, title, bottom, items, count, selected);
                }
                last_dynamic_check = now;
            }
            if (!SDL_PollEvent(&event)) {
                SDL_Delay(20);
                continue;
            }
        } else if (!SDL_WaitEvent(&event)) {
            continue;
        }
        if (event.type == SDL_QUIT) {
            done = 1;
        } else if (event.type == SDL_KEYDOWN) {
            SDLKey key = event.key.keysym.sym;
            char buf[96];
            snprintf(buf, sizeof(buf), "sdl-selector key=%d selected=%d", (int)key, selected);
            log_msg(log_path, buf);
            if (key == SDLK_UP) {
                if (!qr_mode) {
                    selected = selected > 0 ? selected - 1 : count - 1;
                    draw_menu(screen, title, bottom, items, count, selected);
                }
            } else if (key == SDLK_DOWN) {
                if (!qr_mode) {
                    selected = selected + 1 < count ? selected + 1 : 0;
                    draw_menu(screen, title, bottom, items, count, selected);
                }
            } else if (key == SDLK_SPACE || key == SDLK_RETURN || key == SDLK_LALT) {
                rc = 0;
                result_action = qr_mode ? "refresh" : "select";
                done = 1;
            } else if (!qr_mode && key == SDLK_LSHIFT &&
                       x_action_path && *x_action_path) {
                if (write_action(x_action_path, "x")) {
                    rc = 0;
                    result_action = "x";
                    done = 1;
                } else {
                    log_msg(log_path, "sdl-selector could not write X action");
                }
            } else if (key == SDLK_LCTRL || key == SDLK_ESCAPE || key == SDLK_BACKSPACE) {
                rc = 1;
                result_action = "cancel";
                done = 1;
            }
        }
    }

    char buf[160];
    snprintf(buf, sizeof(buf),
             "sdl-selector exit rc=%d action=%s selected_index=%d selected_value=%s",
             rc, result_action, selected,
             rc == 0 ? (qr_mode ? "refresh" : items[selected]) : "");
    log_msg(log_path, buf);

    SDL_Quit();
    if (rc == 0) {
        fprintf(result_out, "%s\n", qr_mode ? "refresh" : items[selected]);
        fflush(result_out);
    }
    fclose(result_out);
    for (int i = 0; i < count; i++) free(items[i]);
    return rc;
}
