// Develop Lo-fi: the lo-fi and speaker effects of lofi.py and speakers.py as one real-time engine with a mode list.
// Each mode is its Python chain with its own band limits, resonances, breakup, crackle and noise. Every mode is
// padded to the slowest mode's latency, so the reported latency never changes with the mode.
#pragma once

#include "lofi_parts.h"
#include "noise_follow.h"
#include "output_stage.h"
#include "params.h"

namespace dev {

// ------------------------------------------------------------------------------------------------- vinyl

struct VinylChain
{
	struct Cfg
	{
		double crackle = 0.4, dust = 0.3, rumble = 0.3, wear = 0.4, warp = 0.12, hissDb = -66.0, levelDb = -30.0;
	} cfg;
	double sr = 48000, rot = 100.0 / 3.0 / 60.0;
	SosChain sideHP, tone, surfLP, crk, body, snap, rumLP;
	Ring ring;
	int Dl = 0;
	double ph1 = 0, ph2 = 0, ph1_0 = 0, ph2_0 = 0;
	Rng rc, rd, rr;
	Hiss hiss;
	double rumNorm = 1, pan = 0.5, noise = 1.0;
	uint64_t seed = 0;
	const NoiseFollower* nf = nullptr;   // the engine's noise follower (null: the noise is constant)

