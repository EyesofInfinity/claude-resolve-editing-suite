// Develop Character VST3: parameter descriptions shared by the engines, the plugin glue and the test harness.
#pragma once

#include <cmath>
#include <cstring>

namespace dev {

struct ParamDef
{
	int id;
	const char* name;
	const char* units;
	double min, max, def;
	const char* const* list;   // non-null: a list parameter with nlist entries (plain value is the index)
	int nlist;
};

inline int paramSteps (const ParamDef& p) { return p.list ? p.nlist - 1 : 0; }

inline double toNormalized (const ParamDef& p, double plain)
{
	if (p.list)
		return p.nlist > 1 ? std::fmin (1.0, std::fmax (0.0, plain / (p.nlist - 1))) : 0.0;
	return std::fmin (1.0, std::fmax (0.0, (plain - p.min) / (p.max - p.min)));
}

inline double toPlain (const ParamDef& p, double norm)
{
	norm = std::fmin (1.0, std::fmax (0.0, norm));
	if (p.list)
		return std::floor (norm * (p.nlist - 1) + 0.5);
	return p.min + norm * (p.max - p.min);
}

inline int findParam (const ParamDef* defs, int n, const char* name)
{
	for (int i = 0; i < n; ++i)
	{
		const char* a = defs[i].name;
		const char* b = name;
		bool same = true;
		for (; *a || *b; ++a, ++b)
		{
			char ca = *a, cb = *b;
			if (ca >= 'A' && ca <= 'Z')
				ca = (char)(ca - 'A' + 'a');
			if (cb >= 'A' && cb <= 'Z')
				cb = (char)(cb - 'A' + 'a');
			if (ca == ' ')
				ca = '_';
			if (cb == ' ')
				cb = '_';
			if (ca != cb)
			{
				same = false;
				break;
			}
		}
		if (same)
			return i;
	}
	return -1;
}

}  // namespace dev
