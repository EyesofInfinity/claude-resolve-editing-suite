// Minimal WAV reading (PCM 16/24/32, float 32/64, extensible) and float32 writing for the test harness.
#pragma once

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

struct Wav
{
	int sr = 48000, ch = 1;
	std::vector<std::vector<float>> data;   // [channel][sample]
	size_t frames () const { return data.empty () ? 0 : data[0].size (); }
};

inline bool readWav (const std::string& path, Wav& w, std::string& err)
{
	FILE* f = std::fopen (path.c_str (), "rb");
	if (!f)
	{
		err = "cannot open " + path;
		return false;
	}
	std::vector<uint8_t> buf;
	{
		std::fseek (f, 0, SEEK_END);
		long n = std::ftell (f);
		std::fseek (f, 0, SEEK_SET);
		buf.resize ((size_t)n);
		if (n > 0 && std::fread (buf.data (), 1, (size_t)n, f) != (size_t)n)
		{
			std::fclose (f);
			err = "short read";
			return false;
		}
		std::fclose (f);
	}
	if (buf.size () < 12 || std::memcmp (buf.data (), "RIFF", 4) || std::memcmp (buf.data () + 8, "WAVE", 4))
	{
		err = "not a RIFF WAVE file";
		return false;
	}
	size_t p = 12;
	int fmtTag = 0, bits = 0, blockAlign = 0;
	const uint8_t* pcm = nullptr;
	size_t pcmBytes = 0;
	auto u16 = [&] (size_t o) { return (uint32_t)buf[o] | ((uint32_t)buf[o + 1] << 8); };
	auto u32 = [&] (size_t o) { return u16 (o) | (u16 (o + 2) << 16); };
	while (p + 8 <= buf.size ())
	{
		uint32_t sz = u32 (p + 4);
		if (!std::memcmp (buf.data () + p, "fmt ", 4))
		{
			fmtTag = (int)u16 (p + 8);
			w.ch = (int)u16 (p + 10);
			w.sr = (int)u32 (p + 12);
			blockAlign = (int)u16 (p + 20);
			bits = (int)u16 (p + 22);
			if (fmtTag == 0xFFFE && sz >= 40)
				fmtTag = (int)u16 (p + 32);
		}
		else if (!std::memcmp (buf.data () + p, "data", 4))
		{
			pcm = buf.data () + p + 8;
			pcmBytes = std::min<size_t> (sz, buf.size () - p - 8);
		}
		p += 8 + sz + (sz & 1);
	}
	if (!pcm || w.ch < 1 || blockAlign < 1)
	{
		err = "no fmt or data chunk";
		return false;
	}
	size_t n = pcmBytes / (size_t)blockAlign;
	w.data.assign (w.ch, std::vector<float> (n));
	int bps = bits / 8;
	for (size_t i = 0; i < n; ++i)
		for (int c = 0; c < w.ch; ++c)
		{
			const uint8_t* s = pcm + i * blockAlign + c * bps;
			float v = 0.0f;
			if (fmtTag == 3 && bits == 32)
				std::memcpy (&v, s, 4);
			else if (fmtTag == 3 && bits == 64)
			{
				double d;
				std::memcpy (&d, s, 8);
				v = (float)d;
			}
			else if (bits == 16)
				v = (int16_t)(s[0] | (s[1] << 8)) / 32768.0f;
			else if (bits == 24)
			{
				int32_t x = (s[0] << 8) | (s[1] << 16) | (s[2] << 24);
				v = (float)((x >> 8) / 8388608.0);
			}
			else if (bits == 32)
			{
				int32_t x;
				std::memcpy (&x, s, 4);
				v = (float)(x / 2147483648.0);
			}
			w.data[c][i] = v;
		}
	return true;
}

inline bool writeWav (const std::string& path, const Wav& w)
{
	FILE* f = std::fopen (path.c_str (), "wb");
	if (!f)
		return false;
	uint32_t n = (uint32_t)w.frames ();
	uint32_t dataBytes = n * (uint32_t)w.ch * 4;
	auto put32 = [&] (uint32_t v) { std::fwrite (&v, 4, 1, f); };
	auto put16 = [&] (uint16_t v) { std::fwrite (&v, 2, 1, f); };
	std::fwrite ("RIFF", 1, 4, f);
	put32 (36 + dataBytes);
	std::fwrite ("WAVEfmt ", 1, 8, f);
	put32 (16);
	put16 (3);
	put16 ((uint16_t)w.ch);
	put32 ((uint32_t)w.sr);
	put32 ((uint32_t)w.sr * w.ch * 4);
	put16 ((uint16_t)(w.ch * 4));
	put16 (32);
	std::fwrite ("data", 1, 4, f);
	put32 (dataBytes);
	std::vector<float> frame (w.ch);
	for (uint32_t i = 0; i < n; ++i)
	{
		for (int c = 0; c < w.ch; ++c)
			frame[c] = w.data[c][i];
		std::fwrite (frame.data (), 4, w.ch, f);
	}
	std::fclose (f);
	return true;
}
