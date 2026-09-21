#include <dlfcn.h>
#include <errno.h>
#include <inttypes.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
  uint8_t version;
  uint8_t call_mode;
  uint8_t pixfmt;
  uint8_t reserved;
  uint32_t width;
  uint32_t height;
  uint32_t payload_len;
  const uint8_t *payload;
} fuzz_case_t;

static uint32_t read_u32_le(const uint8_t *p) {
  return (uint32_t)p[0] |
         ((uint32_t)p[1] << 8) |
         ((uint32_t)p[2] << 16) |
         ((uint32_t)p[3] << 24);
}

static bool parse_case(const uint8_t *data, size_t size, fuzz_case_t *out) {
  if (size < 20) {
    return false;
  }

  if (memcmp(data, "FIMU", 4) != 0) {
    return false;
  }

  out->version = data[4];
  out->call_mode = data[5];
  out->pixfmt = data[6];
  out->reserved = data[7];
  out->width = read_u32_le(data + 8);
  out->height = read_u32_le(data + 12);
  out->payload_len = read_u32_le(data + 16);

  if (out->version != 1) {
    return false;
  }

  if (out->payload_len > size - 20) {
    return false;
  }

  out->payload = data + 20;
  return true;
}

static void *load_target_library(void) {
  const char *path = getenv("TARGET_SO_PATH");
  if (path == NULL || path[0] == '\0') {
    fprintf(stderr, "TARGET_SO_PATH is required\n");
    return NULL;
  }

  void *handle = dlopen(path, RTLD_NOW | RTLD_LOCAL);
  if (handle == NULL) {
    fprintf(stderr, "dlopen(%s) failed: %s\n", path, dlerror());
  }
  return handle;
}

static int invoke_target(const fuzz_case_t *fc) {
  void *handle = load_target_library();
  if (handle == NULL) {
    return -1;
  }

  const char *symbol = getenv("TARGET_SYMBOL");
  if (symbol == NULL || symbol[0] == '\0' || strcmp(symbol, "replace_me") == 0) {
    fprintf(stderr, "TARGET_SYMBOL is required\n");
    dlclose(handle);
    return -1;
  }

  void *entry = dlsym(handle, symbol);
  if (entry == NULL) {
    fprintf(stderr, "dlsym(%s) failed: %s\n", symbol, dlerror());
    dlclose(handle);
    return -1;
  }

  const char *mode = getenv("TARGET_CALL_MODE");
  if (mode == NULL || mode[0] == '\0') {
    mode = "image_frame";
  }

  if (strcmp(mode, "raw_buffer") == 0) {
    typedef void (*raw_buffer_fn)(const uint8_t *, size_t);
    ((raw_buffer_fn)entry)(fc->payload, fc->payload_len);
  } else if (strcmp(mode, "image_frame") == 0) {
    typedef void (*image_frame_fn)(const uint8_t *, size_t, uint32_t, uint32_t, uint32_t);
    ((image_frame_fn)entry)(fc->payload, fc->payload_len, fc->width, fc->height, fc->pixfmt);
  } else {
    fprintf(stderr, "unsupported TARGET_CALL_MODE: %s\n", mode);
    dlclose(handle);
    return -1;
  }

  dlclose(handle);
  return 0;
}

int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
  fuzz_case_t fc;
  if (!parse_case(data, size, &fc)) {
    return 0;
  }

  (void)invoke_target(&fc);
  return 0;
}

static uint8_t *slurp_file(const char *path, size_t *out_size) {
  FILE *fp = fopen(path, "rb");
  if (fp == NULL) {
    fprintf(stderr, "fopen(%s) failed: %s\n", path, strerror(errno));
    return NULL;
  }

  if (fseek(fp, 0, SEEK_END) != 0) {
    fprintf(stderr, "fseek(%s) failed: %s\n", path, strerror(errno));
    fclose(fp);
    return NULL;
  }

  long len = ftell(fp);
  if (len < 0) {
    fprintf(stderr, "ftell(%s) failed: %s\n", path, strerror(errno));
    fclose(fp);
    return NULL;
  }

  if (fseek(fp, 0, SEEK_SET) != 0) {
    fprintf(stderr, "rewind(%s) failed: %s\n", path, strerror(errno));
    fclose(fp);
    return NULL;
  }

  uint8_t *buf = (uint8_t *)malloc((size_t)len);
  if (buf == NULL) {
    fprintf(stderr, "malloc(%ld) failed\n", len);
    fclose(fp);
    return NULL;
  }

  size_t got = fread(buf, 1, (size_t)len, fp);
  fclose(fp);
  if (got != (size_t)len) {
    fprintf(stderr, "fread(%s) short read\n", path);
    free(buf);
    return NULL;
  }

  *out_size = (size_t)len;
  return buf;
}

int main(int argc, char **argv) {
  if (argc != 2) {
    fprintf(stderr, "usage: %s <fimu-testcase>\n", argv[0]);
    return 2;
  }

  size_t size = 0;
  uint8_t *data = slurp_file(argv[1], &size);
  if (data == NULL) {
    return 1;
  }

  (void)LLVMFuzzerTestOneInput(data, size);
  free(data);
  return 0;
}
