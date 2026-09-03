#include <arpa/inet.h>
#include <errno.h>
#include <netinet/in.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/select.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>

#define DEFAULT_PORT 8754
#define MAX_PACKET 1024
#define MAX_RESULTS 16

/* Kept as the deployed discovery wire identifier for interoperability. */
static const char request[] = "POCKETSTREMIO_DISCOVER_V1\n";
static const char prefix[] = "POCKETSTREMIO_PSS_V1\t";

static int valid_url(const char *value) {
    const unsigned char *p = (const unsigned char *)value;
    if (strncmp(value, "http://", 7) != 0 && strncmp(value, "https://", 8) != 0) {
        return 0;
    }
    for (; *p; p++) {
        if (*p <= 32 || *p == 127 || *p == '\\' || *p == '\t') {
            return 0;
        }
    }
    return 1;
}

struct result {
    char instance_id[65];
    char name[49];
    char network[49];
    char url[MAX_PACKET];
};

static int safe_field(const char *value, size_t maximum) {
    const unsigned char *p = (const unsigned char *)value;
    size_t length = strlen(value);
    if (length == 0 || length > maximum) {
        return 0;
    }
    for (; *p; p++) {
        if (*p < 32 || *p >= 127 || *p == '\t') {
            return 0;
        }
    }
    return 1;
}

static void copy_field(char *destination, size_t destination_size,
                       const char *source) {
    size_t length = strlen(source);
    if (length >= destination_size) {
        length = destination_size - 1;
    }
    memcpy(destination, source, length);
    destination[length] = '\0';
}

static int already_seen(struct result results[MAX_RESULTS], int count,
                        const char *instance_id) {
    int i;
    for (i = 0; i < count; i++) {
        if (strcmp(results[i].instance_id, instance_id) == 0) {
            return 1;
        }
    }
    return 0;
}

int main(int argc, char **argv) {
    const char *target = getenv("POCKETSTREMIO_DISCOVERY_TARGET");
    int port = DEFAULT_PORT;
    int sock;
    int broadcast = 1;
    struct sockaddr_in destination;
    struct timeval deadline;
    struct result results[MAX_RESULTS];
    int result_count = 0;

    if (argc > 2) {
        fprintf(stderr, "usage: %s [port]\n", argv[0]);
        return 2;
    }
    if (argc == 2) {
        char *end = NULL;
        long parsed = strtol(argv[1], &end, 10);
        if (!end || *end || parsed < 1 || parsed > 65535) {
            fprintf(stderr, "invalid discovery port\n");
            return 2;
        }
        port = (int)parsed;
    }
    if (!target || !*target) {
        target = "255.255.255.255";
    }

    sock = socket(AF_INET, SOCK_DGRAM, 0);
    if (sock < 0) {
        perror("socket");
        return 1;
    }
    if (setsockopt(sock, SOL_SOCKET, SO_BROADCAST, &broadcast, sizeof(broadcast)) < 0) {
        perror("setsockopt");
        close(sock);
        return 1;
    }

    memset(&destination, 0, sizeof(destination));
    destination.sin_family = AF_INET;
    destination.sin_port = htons((unsigned short)port);
    if (inet_pton(AF_INET, target, &destination.sin_addr) != 1) {
        fprintf(stderr, "invalid discovery target\n");
        close(sock);
        return 2;
    }
    if (sendto(sock, request, sizeof(request) - 1, 0,
               (struct sockaddr *)&destination, sizeof(destination)) < 0) {
        perror("sendto");
        close(sock);
        return 1;
    }

    if (gettimeofday(&deadline, NULL) < 0) {
        perror("gettimeofday");
        close(sock);
        return 1;
    }
    deadline.tv_sec += 3;

    while (result_count < MAX_RESULTS) {
        fd_set readfds;
        struct timeval now;
        struct timeval timeout;
        char packet[MAX_PACKET];
        ssize_t size;
        char *instance_id;
        char *name;
        char *network;
        char *url;
        char *tab;

        if (gettimeofday(&now, NULL) < 0) {
            break;
        }
        timeout.tv_sec = deadline.tv_sec - now.tv_sec;
        timeout.tv_usec = deadline.tv_usec - now.tv_usec;
        if (timeout.tv_usec < 0) {
            timeout.tv_sec--;
            timeout.tv_usec += 1000000;
        }
        if (timeout.tv_sec < 0 || (timeout.tv_sec == 0 && timeout.tv_usec <= 0)) {
            break;
        }

        FD_ZERO(&readfds);
        FD_SET(sock, &readfds);
        if (select(sock + 1, &readfds, NULL, NULL, &timeout) <= 0) {
            break;
        }
        size = recvfrom(sock, packet, sizeof(packet) - 1, 0, NULL, NULL);
        if (size <= 0) {
            if (errno == EINTR) {
                continue;
            }
            break;
        }
        packet[size] = '\0';
        if (strncmp(packet, prefix, sizeof(prefix) - 1) != 0) {
            continue;
        }
        instance_id = packet + sizeof(prefix) - 1;
        tab = strchr(instance_id, '\t');
        if (!tab) {
            continue;
        }
        *tab = '\0';
        name = tab + 1;
        tab = strchr(name, '\t');
        if (!tab) {
            continue;
        }
        *tab = '\0';
        network = tab + 1;
        tab = strchr(network, '\t');
        if (!tab) {
            continue;
        }
        *tab = '\0';
        url = tab + 1;
        tab = strchr(url, '\t');
        if (!tab) {
            continue;
        }
        *tab = '\0';
        if (!safe_field(instance_id, 64) || !safe_field(name, 48) ||
            !safe_field(network, 48) ||
            !valid_url(url) || already_seen(results, result_count, instance_id)) {
            continue;
        }
        copy_field(results[result_count].instance_id,
                   sizeof(results[result_count].instance_id), instance_id);
        copy_field(results[result_count].name,
                   sizeof(results[result_count].name), name);
        copy_field(results[result_count].network,
                   sizeof(results[result_count].network), network);
        copy_field(results[result_count].url,
                   sizeof(results[result_count].url), url);
        result_count++;
    }

    close(sock);
    {
        int i;
        for (i = 0; i < result_count; i++) {
            printf("%s\t%s\t%s\n", results[i].name, results[i].url,
                   results[i].network);
        }
    }
    return result_count > 0 ? 0 : 1;
}
