#pragma once
#include <cstddef>
#include <cstdint>
extern "C" {
void p19_batch_open(std::uint64_t, std::int64_t);
void p19_batch_close();
void p19_set_scene_identity(const char *);
void p19_record_calibration(const char *, const void *, std::size_t);
void p19_record_rgb(const char *, std::int64_t, const void *, std::size_t,
  std::uint32_t, std::uint32_t, std::uint32_t, const char *);
void p19_record_depth(const char *, std::int64_t, const void *, std::size_t,
  std::uint32_t, std::uint32_t, std::uint32_t, const char *);
void p19_record_truth(const char *, std::int64_t, const void *, std::size_t,
  std::uint32_t, std::uint32_t, std::uint32_t, const char *);
}
