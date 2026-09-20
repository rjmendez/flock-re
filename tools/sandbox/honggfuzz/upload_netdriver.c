/*
 * Minimal honggfuzz netdriver-compatible scaffold for the upload protocol surface.
 *
 * This is intentionally small and deterministic: it accepts fuzzed TCP traffic,
 * parses the same opcode/length shapes as the sandbox mock, and keeps the parser
 * stateful enough for coverage-guided mutation. It is not a faithful copy of the
 * production backend, only a local fuzz target.
 */
#if defined(__has_include)
#  if __has_include("libhfnetdriver/netdriver.h")
#    include "libhfnetdriver/netdriver.h"
#  endif
#endif

#include <arpa/inet.h>
#include <errno.h>
#include <netinet/in.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <unistd.h>

#ifndef __has_include
#  define __has_include(x) 0
#endif

#define UPLOAD_OK      1
#define UPLOAD_HELLO   2
#define UPLOAD_PROTO   3
#define UPLOAD_SESSION 4
#define UPLOAD_START   5
#define UPLOAD_FILE    6
#define UPLOAD_HASH    7
#define UPLOAD_SAVE    8
#define UPLOAD_DONE    9
#define UPLOAD_META    12
#define UPLOAD_DEFAULT_PORT 8443
#define UPLOAD_MAX_FRAME     (1u << 20)

typedef struct {
    uint32_t checksum;
    uint32_t seen_hello;
    uint32_t seen_metadata;
    uint32_t seen_file;
    uint32_t seen_hash;
    uint32_t state_bits;
} upload_state_t;

static uint16_t parse_port(const char* text, uint16_t fallback) {
    if (!text || !*text) {
        return fallback;
    }
    char* end = NULL;
    errno = 0;
    long value = strtol(text, &end, 10);
    if (errno != 0 || end == text || *end != '\0' || value < 1 || value > 65535) {
        return fallback;
    }
    return (uint16_t)value;
}

static uint16_t netdriver_port_from_args(int argc, char** argv) {
    const char* env = getenv("HFND_TCP_PORT");
    if (env && *env) {
        return parse_port(env, UPLOAD_DEFAULT_PORT);
    }
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--port") == 0 && i + 1 < argc) {
            return parse_port(argv[i + 1], UPLOAD_DEFAULT_PORT);
        }
        if (strncmp(argv[i], "--port=", 7) == 0) {
            return parse_port(argv[i] + 7, UPLOAD_DEFAULT_PORT);
        }
    }
    return UPLOAD_DEFAULT_PORT;
}

static int socket_set_reuseaddr(int fd) {
    int value = 1;
    return setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &value, (socklen_t)sizeof(value));
}

static ssize_t read_exact(int fd, void* buf, size_t size) {
    uint8_t* out = (uint8_t*)buf;
    size_t have = 0;
    while (have < size) {
        ssize_t got = recv(fd, out + have, size - have, 0);
        if (got == 0) {
            return -1;
        }
        if (got < 0) {
            if (errno == EINTR) {
                continue;
            }
            return -1;
        }
        have += (size_t)got;
    }
    return (ssize_t)have;
}

static bool read_i64_be(int fd, int64_t* out) {
    uint8_t buf[8];
    if (read_exact(fd, buf, sizeof(buf)) != (ssize_t)sizeof(buf)) {
        return false;
    }
    uint64_t value = 0;
    for (size_t i = 0; i < sizeof(buf); i++) {
        value = (value << 8) | (uint64_t)buf[i];
    }
    *out = (int64_t)value;
    return true;
}

static void mix_bytes(upload_state_t* state, const uint8_t* data, size_t len) {
    for (size_t i = 0; i < len; i++) {
        state->checksum = (state->checksum << 5) ^ (state->checksum >> 2) ^ data[i];
    }
}