	static int latencyFor (double sr, double warp)
	{
		if (warp <= 0)
			return 0;
		double rot = 100.0 / 3.0 / 60.0;
		double disp = sr * warp / 100.0 * (0.85 / (2.0 * kPi * rot) + 0.15 / (4.0 * kPi * rot));
		return (int)std::ceil (disp * 1.2) + 16;
	}
	void prepare (double rate, const Cfg& c, uint64_t s)
	{
		sr = rate;
		cfg = c;
		seed = s;
		sideHP = butterHP (2, 150.0, sr);
		double top = 18000.0 - 9000.0 * cfg.wear;
		tone = butterHP (2, 25.0 + 15.0 * cfg.wear, sr);
		tone.append (butterLP (2, top, sr));
		tone.add (rbj (Rbj::peak, 4500.0, sr, 0.8, -1.5 * cfg.wear));
		surfLP = butterLP (1, top, sr);
		crk.clear ();
		crk.add (rbj (Rbj::bandpass, 2800.0, sr, 0.9));
		crk.add (rbj (Rbj::highpass, 900.0, sr, 0.7));
		body.clear ();
		body.add (rbj (Rbj::bandpass, 180.0, sr, 1.2));
		snap.clear ();
		snap.add (rbj (Rbj::bandpass, 1800.0, sr, 0.8));
		rumLP = butterLP (2, 30.0, sr);
		rumNorm = 1.0 / std::sqrt (powerGain (rumLP, sr, 1.0));
		hiss.prepare (sr, nullptr, seed);
		Dl = latencyFor (sr, cfg.warp);
		ring.prepare (2 * Dl + 64);
		reset ();
	}
	int latency () const { return Dl; }
	void reset ()
	{
		sideHP.reset ();
		tone.reset ();
		surfLP.reset ();
		crk.reset ();
		body.reset ();
		snap.reset ();
		rumLP.reset ();
		hiss.reset ();
		ring.reset ();
		Rng r0;
		r0.seed (seed, 304);
		ph1 = r0.uniform () * 6.283;
		ph2 = r0.uniform () * 6.283;
		rc.seed (seed, 303);
		rd.seed (seed, 313);
		rr.seed (seed, 305);
		pan = rd.uniform ();
	}
	inline double pareto (Rng& r, double alpha)
	{
		double u = std::max (r.uniform (), 1e-9);
		return std::pow (u, -1.0 / alpha) * (r.uniform () < 0.5 ? -1.0 : 1.0);
	}
	inline void tick (double* y)
	{
		double mid = 0.5 * (y[0] + y[1]), side = 0.5 * (y[0] - y[1]);
		side = sideHP.tick (side, 0);
		double v[2] = {mid + side, mid - side};
		for (int c = 0; c < 2; ++c)
			v[c] = tone.tick (v[c], c);
		if (Dl > 0)
		{
			ring.push (v, 2);
			double w = cfg.warp / 100.0;
			double disp = -w * 0.85 * std::cos (ph1) * sr / (2.0 * kPi * rot) -
			              w * 0.15 * std::cos (ph2) * sr / (4.0 * kPi * rot);
			double rate = 1.0 + w * (0.85 * std::sin (ph1) + 0.15 * std::sin (ph2));
			ph1 += 2.0 * kPi * rot / sr;
			ph2 += 4.0 * kPi * rot / sr;
			if (ph1 > 2.0 * kPi)
				ph1 -= 2.0 * kPi;
			if (ph2 > 2.0 * kPi)
				ph2 -= 2.0 * kPi;
			for (int c = 0; c < 2; ++c)
				v[c] = ring.read (c, -Dl + disp, rate);
		}
		// the surface
		double s[2] = {0.0, 0.0};
		if (noise > 0)
		{
			if (cfg.crackle > 0)
			{
				double rate = 30.0 + 600.0 * cfg.crackle * cfg.crackle;
				double imp[2] = {0.0, 0.0};
				for (int c = 0; c < 2; ++c)
					if (rc.uniform () < rate * 0.7 / sr)
						imp[c] += 0.010 * pareto (rc, 2.2);
				if (rc.uniform () < rate * 0.3 / sr)
				{
					double sh = 0.010 * pareto (rc, 2.2);
					imp[0] += sh;
					imp[1] += sh;
				}
				for (int c = 0; c < 2; ++c)
					s[c] = crk.tick (imp[c], c);
			}
			if (cfg.dust > 0)
			{
				double rate = 0.3 + 3.0 * cfg.dust;
				double pop = rd.uniform () < rate / sr ? 0.05 * pareto (rd, 1.6) : 0.0;
				double p = body.tick (pop, 0) * 2.5 + snap.tick (pop, 0);
				s[0] += p * (0.6 + 0.4 * pan);
				s[1] += p * (1.0 - 0.4 * pan);
			}
			double lv = undb (cfg.levelDb + 30.0);
			s[0] *= lv;
			s[1] *= lv;
			if (cfg.rumble > 0)
			{
				double r = rumLP.tick (rr.gauss (), 0) * rumNorm * undb (-52.0) * cfg.rumble;
				s[0] += r;
				s[1] += -r * 0.8;
			}
			if (cfg.hissDb > -150)
			{
				double hl = undb (cfg.hissDb);
				s[0] += hiss.tick (0) * hl;
				s[1] += hiss.tick (1) * hl;
			}
			if (nf && nf->on)
			{
				// the surface follows the input, and no pop rises past the input's own recent peak
				double fg = nf->gain (), cp = nf->cap ();
				for (int c = 0; c < 2; ++c)
					s[c] = underCap (surfLP.tick (s[c], c) * noise * fg, cp);
			}
			else
				for (int c = 0; c < 2; ++c)
					s[c] = surfLP.tick (s[c], c) * noise;
		}
		y[0] = v[0] + s[0];
		y[1] = v[1] + s[1];
	}
};

// ---------------------------------------------------------------------------------------------- cassette

struct CassetteChain
{
	struct Cfg
	{
		double drive = 4.0, wow = 0.12, flutter = 0.10, hissDb = -54.0, dropout = 0.3, azimuthUs = 12.0,
		       quality = 0.5;
	} cfg;
	double sr = 48000, driveOffset = 0.0, noise = 1.0;
	Magnetiser mag;
	SosChain bump, hp35, lo2500;
	Fir fir;
	std::vector<double> taps;
	Dropouts drops;
	WowStage wow;
	Hiss hiss;
	int Dl = 0;
	const NoiseFollower* nf = nullptr;

