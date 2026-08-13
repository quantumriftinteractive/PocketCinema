#include <SDL/SDL.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define MAX_ITEMS 16
#define MAX_LINE 128

static const unsigned char font[96][7] = {
    [0] = {0,0,0,0,0,0,0},
    [1] = {4,4,4,4,0,4,0},
    [2] = {10,10,0,0,0,0,0},
    [3] = {10,31,10,10,31,10,0},
    [4] = {14,20,14,5,30,4,0},
    [5] = {24,25,2,4,8,19,3},
    [6] = {12,18,20,8,21,18,13},
    [7] = {4,4,0,0,0,0,0},
    [8] = {2,4,8,8,8,4,2},
    [9] = {8,4,2,2,2,4,8},
    [10] = {0,4,21,14,21,4,0},
    [11] = {0,4,4,31,4,4,0},
    [12] = {0,0,0,0,0,4,8},
    [13] = {0,0,0,31,0,0,0},
    [14] = {0,0,0,0,0,12,12},
    [15] = {1,2,4,8,16,0,0},
    [16] = {14,17,19,21,25,17,14},
    [17] = {4,12,4,4,4,4,14},
    [18] = {14,17,1,2,4,8,31},
    [19] = {30,1,1,14,1,1,30},
    [20] = {2,6,10,18,31,2,2},
    [21] = {31,16,30,1,1,17,14},
    [22] = {6,8,16,30,17,17,14},
    [23] = {31,1,2,4,8,8,8},
    [24] = {14,17,17,14,17,17,14},
    [25] = {14,17,17,15,1,2,12},
    [26] = {0,12,12,0,12,12,0},
    [27] = {0,12,12,0,12,4,8},
    [28] = {2,4,8,16,8,4,2},
    [29] = {0,0,31,0,31,0,0},
    [30] = {8,4,2,1,2,4,8},
    [31] = {14,17,1,2,4,0,4},
    [32] = {14,17,1,13,21,21,14},
    [33] = {14,17,17,31,17,17,17},
    [34] = {30,17,17,30,17,17,30},
    [35] = {14,17,16,16,16,17,14},
    [36] = {30,17,17,17,17,17,30},
    [37] = {31,16,16,30,16,16,31},
    [38] = {31,16,16,30,16,16,16},
    [39] = {14,17,16,23,17,17,14},
    [40] = {17,17,17,31,17,17,17},
    [41] = {14,4,4,4,4,4,14},
    [42] = {7,2,2,2,18,18,12},
    [43] = {17,18,20,24,20,18,17},
    [44] = {16,16,16,16,16,16,31},
    [45] = {17,27,21,21,17,17,17},
    [46] = {17,25,21,19,17,17,17},
    [47] = {14,17,17,17,17,17,14},
    [48] = {30,17,17,30,16,16,16},
    [49] = {14,17,17,17,21,18,13},
    [50] = {30,17,17,30,20,18,17},
    [51] = {15,16,16,14,1,1,30},
    [52] = {31,4,4,4,4,4,4},
    [53] = {17,17,17,17,17,17,14},
    [54] = {17,17,17,17,17,10,4},
    [55] = {17,17,17,21,21,21,10},
    [56] = {17,17,10,4,10,17,17},
    [57] = {17,17,10,4,4,4,4},
    [58] = {31,1,2,4,8,16,31},
};

static void log_msg(const char *path, const char *msg) {
    FILE *file;
    if (!path || !*path) return;
    file = fopen(path, "a");
    if (!file) return;
    fprintf(file, "%s\n", msg);
    fclose(file);
}

static void rect(SDL_Surface *screen, int x, int y, int w, int h, Uint32 color) {
    SDL_Rect area = {screen->w - x - w, screen->h - y - h, w, h};
    SDL_FillRect(screen, &area, color);
}

static void draw_char(SDL_Surface *screen, char character, int x, int y, int scale, Uint32 color) {
    const unsigned char *glyph;
    int row;
    int column;
    if (character >= 'a' && character <= 'z') character -= 32;
    if (character < 32 || character > 122) character = '?';
    glyph = font[(int)character - 32];
    for (row = 0; row < 7; row++) {
        for (column = 0; column < 5; column++) {
            if (glyph[row] & (1 << (4 - column))) {
                rect(screen, x + column * scale, y + row * scale, scale, scale, color);
            }
        }
    }
}

