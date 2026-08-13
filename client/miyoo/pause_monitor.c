#include <errno.h>
#include <fcntl.h>
#include <linux/input.h>
#include <poll.h>
#include <signal.h>
#include <stdio.h>
#include <sys/time.h>
#include <unistd.h>

static volatile sig_atomic_t running = 1;

static void stop_monitor(int signal_number)
{
    (void)signal_number;
    running = 0;
}

static long long now_milliseconds(void)
{
    struct timeval now;
    gettimeofday(&now, NULL);
    return (long long)now.tv_sec * 1000 + now.tv_usec / 1000;
}

int main(int argc, char **argv)
{
    struct input_event event;
    struct pollfd input;
    long long pause_started = 0;
    long long paused_milliseconds = 0;
    ssize_t bytes_read;
    int paused = 0;
    FILE *result;

    if (argc != 2) {
        fprintf(stderr, "usage: %s RESULT_FILE\n", argv[0]);
        return 1;
    }

    signal(SIGINT, stop_monitor);
    signal(SIGTERM, stop_monitor);

    input.fd = open("/dev/input/event0", O_RDONLY | O_NONBLOCK);
    if (input.fd < 0) {
        perror("pause monitor: /dev/input/event0");
        return 2;
    }
    input.events = POLLIN;

    while (running) {
        int poll_result = poll(&input, 1, 250);
        if (poll_result < 0) {
            if (errno == EINTR)
                continue;
            perror("pause monitor: poll");
            close(input.fd);
            return 3;
        }
        if (poll_result == 0 || !(input.revents & POLLIN))
            continue;

        while ((bytes_read = read(input.fd, &event, sizeof(event))) == sizeof(event)) {
            if (event.type != EV_KEY || event.value != 1)
                continue;
            if (event.code == KEY_SPACE) {
                long long event_time = now_milliseconds();
                if (paused)
                    paused_milliseconds += event_time - pause_started;
                else
                    pause_started = event_time;
                paused = !paused;
            } else if (event.code == KEY_ESC) {
                running = 0;
                break;
            }
        }
        if (bytes_read < 0 && errno != EAGAIN && errno != EWOULDBLOCK) {
            perror("pause monitor: read");
            close(input.fd);
            return 4;
        }
    }

    if (paused)
        paused_milliseconds += now_milliseconds() - pause_started;
    close(input.fd);

    result = fopen(argv[1], "w");
    if (result == NULL) {
        perror("pause monitor: result");
        return 5;
    }
    fprintf(result, "%lld\n", paused_milliseconds / 1000);
    if (fclose(result) != 0) {
        perror("pause monitor: close result");
        return 6;
    }
    return 0;
}