	void prepare (double rate, const Cfg& c, int wowLat, uint64_t seed)
	{
		sr = rate;
		cfg = c;
		mag.prepare (sr, 2);
		mag.setTargets (cfg.drive, 0.45 - 0.2 * cfg.quality, 0.15);
		replayDesign (1.875, sr, 1.1, 0.55 - 0.3 * cfg.quality, 2.0, 2.0, bump, &taps);
		fir.prepare (taps);
		hp35 = butterHP (2, 35.0, sr);
		lo2500 = butterLP (1, 2500.0, sr);
		drops.prepare (sr, seed);
		drops.amount = cfg.dropout;
		Dl = wowLat;
		wow.prepare (sr, 2, Dl, seed);
		wow.gen.setTargets (cfg.wow, 0.7, cfg.flutter, 9.0);
		wow.chOffset[1] = -cfg.azimuthUs * 1e-6 * sr;
		hiss.prepare (sr, &taps, seed);
		reset ();
	}
	int latency () const { return mag.latency () + fir.delay () + Dl; }
	void setDriveOffset (double d)
	{
		driveOffset = d;
		mag.setTargets (cfg.drive + d, 0.45 - 0.2 * cfg.quality, 0.15);
	}
	void reset ()
	{
		mag.reset ();
		bump.reset ();
		fir.reset ();
		hp35.reset ();
		lo2500.reset ();
		drops.reset ();
		wow.reset ();
		hiss.reset ();
	}
	inline void tick (double* y)
	{
		double v[2];
		mag.tick (y, v);
		for (int c = 0; c < 2; ++c)
			v[c] = hp35.tick (fir.tick (bump.tick (v[c], c), c), c);
		if (cfg.dropout > 0)
		{
			double g = drops.tick ();
			double glo = std::pow (10.0, -0.25 * g / 20.0), ghi = std::pow (10.0, -g / 20.0);
			for (int c = 0; c < 2; ++c)
			{
				double lo = lo2500.tick (v[c], c);
				v[c] = lo * glo + (v[c] - lo) * ghi;
			}
		}
		wow.tick (v);
		if (cfg.hissDb > -150 && noise > 0)
		{
			double hl = undb (cfg.hissDb + 4.0 * (0.5 - cfg.quality)) * noise;
			if (nf)
				hl *= nf->gain ();
			v[0] += hiss.tick (0) * hl;
			v[1] += hiss.tick (1) * hl;
		}
		y[0] = v[0];
		y[1] = v[1];
	}
};

// ---------------------------------------------------------------------------------------------- speakers

struct SpeakerModel
{
	double lo, hi;
	int order;
	double peaks[2][3];
	int npeaks;
	double drive, breakup, noiseDb, nbLo, nbHi, offset, humDb, whineDb, boxMs;
	bool codec, wall;
};

// speakers.MODELS
inline SpeakerModel speakerModel (int i)
{
	switch (i)
	{
		case 0:   // radio
			return {180, 4500, 2, {{420, 1.4, 5}, {1800, 1.0, 2}}, 2, 6, 0.35, -52, 300, 5000, 0, -200, -200, 0,
			        false, false};
		case 1:   // telephone
			return {300, 3400, 4, {{1000, 0.9, 3}, {2600, 2.0, 3}}, 2, 3, 0.25, -60, 300, 3400, -1, -200, -200, 0,
			        true, false};
		case 2:   // tv
			return {150, 7000, 2, {{260, 1.5, 5}, {2600, 1.8, 4}}, 2, 4, 0.3, -200, 300, 5000, 0, -58, -62, 0,
			        false, false};
		case 3:   // intercom
			return {350, 3200, 3, {{1200, 2.0, 6}, {2400, 3.0, 3}}, 2, 10, 0.6, -50, 400, 4000, 0, -200, -200, 2.3,
			        false, false};
		default:  // wall
			return {60, 6000, 1, {{85, 1.0, 4}, {0, 1, 0}}, 1, 0, 0.0, -200, 300, 5000, -10, -200, -200, 0, false,
			        true};
	}
}

// speakers.speaker(): mono. Latency: the room convolution's block (wall), the codec (telephone) and the cone's
// 4x oversampling (or a plain delay of the same length when the cone is idle).
struct SpeakerChain
{
	SpeakerModel m {};
	double sr = 48000, driveOffset = 0.0, noise = 1.0, makeup = 1.0;
	SosChain band1, codecLP, nbp, coneHP, peaks, band2;
	Codec8k codec;
	Oversampler os;
	Delay coneDelay, boxDelay, wallDelay;
	PartConv room;
	Rng rng;
	double nNorm = 1;
	double humPh = 0, whinePh = 0;
	int box = 0;
	uint64_t seed = 0;
	const NoiseFollower* nf = nullptr;
	static constexpr int kRoomBlock = 256;

