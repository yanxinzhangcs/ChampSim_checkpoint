/*
 * Daniel A. Jimenez
 *
 * hash.h
 *
 * These are two hash functions for indexing Bloom filters and perceptron
 * weights tables. I found these funny numbers through randomly searching
 * through numbers that had no small prime factors. I found this idea of
 * shifting back and forth by 33 somewhere on the Internet I forgot.
 *
 */

#include <stdint.h>

#ifndef _HASH_H_
#define _HASH_H_
namespace mppspace {

struct dan_hash {
	static const uint64_t c1=0x3212cff2061efb23ul;
	static const uint64_t c2=0x76c486e740078a83ul;
	static const uint64_t c3=0x55497a8558972cbbul;
	static const uint64_t c4=0x3f42f3af0746f5fful;

	static uint64_t hash1 (uint64_t h) {
		h ^= h >> 33;
		h *= c1;
		h ^= h >> 33;
		h *= c2;
		h ^= h >> 33;
		return h;
	}

	static uint64_t hash2 (uint64_t h) {
		h ^= h >> 33;
		h *= c3;
		h ^= h >> 33;
		h *= c4;
		h ^= h >> 33;
		return h;
	}
};
} // namespace mppspace
#endif