static void draw_text(SDL_Surface *screen, const char *value, int x, int y,
                      int scale, Uint32 color, int max_chars) {
    const char *cursor;
    int count = 0;
    for (cursor = value; *cursor && count < max_chars; cursor++, count++) {
        draw_char(screen, *cursor, x + count * 6 * scale, y, scale, color);
    }
}

static void draw_menu(SDL_Surface *screen, const char *title, const char *bottom,
                      char **items, int count, int selected) {
    Uint32 background = SDL_MapRGB(screen->format, 12, 14, 18);
    Uint32 row = SDL_MapRGB(screen->format, 30, 84, 116);
    Uint32 white = SDL_MapRGB(screen->format, 240, 244, 248);
    Uint32 muted = SDL_MapRGB(screen->format, 170, 180, 190);
    Uint32 accent = SDL_MapRGB(screen->format, 255, 222, 120);
    int index;

    SDL_FillRect(screen, NULL, background);
    draw_text(screen, title, 20, 18, 3, white, 32);

    for (index = 0; index < count; index++) {
        int y = 92 + index * 52;
        if (index == selected) {
            rect(screen, 14, y - 10, 612, 38, row);
            draw_text(screen, ">", 24, y, 2, accent, 1);
        }
        if (strncmp(items[index], "https://", 8) == 0) {
            draw_text(screen, items[index], 52, y + 5, 1,
                      index == selected ? white : muted, 90);
        } else {
            draw_text(screen, items[index], 52, y, 2,
                      index == selected ? white : muted, 45);
        }
    }

    draw_text(screen, bottom, 20, 440, 2, muted, 48);
    SDL_Flip(screen);
}

int main(int argc, char **argv) {
    const char *title = argc > 1 ? argv[1] : "Tailscale";
    const char *bottom = argc > 2 ? argv[2] : "A Select  B Exit";
    const char *log_path = getenv("ONION_TAILSCALE_SELECTOR_LOG");
    char *items[MAX_ITEMS];
    char line[MAX_LINE];
    int count = 0;
    int selected = 0;
    int done = 0;
    int result = 1;
    int result_fd;
    FILE *result_out;
    SDL_Surface *screen;

    while (count < MAX_ITEMS && fgets(line, sizeof(line), stdin)) {
        line[strcspn(line, "\r\n")] = '\0';
        if (!line[0]) continue;
        items[count] = strdup(line);
        if (!items[count]) return 2;
        count++;
    }
    if (count == 0) return 3;

    result_fd = dup(STDOUT_FILENO);
    result_out = result_fd >= 0 ? fdopen(result_fd, "w") : NULL;
    if (!result_out || !freopen("/dev/null", "w", stdout)) return 4;

    if (SDL_Init(SDL_INIT_VIDEO) != 0) {
        log_msg(log_path, SDL_GetError());
        return 5;
    }
    SDL_ShowCursor(SDL_DISABLE);
    SDL_EnableKeyRepeat(250, 80);
    screen = SDL_SetVideoMode(640, 480, 32, SDL_SWSURFACE);
    if (!screen) {
        log_msg(log_path, SDL_GetError());
        SDL_Quit();
        return 6;
    }

    draw_menu(screen, title, bottom, items, count, selected);
    while (!done) {
        SDL_Event event;
        if (!SDL_WaitEvent(&event)) continue;
        if (event.type == SDL_QUIT) {
            done = 1;
        } else if (event.type == SDL_KEYDOWN) {
            SDLKey key = event.key.keysym.sym;
            char message[96];
            snprintf(message, sizeof(message), "selector key=%d selected=%d", (int)key, selected);
            log_msg(log_path, message);
            if (key == SDLK_UP) {
                selected = selected > 0 ? selected - 1 : count - 1;
                draw_menu(screen, title, bottom, items, count, selected);
            } else if (key == SDLK_DOWN) {
                selected = selected + 1 < count ? selected + 1 : 0;
                draw_menu(screen, title, bottom, items, count, selected);
            } else if (key == SDLK_SPACE || key == SDLK_RETURN || key == SDLK_LALT) {
                result = 0;
                done = 1;
            } else if (key == SDLK_LCTRL || key == SDLK_ESCAPE || key == SDLK_BACKSPACE) {
                result = 1;
                done = 1;
            }
        }
    }

    SDL_Quit();
    if (result == 0) {
        fprintf(result_out, "%s\n", items[selected]);
        fflush(result_out);
    }
    fclose(result_out);
    while (count > 0) free(items[--count]);
    return result;
}