	void prepare (double rate, int model, uint64_t s)
	{
		sr = rate;
		seed = s;
		m = speakerModel (model);
		band1 = butterHP (m.order, m.lo, sr);
		band1.append (butterLP (m.order, m.hi, sr));
		if (m.codec)
		{
			codec.prepare (sr);
			codecLP = butterLP (6, 3500.0, sr);
		}
		nbp = butterBP (2, m.nbLo, m.nbHi, sr);
		nNorm = 1.0 / std::sqrt (powerGain (nbp, sr, 0.5));
		os.prepare (4);
		coneHP = butterHP (1, 10.0, sr);
		coneDelay.prepare (os.latency () + 2);
		coneDelay.setDelay (os.latency ());
		peaks.clear ();
		for (int i = 0; i < m.npeaks; ++i)
			peaks.add (rbj (Rbj::peak, m.peaks[i][0], sr, m.peaks[i][1], m.peaks[i][2]));
		if (m.wall)
		{
			peaks.add (rbj (Rbj::lowpass, 220.0, sr, 0.55));
			peaks.add (rbj (Rbj::peak, 2500.0, sr, 1.2, 9.0));
			peaks.add (rbj (Rbj::highshelf, 4000.0, sr, 0.7, -6.0));
			// speakers._room_tail: a short diffuse decay
			double decay = 0.35;
			int L = (int)(sr * decay * 1.2);
			std::vector<double> ir (L);
			Rng r;
			r.seed (seed, 401);
			SosChain lp = butterLP (1, 2500.0, sr);
			double e = 0;
			for (int i = 0; i < L; ++i)
			{
				double t = (double)i / sr;
				ir[i] = lp.tick (r.gauss () * std::exp (-6.9 * t / decay), 0);
			}
			ir[0] = 0.0;
			for (double v : ir)
				e += v * v;
			for (double& v : ir)
				v /= std::sqrt (e);
			room.prepare (ir, kRoomBlock);
			wallDelay.prepare (kRoomBlock + 2);
			wallDelay.setDelay (kRoomBlock);
		}
		box = m.boxMs > 0 ? (int)(sr * m.boxMs / 1000.0) : 0;
		if (box > 0)
		{
			boxDelay.prepare (box + 2);
			boxDelay.setDelay (box);
		}
		band2 = butterHP (2, m.lo, sr);
		band2.append (butterLP (2, m.hi, sr));
		reset ();
	}
	int latency () const
	{
		return (m.wall ? kRoomBlock : 0) + (m.codec ? codec.lat : 0) + os.latency ();
	}
	void reset ()
	{
		band1.reset ();
		codecLP.reset ();
		nbp.reset ();
		coneHP.reset ();
		peaks.reset ();
		band2.reset ();
		if (m.codec)
			codec.reset ();
		os.reset ();
		coneDelay.reset ();
		boxDelay.reset ();
		wallDelay.reset ();
		if (m.wall)
			room.reset ();
		rng.seed (seed, 402);
		humPh = whinePh = 0.0;
	}
	inline void tick (double* y)
	{
		double v = 0.5 * (y[0] + y[1]);
		if (m.wall)
		{
			double tail = room.tick (v);
			v = wallDelay.tick1 (v, 0);
			wallDelay.step ();
			v = v + 0.45 * tail;
		}
		v = band1.tick (v, 0);
		if (m.codec)
			v = codecLP.tick (codec.tick (v), 0);
		// the line's noise, the set's hum and its whine follow the input (fg is exactly 1 with the follower off)
		double fg = nf ? nf->gain () : 1.0;
		// the line's noise and the set's hum enter before the amplifier
		if (m.noiseDb > -150 && noise > 0)
			v += nbp.tick (rng.gauss (), 0) * nNorm * undb (m.noiseDb) * noise * fg;
		if (m.humDb > -150)
		{
			double hum = 0.0;
			const int hs[4] = {1, 2, 3, 5};
			for (int h : hs)
				hum += std::sin (humPh * h) / h;
			humPh += 2.0 * kPi * 60.0 / sr;
			if (humPh > 2.0 * kPi)
				humPh -= 2.0 * kPi;
			v += hum * undb (m.humDb) * noise * fg;
		}
		double d = m.drive + driveOffset;
		if (d <= 0 && m.breakup <= 0)
		{
			v = coneDelay.tick1 (v, 0);
			coneDelay.step ();
		}
		else
		{
			double k = undb (d), b = 0.35 * m.breakup;
			double tb = std::tanh (b), den = k * (1.0 - tb * tb);
			double u[4];
			os.up (v, 0, u);
			for (int q = 0; q < 4; ++q)
				u[q] = (std::tanh (k * u[q] + b) - tb) / den;
			v = coneHP.tick (os.down (u, 0), 0);
		}
		v = peaks.tick (v, 0);
		if (box > 0)
		{
			double old = boxDelay.tick1 (v, 0);
			boxDelay.step ();
			v = v + 0.5 * old;
		}
		v = band2.tick (v, 0) * makeup;
		if (m.whineDb > -150)
		{
			v += std::sin (whinePh) * undb (m.whineDb) * noise * fg;
			whinePh += 2.0 * kPi * 15734.0 / sr;
			if (whinePh > 2.0 * kPi)
				whinePh -= 2.0 * kPi;
		}
		y[0] = y[1] = v;
	}
};

// ---------------------------------------------------------------------------------------------- bitcrush

// lofi.bitcrush with filters "vintage": a gentle filter, sample and hold, quantise, a gentle filter.
struct BitcrushChain
{
	SosChain pre, post;
	Hold hold;
	double q = 512.0;
	void prepare (double sr, double rate, int bits)
	{
		double nyq = rate / 2.0;
		pre = butterLP (2, 0.9 * nyq, sr);
		post = butterLP (3, 1.1 * nyq, sr);
		hold.prepare (sr, rate);
		q = std::pow (2.0, bits - 1.0);
		reset ();
	}
	void reset ()
	{
		pre.reset ();
		post.reset ();
		hold.reset ();
	}
	inline void tick (double* y, int nch)
	{
		for (int c = 0; c < nch; ++c)
			y[c] = pre.tick (y[c], c);
		hold.tick (y, nch);
		for (int c = 0; c < nch; ++c)
			y[c] = post.tick (quantLinear (y[c], q), c);
	}
};

// ------------------------------------------------------------------------------------------- the terminal

// speakers.terminal: the cool tilt, 10 bits at 32 kHz through the vintage filters, a tight gate. The gate's
// threshold is relative to the loud passages: the Python reads them as the 95th percentile of the 10 ms RMS over the
// whole clip; here a running 95th-percentile tracker (in dB) follows them.
struct TerminalChain
{
	SosChain eq;
	BitcrushChain crush;
	double sr = 48000, makeup = 1.0;
	std::vector<double> sq;
	int W = 480, wpos = 0;
	double sum = 0.0, qDb = -30.0, up = 0, dn = 0, cur = 0.0, att = 0, rel = 0;
	int hold = 0, held = 0;
	double target = 0.0;
	int64_t t = 0;