static bool consume_frame(int fd, upload_state_t* state) {
    uint8_t op = 0;
    ssize_t got = recv(fd, &op, 1, 0);
    if (got == 0) {
        return false;
    }
    if (got < 0) {
        return false;
    }

    state->state_bits ^= (uint32_t)op;
    switch (op) {
    case UPLOAD_HELLO: {
        uint8_t proto = 0;
        int64_t len = 0;
        if (read_exact(fd, &proto, sizeof(proto)) != (ssize_t)sizeof(proto) ||
            !read_i64_be(fd, &len)) {
            return false;
        }
        if (len < 0) {
            len = 0;
        }
        if ((uint64_t)len > UPLOAD_MAX_FRAME) {
            return false;
        }
        uint8_t* buf = (uint8_t*)malloc((size_t)len ? (size_t)len : 1u);
        if (!buf) {
            return false;
        }
        if (len > 0 && read_exact(fd, buf, (size_t)len) != (ssize_t)len) {
            free(buf);
            return false;
        }
        state->seen_hello++;
        state->state_bits ^= (uint32_t)proto;
        mix_bytes(state, buf, (size_t)len);
        free(buf);
        break;
    }
    case UPLOAD_META:
    case UPLOAD_FILE: {
        int64_t len = 0;
        if (!read_i64_be(fd, &len)) {
            return false;
        }
        if (len < 0) {
            len = 0;
        }
        if ((uint64_t)len > UPLOAD_MAX_FRAME) {
            return false;
        }
        uint8_t scratch[4096];
        uint64_t remaining = (uint64_t)len;
        while (remaining > 0) {
            size_t chunk = remaining < sizeof(scratch) ? (size_t)remaining : sizeof(scratch);
            if (read_exact(fd, scratch, chunk) != (ssize_t)chunk) {
                return false;
            }
            mix_bytes(state, scratch, chunk);
            remaining -= (uint64_t)chunk;
        }
        if (op == UPLOAD_META) {
            state->seen_metadata++;
            state->state_bits ^= 0x1200u;
        } else {
            state->seen_file++;
            state->state_bits ^= 0x3400u;
        }
        break;
    }
    case UPLOAD_HASH: {
        uint8_t hash[32];
        if (read_exact(fd, hash, sizeof(hash)) != (ssize_t)sizeof(hash)) {
            return false;
        }
        state->seen_hash++;
        uint8_t expected[32];
        for (size_t i = 0; i < sizeof(expected); i++) {
            expected[i] = (uint8_t)(state->checksum >> ((i & 3u) * 8u));
        }
        if (memcmp(hash, expected, sizeof(hash)) == 0) {
            state->state_bits ^= 0x80000000u;
        } else {
            state->state_bits ^= 0x40000000u;
        }
        break;
    }
    case UPLOAD_SESSION:
    case UPLOAD_START:
    case UPLOAD_SAVE:
    case UPLOAD_DONE:
    case UPLOAD_PROTO:
    case UPLOAD_OK:
        state->state_bits ^= (uint32_t)(op << 8);
        break;
    default:
        state->state_bits ^= 0xDEADBEEFu ^ (uint32_t)op;
        break;
    }

    return true;
}

static int handle_connection(int fd) {
    upload_state_t state = {0};
    while (consume_frame(fd, &state)) {
    }
    return 0;
}

static int run_server(uint16_t port) {
    int fd = socket(AF_INET, SOCK_STREAM, 0);
    if (fd < 0) {
        perror("socket");
        return 1;
    }
    if (socket_set_reuseaddr(fd) < 0) {
        perror("setsockopt");
        close(fd);
        return 1;
    }

    struct sockaddr_in addr;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_port = htons(port);
    addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);

    if (bind(fd, (struct sockaddr*)&addr, sizeof(addr)) < 0) {
        perror("bind");
        close(fd);
        return 1;
    }
    if (listen(fd, 16) < 0) {
        perror("listen");
        close(fd);
        return 1;
    }

    for (;;) {
        int cfd = accept(fd, NULL, NULL);
        if (cfd < 0) {
            if (errno == EINTR) {
                continue;
            }
            perror("accept");
            break;
        }
        handle_connection(cfd);
        close(cfd);
    }

    close(fd);
    return 0;
}

int HonggfuzzNetDriver_main(int argc, char** argv) {
    (void)argc;
    return run_server(netdriver_port_from_args(argc, argv));
}

int main(int argc, char** argv) {
    return HonggfuzzNetDriver_main(argc, argv);
}
