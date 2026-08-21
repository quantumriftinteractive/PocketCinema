#include <errno.h>
#include <fcntl.h>
#include <linux/input.h>
#include <poll.h>
#include <signal.h>
#include <stdio.h>
#include <string.h>
#include <sys/time.h>
#include <time.h>
#include <unistd.h>

static volatile sig_atomic_t running = 1;

static void stop_diagnostic(int signal_number)
{
    (void)signal_number;
    running = 0;
}

static void format_timestamp(const struct timeval *timestamp, char *buffer,
                             size_t buffer_size)
{
    struct tm local_time;
    time_t seconds = timestamp->tv_sec;

    localtime_r(&seconds, &local_time);
    strftime(buffer, buffer_size, "%Y-%m-%dT%H:%M:%S", &local_time);
}

int main(int argc, char **argv)
{
    const char *log_path;
    int timeout_seconds = 90;
    int input_fd;
    int poll_result;
    FILE *log_file;
    struct pollfd input;
    struct input_event event;

    if (argc < 2 || argc > 3) {
        fprintf(stderr, "usage: %s LOG_FILE [TIMEOUT_SECONDS]\n", argv[0]);
        return 1;
    }
    log_path = argv[1];
    if (argc == 3 && sscanf(argv[2], "%d", &timeout_seconds) != 1) {
        fprintf(stderr, "invalid timeout: %s\n", argv[2]);
        return 1;
    }
    if (timeout_seconds < 1 || timeout_seconds > 3600) {
        fprintf(stderr, "timeout must be between 1 and 3600 seconds\n");
        return 1;
    }

    signal(SIGINT, stop_diagnostic);
    signal(SIGTERM, stop_diagnostic);

    log_file = fopen(log_path, "a");
    if (log_file == NULL) {
        perror("button diagnostic: log");
        return 2;
    }
    setvbuf(log_file, NULL, _IOLBF, 0);

    input_fd = open("/dev/input/event0", O_RDONLY | O_NONBLOCK);
    if (input_fd < 0) {
        perror("button diagnostic: /dev/input/event0");
        fclose(log_file);
        return 3;
    }
    input.fd = input_fd;
    input.events = POLLIN;

    fprintf(log_file, "BEGIN device=/dev/input/event0 timeout_seconds=%d\n",
            timeout_seconds);
    while (running) {
        poll_result = poll(&input, 1, 250);
        if (poll_result < 0) {
            if (errno == EINTR)
                continue;
            perror("button diagnostic: poll");
            break;
        }
        if (poll_result == 0) {
            static int elapsed_quarters;
            elapsed_quarters++;
            if (elapsed_quarters >= timeout_seconds * 4)
                break;
            continue;
        }
        if (!(input.revents & POLLIN))
            break;

        errno = 0;
        while (read(input_fd, &event, sizeof(event)) == sizeof(event)) {
            char timestamp[32];

            if (event.type != EV_KEY)
                continue;
            format_timestamp(&event.time, timestamp, sizeof(timestamp));
            fprintf(log_file, "%s.%06ld code=%u value=%d\n", timestamp,
                    (long)event.time.tv_usec, event.code, event.value);
            /* OnionOS Menu is reported as KEY_ESC on this device. */
            if ((event.code == KEY_ESC || event.code == KEY_MENU) &&
                event.value == 0)
                running = 0;
        }
        if (errno != EAGAIN && errno != EWOULDBLOCK && errno != 0) {
            perror("button diagnostic: read");
            break;
        }
        errno = 0;
    }

    fprintf(log_file, "END\n");
    close(input_fd);
    fclose(log_file);
    return 0;
}