	void prepare (double rate)
	{
		sr = rate;
		double c = 0.6;
		eq = butterHP (2, 110.0 + 60.0 * c, sr);
		eq.add (rbj (Rbj::lowshelf, 320.0, sr, 0.7, -4.0 * c));
		eq.add (rbj (Rbj::peak, 2200.0, sr, 1.0, 1.5 * c));
		eq.add (rbj (Rbj::highshelf, 6500.0, sr, 0.7, 3.0 * c));
		crush.prepare (sr, 32000.0, 10);
		W = std::max (1, (int)(sr * 0.01));
		sq.assign (W, 0.0);
		hold = (int)(sr * 25.0 / 1000.0);
		att = coefMs (1.0, sr);
		rel = coefMs (35.0, sr);
		up = 30.0 / sr * 0.95;   // dB per sample upward (the 95th-percentile balance: up = 19 x down)
		dn = 30.0 / sr * 0.05;
		reset ();
	}
	void reset ()
	{
		eq.reset ();
		crush.reset ();
		std::fill (sq.begin (), sq.end (), 0.0);
		wpos = 0;
		sum = 0.0;
		qDb = -30.0;
		cur = 0.0;
		held = 0;
		target = 0.0;
		t = 0;
	}
	inline void tick (double* y)
	{
		double x = 0.5 * (y[0] + y[1]);
		double v = eq.tick (x, 0);
		double vv[1] = {v};
		crush.tick (vv, 1);
		v = vv[0];
		// the gate's detector: RMS over the trailing 10 ms (summed directly every 1024 samples to stop drift)
		double s2 = x * x;
		sum += s2 - sq[wpos];
		sq[wpos] = s2;
		if (++wpos >= W)
			wpos = 0;
		if ((++t & 1023) == 0)
		{
			sum = 0.0;
			for (double e : sq)
				sum += e;
		}
		double env = std::sqrt (std::max (sum, 0.0) / W);
		double envDb = 20.0 * std::log10 (env + 1e-12);
		qDb += envDb > qDb ? up : -dn;
		qDb = std::max (-90.0, qDb);
		double ed = envDb - qDb;
		const double open = -32.0, close = -37.0;
		if (ed > open)
		{
			target = 1.0;
			held = hold;
		}
		else if (ed < close)
		{
			if (held > 0)
				--held;
			else
				target = 0.0;
		}
		cur += (target - cur) * (target > cur ? att : rel);
		double fl = undb (-80.0);
		double g = fl + (1.0 - fl) * cur;
		v *= g * makeup;
		y[0] = y[1] = v;
	}
};

// ------------------------------------------------------------------------------------------------ memory

// lofi.memory at amount 0.7: narrowed, warm, band limited with its tone drifting, through a worn cassette and a soft
// record surface, loudness held.
struct MemoryChain
{
	static constexpr double am = 0.7;
	SosChain pre;
	SvfLP svf;
	SlowNoise drift;
	CassetteChain cas;
	VinylChain vin;
	double sr = 48000, makeup = 1.0;

