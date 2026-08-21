#include <errno.h>
#include <fcntl.h>
#include <linux/input.h>
#include <poll.h>
#include <signal.h>
#include <stdio.h>
#include <unistd.h>

static volatile sig_atomic_t running = 1;

static void stop_control(int signal_number)
{
    (void)signal_number;
    running = 0;
}

static int seek_delta(unsigned int code)
{
    switch (code) {
    case KEY_UP:
        return 60;
    case KEY_DOWN:
        return -60;
    case KEY_LEFT:
        return -10;
    case KEY_RIGHT:
        return 10;
    case KEY_PAGEUP:
        return 600;
    case KEY_PAGEDOWN:
        return -600;
    default:
        return 0;
    }
}

int main(int argc, char **argv)
{
    struct input_event event;
    struct pollfd input;
    const char *control_path;
    const char *log_path = NULL;
    FILE *control;
    FILE *log_file;

    if (argc != 2) {
        fprintf(stderr, "usage: %s CONTROL_FILE\n", argv[0]);
        return 1;
    }
    control_path = argv[1];
    if (argc >= 3)
        log_path = argv[2];
    signal(SIGINT, stop_control);
    signal(SIGTERM, stop_control);

    input.fd = open("/dev/input/event0", O_RDONLY | O_NONBLOCK);
    if (input.fd < 0) {
        perror("playback control: /dev/input/event0");
        return 2;
    }
    input.events = POLLIN;

    /* Discard selector/menu events queued before FFplay became visible. */
    while (read(input.fd, &event, sizeof(event)) == sizeof(event))
        ;

    while (running) {
        int poll_result = poll(&input, 1, 250);
        if (poll_result < 0) {
            if (errno == EINTR)
                continue;
            perror("playback control: poll");
            close(input.fd);
            return 3;
        }
        if (poll_result == 0 || !(input.revents & POLLIN))
            continue;
        while (read(input.fd, &event, sizeof(event)) == sizeof(event)) {
            int delta;
            if (event.type != EV_KEY)
                continue;
            if (log_path != NULL) {
                log_file = fopen(log_path, "a");
                if (log_file != NULL) {
                    fprintf(log_file, "key code=%u value=%d\n", event.code, event.value);
                    fclose(log_file);
                }
            }
            if (event.value != 1)
                continue;
            if (event.code == KEY_ENTER) {
                control = fopen(control_path, "w");
                if (control != NULL) {
                    fputs("aspect\n", control);
                    fclose(control);
                }
                continue;
            }
            delta = seek_delta(event.code);
            if (delta == 0)
                continue;
            control = fopen(control_path, "w");
            if (control == NULL)
                continue;
            fprintf(control, "%d\n", delta);
            fclose(control);
        }
    }
    close(input.fd);
    return 0;
}