	void prepare (double rate, int wowLat, uint64_t seed)
	{
		sr = rate;
		pre = butterHP (2, 90.0 + 110.0 * am, sr);
		pre.add (rbj (Rbj::peak, 900.0, sr, 0.7, 2.0 * am));
		drift.prepare (sr, 0.15, seed);
		CassetteChain::Cfg cc;
		cc.drive = 3.0 + 3.0 * am;
		cc.wow = 0.08 + 0.25 * am;
		cc.flutter = 0.05 + 0.08 * am;
		cc.hissDb = -60.0 + 8.0 * am;
		cc.dropout = 0.4 * am;
		cc.quality = 0.6 - 0.4 * am;
		cas.prepare (sr, cc, wowLat, seed);
		VinylChain::Cfg vc;
		vc.crackle = 0.25 * am;
		vc.dust = 0.15 * am;
		vc.rumble = 0.0;
		vc.wear = 0.6;
		vc.warp = 0.0;
		vc.hissDb = -200.0;
		vin.prepare (sr, vc, seed);
		reset ();
	}
	int latency () const { return cas.latency () + vin.latency (); }
	void reset ()
	{
		pre.reset ();
		svf.reset ();
		drift.reset ();
		cas.reset ();
		vin.reset ();
	}
	inline void tick (double* y)
	{
		double mid = 0.5 * (y[0] + y[1]), side = 0.5 * (y[0] - y[1]) * (1.0 - 0.7 * am);
		double v[2] = {mid + side, mid - side};
		double dr = 0.5 + 0.5 * drift.next ();
		double fc = 7000.0 * (1.0 - 0.45 * am) * (0.75 + 0.25 * dr);
		for (int c = 0; c < 2; ++c)
			v[c] = svf.tick (pre.tick (v[c], c), fc, sr, c);
		cas.tick (v);
		vin.tick (v);
		y[0] = v[0] * makeup;
		y[1] = v[1] * makeup;
	}
};

// ------------------------------------------------------------------------------------------------ the engine

struct LofiEngine
{
	// the parameter ids are the order here; two follower parameters are appended so earlier ids and saved
	// states keep their meaning
	enum { kMode, kAmount, kTone, kDrive, kNoise, kOutput, kFollow, kFollowRelease, kNumParams };
	enum Mode { mVinyl, mCassette, mRadio, mTelephone, mTv, mIntercom, mWall, mBitcrush, mMemory, mTerminal, kModes };
	static const ParamDef* params ()
	{
		static const char* const modes[] = {"Vinyl", "Cassette", "Radio", "Telephone", "Old TV", "Intercom",
		                                    "Through a Wall", "Bitcrush", "Memory", "Terminal Voice"};
		static const char* const offOn[] = {"Off", "On"};
		static const ParamDef p[kNumParams] = {
		    {kMode, "Mode", "", 0, kModes - 1, 0, modes, kModes},
		    {kAmount, "Amount", "%", 0.0, 100.0, 100.0, nullptr, 0},
		    {kTone, "Tone", "dB", -12.0, 12.0, 0.0, nullptr, 0},
		    {kDrive, "Drive", "dB", -12.0, 12.0, 0.0, nullptr, 0},
		    {kNoise, "Noise", "dB", -60.0, 12.0, 0.0, nullptr, 0},
		    {kOutput, "Output", "dB", -24.0, 12.0, 0.0, nullptr, 0},
		    {kFollow, "Noise Follow", "", 0, 1, 1, offOn, 2},
		    {kFollowRelease, "Follow Release", "ms", 50.0, 2000.0, 400.0, nullptr, 0},
		};
		return p;
	}
	// Static loudness makeup per mode (dB), for the modes whose Python matches loudness to the input. Calibrated by
	// the harness (charhost calibrate) on a narration segment the comparisons do not use.
	// (makeup measured: narration 20 s to 40 s at -18 LUFS, peaks -3 dBTP)
	static constexpr double kMakeupDb[kModes] = {0.0, 0.0, -1.30, 0.73, -0.49, 1.75, -9.08, 0.0, -0.27, 1.41};
	double makeupOverride[kModes];
	bool useOverride = false;

	double sr = 48000;
	int nch = 2;
	double p[kNumParams] {};
	VinylChain vinyl;
	CassetteChain cassette;
	SpeakerChain speakers[5];
	BitcrushChain crush;
	MemoryChain memory;
	TerminalChain terminal;
	Delay pad[kModes];
	int lat[kModes] {};
	int Lmax = 0;
	int mode = 0, pendingMode = -1;
	Ramp wetFade;
	SosChain tilt;
	double toneDb = 0.0;
	NoiseFollower follow;
	// The follower reads the input delayed to the point in the mode's chain where its noise enters, so the noise and
	// the cap on the pops line up with the signal they ride on.
	std::vector<double> pkRing;
	int pkW = 0;
	int injLat[kModes] {};
	OutputStage outs;

	LofiEngine ()
	{
		for (int i = 0; i < kNumParams; ++i)
			p[i] = params ()[i].def;
		for (int i = 0; i < kModes; ++i)
			makeupOverride[i] = 0.0;
	}
	double makeupDb (int m) const { return useOverride ? makeupOverride[m] : kMakeupDb[m]; }
	void prepare (double rate, int maxBlock, int channels)
	{
		(void)maxBlock;
		sr = rate;
		nch = std::max (1, std::min (kMaxCh, channels));
		int wl = wowLatency (sr, 0.08 + 0.25 * MemoryChain::am, 0.7, 0.05 + 0.08 * MemoryChain::am, 9.0);
		vinyl.prepare (sr, VinylChain::Cfg (), 0);
		cassette.prepare (sr, CassetteChain::Cfg (), wl, 0);
		for (int i = 0; i < 5; ++i)
			speakers[i].prepare (sr, i, 0);
		crush.prepare (sr, 12000.0, 10);
		memory.prepare (sr, wl, 0);
		terminal.prepare (sr);
		lat[mVinyl] = vinyl.latency ();
		lat[mCassette] = cassette.latency ();
		for (int i = 0; i < 5; ++i)
			lat[mRadio + i] = speakers[i].latency ();
		lat[mBitcrush] = 0;
		lat[mMemory] = memory.latency ();
		lat[mTerminal] = 0;
		Lmax = 0;
		for (int i = 0; i < kModes; ++i)
			Lmax = std::max (Lmax, lat[i]);
		for (int i = 0; i < kModes; ++i)
		{
			pad[i].prepare (Lmax - lat[i] + 2);
			pad[i].setDelay (Lmax - lat[i]);
		}
		wetFade.setLen ((int)(0.005 * sr));
		follow.prepare (sr);
		// where each mode's noise enters its chain, in samples after the input: the vinyl surface after the warp,
		// the cassette hiss after the wow (memory: its cassette, then a record with no warp), the speakers' line
		// noise and hum after the wall's room and the codec
		for (int i = 0; i < kModes; ++i)
			injLat[i] = 0;
		injLat[mVinyl] = vinyl.latency ();
		injLat[mCassette] = cassette.latency ();
		injLat[mMemory] = memory.cas.latency () + memory.vin.latency ();
		for (int i = 0; i < 5; ++i)
		{
			const SpeakerChain& s = speakers[i];
			injLat[mRadio + i] = (s.m.wall ? SpeakerChain::kRoomBlock : 0) + (s.m.codec ? s.codec.lat : 0);
		}
		pkRing.assign (Lmax + 2, 0.0);
		pkW = 0;
		vinyl.nf = &follow;
		cassette.nf = &follow;
		memory.cas.nf = &follow;
		memory.vin.nf = &follow;
		for (auto& s : speakers)
			s.nf = &follow;
		outs.prepare (sr, nch, Lmax);
		mode = (int)p[kMode];
		reset ();
	}
	int latency () const { return outs.latency (); }
	int tail () const { return latency () + (int)(0.5 * sr); }
	void setParam (int i, double v)
	{
		if (i >= 0 && i < kNumParams)
			p[i] = v;
	}
	void setBypass (bool b) { outs.setBypass (b); }
	void applyMakeup ()
	{
		for (int i = 0; i < 5; ++i)
			speakers[i].makeup = undb (makeupDb (mRadio + i));
		memory.makeup = undb (makeupDb (mMemory));
		terminal.makeup = undb (makeupDb (mTerminal));
	}
	void applyTone (int m)
	{
		toneDb = p[kTone];
		double fc = m == mWall ? 400.0 : 1000.0;
		tilt.clear ();
		tilt.add (rbj (Rbj::lowshelf, fc, sr, 0.5, -toneDb / 2.0));
		tilt.add (rbj (Rbj::highshelf, fc, sr, 0.5, toneDb / 2.0));
	}
	void apply ()
	{
		int m = std::max (0, std::min (kModes - 1, (int)std::nearbyint (p[kMode])));
		if (m != mode && pendingMode < 0)
		{
			pendingMode = m;
			wetFade.set (0.0);
		}
		double drv = p[kDrive];
		cassette.setDriveOffset (drv);
		memory.cas.setDriveOffset (drv);
		for (auto& s : speakers)
			s.driveOffset = drv;
		double nz = p[kNoise] <= -59.5 ? 0.0 : undb (p[kNoise]);
		vinyl.noise = cassette.noise = memory.cas.noise = memory.vin.noise = nz;
		for (auto& s : speakers)
			s.noise = nz;
		if (p[kTone] != toneDb)
			applyTone (mode);
		follow.on = p[kFollow] > 0.5;
		follow.setRelease (p[kFollowRelease]);
		applyMakeup ();
		outs.setMix (p[kAmount] / 100.0);
		outs.setGainDb (p[kOutput]);
	}
	void resetMode (int m)
	{
		switch (m)
		{
			case mVinyl: vinyl.reset (); break;
			case mCassette: cassette.reset (); break;
			case mBitcrush: crush.reset (); break;
			case mMemory: memory.reset (); break;
			case mTerminal: terminal.reset (); break;
			default: speakers[m - mRadio].reset (); break;
		}
		pad[m].reset ();
		tilt.reset ();
	}
	void reset ()
	{
		mode = std::max (0, std::min (kModes - 1, (int)std::nearbyint (p[kMode])));
		pendingMode = -1;
		toneDb = 1e9;
		apply ();
		for (int i = 0; i < kModes; ++i)
			resetMode (i);
		applyTone (mode);
		wetFade.jump (1.0);
		follow.reset ();
		std::fill (pkRing.begin (), pkRing.end (), 0.0);
		pkW = 0;
		outs.reset ();
	}
	inline void runMode (double* y)
	{
		switch (mode)
		{
			case mVinyl: vinyl.tick (y); break;
			case mCassette: cassette.tick (y); break;
			case mBitcrush: crush.tick (y, 2); break;
			case mMemory: memory.tick (y); break;
			case mTerminal: terminal.tick (y); break;
			default: speakers[mode - mRadio].tick (y); break;
		}
		double o[2];
		pad[mode].tick (y, o, 2);
		y[0] = o[0];
		y[1] = o[1];
	}
	void process (const float* const* in, float* const* out, int channels, int n)
	{
		apply ();
		float xf[kMaxCh], of[kMaxCh];
		double wet[kMaxCh];
		for (int i = 0; i < n; ++i)
		{
			for (int c = 0; c < nch; ++c)
				xf[c] = in[std::min (c, channels - 1)][i];
			double y[2] = {xf[0], nch > 1 ? (double)xf[1] : (double)xf[0]};
			{
				int L = (int)pkRing.size ();
				pkRing[pkW] = std::max (std::fabs (y[0]), std::fabs (y[1]));
				int r = pkW - injLat[mode];
				if (r < 0)
					r += L;
				follow.tick (pkRing[r]);
				if (++pkW >= L)
					pkW = 0;
			}
			runMode (y);
			if (toneDb != 0.0)
			{
				y[0] = tilt.tick (y[0], 0);
				y[1] = tilt.tick (y[1], 1);
			}
			double f = wetFade.next ();
			if (pendingMode >= 0 && wetFade.settled () && f == 0.0)
			{
				mode = pendingMode;
				pendingMode = -1;
				resetMode (mode);
				applyTone (mode);
				wetFade.set (1.0);
			}
			if (nch == 1)
				wet[0] = 0.5 * (y[0] + y[1]) * f;
			else
			{
				wet[0] = y[0] * f;
				wet[1] = y[1] * f;
			}
			outs.tick (xf, wet, of);
			for (int c = 0; c < channels; ++c)
				out[c][i] = of[std::min (c, nch - 1)];
		}
	}
};

}  // namespace dev
